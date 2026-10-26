"""Inspect config without secrets; --probe makes at most two synthetic model calls.
Does not edit .env, set verified=true, use a database, or read any PDF.
"""
import argparse
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.ai_service import DeveloperProfileResolver, ModelFailure, OpenAICompatible
from app.config import get_model_settings
from app.model_service import translation_messages

SAMPLES = [
    ('en', 'zh', 'Optical microscopy is widely used in scientific research.'),
    ('zh', 'en', '光学显微镜广泛应用于科学研究。'),
]

async def probe(settings, adapter=None, on_start=None):
    # The unverified profile is used ONLY for this explicit synthetic validation.
    # Normal website requests still require ModelService's verified gate.
    profile = replace(DeveloperProfileResolver(settings).resolve('local-verification', 'translation'), max_output_tokens=128)
    if profile.provider != 'openai_compatible':
        raise ModelFailure('MODEL_CONFIG', '此探测器只验证已适配的 OpenAI 兼容对话协议')
    transport = adapter or OpenAICompatible()
    results = []
    for source, target, text in SAMPLES:
        if on_start: on_start()
        translated = await transport.complete(translation_messages(text, source, target), profile)
        results.append({'sourceLanguage': source, 'targetLanguage': target, 'input': text,
                        'translation': translated, 'httpStatus': 200})
    return results

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', action='store_true', help='Allow at most two real requests, <=128 output tokens each; stop on first failure')
    args = parser.parse_args()
    attempts = 0
    def started():
        nonlocal attempts
        attempts += 1
    try:
        settings = get_model_settings()
        complete = bool(settings.provider and settings.base_url and settings.model and settings.api_key and settings.api_key.get_secret_value().strip())
        report = {'configured': complete, 'verifiedFlag': settings.verified, 'realRequestsExecuted': False, 'requestsAttempted': 0}
        if not complete:
            report.update(status='MODEL_NOT_CONFIGURED', message='模型未配置：请仅在 backend/.env 私下填写 AI_PROVIDER、AI_BASE_URL、AI_MODEL、AI_API_KEY；保留 AI_MODEL_VERIFIED=false 直至真实验证。')
        elif args.probe:
            results = asyncio.run(probe(settings, on_start=started))
            report.update(realRequestsExecuted=True, requestsAttempted=attempts, results=results, status='BILINGUAL_PROTOCOL_OK', message='两次真实请求返回有效译文。仍需检查译文合理性；本脚本不会自动更改验证标记。')
        else:
            report.update(status='CONFIG_ONLY', message='未发送请求；显式 --probe 才会验证真实接口。')
        print(json.dumps(report, ensure_ascii=False))
        return 0 if complete else 2
    except ModelFailure as error:
        # Never print the upstream response, config, key or exception traceback.
        print(json.dumps({'status': error.code, 'message': error.message, 'completed': False, 'requestsAttempted': attempts, 'maxRequests': 2}, ensure_ascii=False))
        return 1
    except Exception:
        print(json.dumps({'status': 'CONFIG_OR_PROBE_ERROR', 'requestsAttempted': attempts, 'message': '配置或探测失败；未输出敏感配置或内部异常。'}, ensure_ascii=False))
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
