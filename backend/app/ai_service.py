"""Shared model transport and request-scoped profile boundary, independent of translation."""
from dataclasses import dataclass, field
from typing import Protocol, Literal
import asyncio
import json
import time
from .translation_runtime import current_timing
from urllib.parse import urlsplit
import httpx
from pydantic import SecretStr

class ModelFailure(Exception):
    def __init__(self, code, message, status=503):
        self.code, self.message, self.status = code, message, status

@dataclass(frozen=True)
class ModelProfile:
    provider: str
    base_url: str
    model: str
    api_key: SecretStr = field(repr=False)
    scope: Literal['developer', 'user'] = 'developer'
    owner_user_id: str | None = None
    verified: bool = False
    max_output_tokens: int = 2048

class ProfileResolver(Protocol):
    def resolve(self, principal_id: str, capability: str) -> ModelProfile: ...

class DeveloperProfileResolver:
    """Developer-local config only, never a store for final users' credentials."""
    def __init__(self, settings): self.settings = settings
    def resolve(self, principal_id, capability):
        s = self.settings
        if not principal_id or capability != 'translation':
            raise ModelFailure('MODEL_PROFILE_UNAVAILABLE', '模型未配置：没有可用的调用配置')
        if not getattr(s, 'translation_api_key', None) or not getattr(s, 'translation_model', '') or not getattr(s, 'translation_base_url', ''):
            raise ModelFailure('MODEL_NOT_CONFIGURED', '模型未配置：请在后端本地配置模型服务')
        return ModelProfile(provider=s.translation_provider,base_url=s.translation_base_url,model=s.translation_model,
            api_key=s.translation_api_key,verified=getattr(s,'translation_model_verified',False),
            max_output_tokens=getattr(s,'max_output_tokens',2048))

class Adapter(Protocol):
    async def complete(self, messages: list[dict[str,str]], profile: ModelProfile) -> str: ...

class OpenAICompatible:
    async def complete(self, messages, profile):
        base = profile.base_url.rstrip('/')
        client_options = {}
        if profile.scope == 'user':
            from .model_network import validate_base, PublicModelTransport
            base = validate_base(base)
            client_options['transport'] = PublicModelTransport()
        url = urlsplit(base)
        if url.username or url.password or url.query or url.fragment or not url.hostname:
            raise ModelFailure('MODEL_CONFIG', '模型地址配置无效')
        if url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost', '::1')):
            raise ModelFailure('MODEL_CONFIG', '模型地址必须使用 HTTPS（本机测试除外）')
        if not 16 <= profile.max_output_tokens <= 4096:
            raise ModelFailure('MODEL_CONFIG', '模型输出 Token 上限无效')
        payload = {'model': profile.model, 'messages': messages, 'temperature': 0, 'max_tokens': profile.max_output_tokens}
        metrics = current_timing.get()
        gateway_started = time.perf_counter()
        if metrics is not None: metrics.gateway_calls += 1
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5), follow_redirects=False, trust_env=False, **client_options) as client:
                async with client.stream('POST', base + '/chat/completions', headers={'Authorization': 'Bearer ' + profile.api_key.get_secret_value()}, json=payload) as response:
                    if metrics is not None: metrics.gateway_status = response.status_code
                    if response.status_code in (401, 403):
                        raise ModelFailure('MODEL_AUTH', '模型服务认证失败，请联系管理员检查配置')
                    if response.status_code in (402, 429):
                        raise ModelFailure('MODEL_QUOTA', '模型网关额度不足或正在限流，请稍后重试。', 429)
                    if response.status_code == 404:
                        raise ModelFailure('MODEL_NOT_FOUND', '模型名称或对话接口不存在，请检查模型设置')
                    if response.status_code != 200:
                        raise ModelFailure('MODEL_UNAVAILABLE', '模型服务暂时不可用，请稍后重试')
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 128 * 1024:
                            raise ModelFailure('MODEL_INVALID_RESPONSE', '模型返回内容过长或格式无效')
            data = json.loads(body)
            choice = data['choices'][0]
            if not isinstance(choice, dict) or not isinstance(choice.get('message'), dict):
                raise ValueError('invalid choice')
            if choice.get('finish_reason') == 'length':
                raise ModelFailure('MODEL_OUTPUT_LIMIT', '译文达到输出上限，可能不完整；请缩小选区后重试。')
            result = choice['message']['content']
            if not isinstance(result, str) or not result.strip() or len(result) > 20000:
                raise ValueError('invalid content')
            # Never return a credential even if a faulty upstream echoes it.
            if profile.api_key.get_secret_value() in result:
                raise ValueError('credential echoed')
            return result.strip()
        except ModelFailure:
            raise
        except (httpx.TimeoutException, TimeoutError):
            raise ModelFailure('MODEL_TIMEOUT', '翻译超时，请重试', 504) from None
        except httpx.HTTPError:
            raise ModelFailure('MODEL_UNAVAILABLE', '无法连接模型服务，请稍后重试') from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise ModelFailure('MODEL_INVALID_RESPONSE', '模型返回格式无效，请重试') from None
        finally:
            if metrics is not None: metrics.gateway_ms += (time.perf_counter()-gateway_started)*1000

ADAPTERS: dict[str, Adapter] = {'openai_compatible': OpenAICompatible()}

class ModelService:
    def __init__(self, adapters=None):
        self.adapters = ADAPTERS if adapters is None else adapters

    async def complete(self, messages, principal_id: str, profile: ModelProfile):
        # An authenticated owner is required independently of the provider implementation.
        if not principal_id or (profile.scope == 'user' and profile.owner_user_id != principal_id):
            raise ModelFailure('MODEL_PROFILE_FORBIDDEN', '不能使用其他用户的模型配置', 403)
        if profile.scope not in ('developer','user') or (profile.scope == 'developer' and profile.owner_user_id is not None):
            raise ModelFailure('MODEL_PROFILE_FORBIDDEN', '模型配置作用域无效', 403)
        adapter = self.adapters.get(profile.provider)
        if not profile.verified or not adapter or not profile.api_key or not profile.model or not profile.base_url:
            raise ModelFailure('MODEL_NOT_CONFIGURED', '模型未配置：服务或模型尚未确认可用')
        if profile.scope == 'user':
            try:
                async with asyncio.timeout(35): result = await adapter.complete(messages, profile)
            except TimeoutError:
                raise ModelFailure('MODEL_TIMEOUT', '模型请求超时，请稍后重试', 504) from None
        else:
            result = await adapter.complete(messages, profile)
        if not isinstance(result,str) or not result.strip() or len(result)>20000 or profile.api_key.get_secret_value() in result:
            raise ModelFailure('MODEL_INVALID_RESPONSE', '模型返回格式无效，请重试')
        return result.strip()
