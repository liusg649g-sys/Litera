"""Short-lived, owner-bound receipts for server-produced translation captures.

Receipts prove the response came from this backend. They do not authorize a
client to change its source, and test-environment responses are always Mock.
"""
import hashlib
import hmac
import json
import time
from typing import Literal
from pydantic import Field
from .config import get_settings
from .documents import reject
from .schemas import InputModel

PROOF_TTL_SECONDS = 24 * 60 * 60
PROOF_FUTURE_SKEW_SECONDS = 60
_DOMAIN = b"litera-note-translation-v1\x00"


class TranslationProof(InputModel):
    version: Literal[1]
    issuedAt: int = Field(ge=0, strict=True)
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: Literal['model_api', 'isolated_mock']


def clock_seconds():
    return int(time.time())


def provenance():
    return 'isolated_mock' if get_settings().app_env == 'test' else 'model_api'


def _message(owner, file_sha256, result, issued_at, origin):
    source = result['source']
    value = {'ownerId': owner, 'fileSha256': file_sha256,
             'documentId': source['documentId'], 'pageNumber': source['pageNumber'],
             'sourceLanguage': source['sourceLanguage'], 'targetLanguage': source['targetLanguage'],
             'contextRevision': source['contextRevision'], 'originalText': result['originalText'],
             'translatedText': result['translatedText'], 'issuedAt': issued_at, 'provenance': origin}
    for key in ('modelInputText', 'normalizationCount'):
        if key in result:
            value[key] = result[key]
    return _DOMAIN + json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def _signature(owner, file_sha256, result, issued_at, origin):
    return hmac.new(get_settings().session_secret.encode('utf-8'),
                    _message(owner, file_sha256, result, issued_at, origin), hashlib.sha256).hexdigest()


def issue_translation_proof(owner, file_sha256, result, origin=None):
    issued_at, origin = clock_seconds(), origin or provenance()
    if origin != provenance() and not (origin == 'isolated_mock' and get_settings().translation_mock_enabled):
        reject(503,'MOCK_DISABLED','此环境未启用模拟翻译')
    return {'version': 1, 'issuedAt': issued_at, 'provenance': origin,
            'signature': _signature(owner, file_sha256, result, issued_at, origin)}


def verify_translation_proof(owner, file_sha256, result, proof):
    current = clock_seconds()
    if proof.issuedAt > current + PROOF_FUTURE_SKEW_SECONDS or current - proof.issuedAt > PROOF_TTL_SECONDS:
        reject(422, 'TRANSLATION_PROOF_EXPIRED', '译文凭据已过期，请重新翻译后保存。')
    expected = _signature(owner, file_sha256, result, proof.issuedAt, proof.provenance)
    allowed = {provenance()}
    if get_settings().translation_mock_enabled: allowed.add('isolated_mock')
    if proof.provenance not in allowed or not hmac.compare_digest(expected, proof.signature):
        reject(422, 'TRANSLATION_PROOF_INVALID', '译文与其原文来源不匹配，请重新翻译后保存。')
    return proof.provenance
