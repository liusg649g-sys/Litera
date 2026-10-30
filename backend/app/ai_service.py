"""Shared model transport and request-scoped profile boundary, independent of translation."""
from dataclasses import dataclass, field
from typing import Protocol, Literal
import asyncio
import json
import time
from threading import BoundedSemaphore
from .translation_runtime import current_timing
from urllib.parse import urlsplit
import httpx
from pydantic import SecretStr

# One shared ceiling for every outbound model call (chat and embedding). Translation
# admission keeps its non-blocking semantics; QA/index builds acquire the same slots.
MODEL_SLOTS = BoundedSemaphore(2)

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
    """Developer-local config only, never a store for final users' credentials.

    Chat (translation/qa) and embedding share the gateway and key; only the model
    name and the verified flag differ. No user-supplied key is used for embeddings.
    """
    def __init__(self, settings): self.settings = settings

    def _get(self, name, legacy, default=None):
        # ModelSettings exposes unified AI_* names; older callers (and tests) still
        # hand a namespace with only the TRANSLATION_* aliases.
        value = getattr(self.settings, name, None)
        return getattr(self.settings, legacy, default) if value is None else value

    def resolve(self, principal_id, capability):
        if not principal_id or capability not in ('translation', 'qa', 'embedding'):
            raise ModelFailure('MODEL_PROFILE_UNAVAILABLE', '模型未配置：没有可用的调用配置')
        api_key = self._get('api_key', 'translation_api_key')
        base_url = self._get('base_url', 'translation_base_url', '')
        provider = self._get('provider', 'translation_provider', 'openai_compatible')
        if not api_key or not base_url:
            raise ModelFailure('MODEL_NOT_CONFIGURED', '模型未配置：请在后端本地配置模型服务')
        if capability == 'embedding':
            embedding_model = getattr(self.settings, 'embedding_model', '')
            if not embedding_model:
                raise ModelFailure('MODEL_NOT_CONFIGURED', '模型未配置：请在后端本地配置向量模型')
            embed_key = getattr(self.settings, 'embedding_api_key', None)
            embed_key = embed_key if embed_key and embed_key.get_secret_value() else api_key
            embed_base = getattr(self.settings, 'embedding_base_url', '') or base_url
            return ModelProfile(provider=provider, base_url=embed_base, model=embedding_model,
                api_key=embed_key, verified=getattr(self.settings, 'embedding_verified', False),
                max_output_tokens=16)
        model = self._get('model', 'translation_model', '')
        if not model:
            raise ModelFailure('MODEL_NOT_CONFIGURED', '模型未配置：请在后端本地配置模型服务')
        return ModelProfile(provider=provider,base_url=base_url,model=model,
            api_key=api_key,verified=bool(self._get('verified', 'translation_model_verified', False)),
            max_output_tokens=getattr(self.settings,'max_output_tokens',2048))

class Adapter(Protocol):
    async def complete(self, messages: list[dict[str,str]], profile: ModelProfile) -> str: ...
    async def embeddings(self, texts: list[str], profile: ModelProfile) -> list[list[float]]: ...

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

    async def embeddings(self, texts, profile):
        """Batch embeddings over the same gateway, TLS and auth rules as chat."""
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
        metrics = current_timing.get()
        gateway_started = time.perf_counter()
        if metrics is not None: metrics.gateway_calls += 1
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(40, connect=5), follow_redirects=False,
                                         trust_env=False, **client_options) as client:
                response = await client.post(base + '/embeddings',
                    headers={'Authorization': 'Bearer ' + profile.api_key.get_secret_value()},
                    json={'model': profile.model, 'input': texts})
            if metrics is not None: metrics.gateway_status = response.status_code
            if response.status_code in (401, 403):
                raise ModelFailure('MODEL_AUTH', '模型服务认证失败，请联系管理员检查配置')
            if response.status_code in (402, 429):
                raise ModelFailure('MODEL_QUOTA', '模型网关额度不足或正在限流，请稍后重试。', 429)
            if response.status_code == 404:
                raise ModelFailure('MODEL_NOT_FOUND', '向量模型或接口不存在，请检查模型设置')
            if response.status_code != 200:
                raise ModelFailure('MODEL_UNAVAILABLE', '模型服务暂时不可用，请稍后重试')
            if len(response.content) > 8 * 1024 * 1024:
                raise ModelFailure('MODEL_INVALID_RESPONSE', '模型返回内容过长或格式无效')
            data = response.json()
            rows = data['data']
            if not isinstance(rows, list) or len(rows) != len(texts):
                raise ValueError('invalid embedding count')
            vectors = []
            for row in sorted(rows, key=lambda item: item.get('index', 0)):
                vector = row['embedding']
                if not isinstance(vector, list) or not vector:
                    raise ValueError('invalid embedding')
                vectors.append([float(value) for value in vector])
            width = len(vectors[0])
            if any(len(vector) != width for vector in vectors):
                raise ValueError('inconsistent dimension')
            return vectors
        except ModelFailure:
            raise
        except (httpx.TimeoutException, TimeoutError):
            raise ModelFailure('MODEL_TIMEOUT', '模型请求超时，请重试', 504) from None
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

    async def embed(self, texts: list[str], principal_id: str, profile: ModelProfile):
        """Developer-scoped batch embeddings. User chat profiles never carry vectors."""
        if not principal_id or profile.scope != 'developer':
            raise ModelFailure('MODEL_PROFILE_FORBIDDEN', '不能使用其他用户的模型配置', 403)
        adapter = self.adapters.get(profile.provider)
        if (not profile.verified or not adapter or not profile.api_key or not profile.model
                or not profile.base_url or not hasattr(adapter, 'embeddings')):
            raise ModelFailure('MODEL_NOT_CONFIGURED', '模型未配置：向量服务尚未确认可用', 503)
        if not texts or len(texts) > 64 or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ModelFailure('MODEL_INVALID_REQUEST', '向量请求内容无效', 422)
        vectors = await adapter.embeddings(texts, profile)
        if not isinstance(vectors, list) or len(vectors) != len(texts) or not all(vectors):
            raise ModelFailure('MODEL_INVALID_RESPONSE', '模型返回格式无效，请重试')
        return vectors
