"""Authenticated selection translation; no schema changes or persisted translation history."""
from collections import defaultdict, deque
from threading import Lock
import time
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field, field_validator, model_validator
from sqlalchemy.orm import Session
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from .schemas import InputModel
from .database import get_db
from .config import get_model_settings as get_settings
from .documents import owned_document, storage_path
from .models import LoginSession
from .model_service import ModelFailure, translate_text
from .ai_service import DeveloperProfileResolver, MODEL_SLOTS
from .text_quality import unreliable_characters, opaque_font_mapping
from .pdf_text import ModelInput, model_input_text
from .translation_runtime import current_timing, observed_translation, run_connected
from .translation_proof import issue_translation_proof

slots = MODEL_SLOTS
rate_lock = Lock()
attempts = defaultdict(deque)

class TranslationInput(InputModel):
    modelSource: Literal['developer', 'user', 'mock'] = 'developer'
    modelRevision: str | None = Field(default=None,max_length=36)
    text: str = Field(min_length=1, max_length=6000)
    sourceLanguage: Literal['en', 'zh']
    targetLanguage: Literal['en', 'zh']
    pageNumber: int = Field(ge=1, strict=True)
    contextRevision: int = Field(ge=0, strict=True)

    @field_validator('text')
    @classmethod
    def nonempty(cls, value):
        if not value.strip(): raise ValueError('Empty selection')
        return value

    @model_validator(mode='after')
    def direction(self):
        if self.sourceLanguage == self.targetLanguage: raise ValueError('Different languages required')
        return self

def error(status, code, message):
    raise HTTPException(status, detail={'code': code, 'message': message})

def model_resolver():
    """Dependency override point for a future authenticated user-profile resolver."""
    class LazyDeveloperResolver:
        def resolve(self, principal_id, capability):
            return DeveloperProfileResolver(get_settings()).resolve(principal_id, capability)
    return LazyDeveloperResolver()

def create_translation_router(require_csrf):
    router = APIRouter(prefix='/api/v1/documents', tags=['translations'])

    @router.post('/{document_id}/translations')
    @observed_translation
    async def translate(document_id: str, payload: TranslationInput, request: Request, response: Response, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db), resolver=Depends(model_resolver)):
        doc, attachment = owned_document(db, session.user_id, document_id)
        from .config import get_settings as business_settings
        if payload.modelSource == 'developer' and business_settings().unified_acceptance:
            error(403,'DEVELOPER_MODEL_DISABLED','统一验收站不使用开发者额度，请选择个人模型或明确的 Mock 模式')
        if unreliable_characters(payload.text):
            error(422, 'PDF_TEXT_UNRELIABLE', '无法可靠提取原文：选区包含异常编码，已阻止翻译。请使用有效文字映射或经人工核对的 OCR 副本。')
        model_input = ModelInput(payload.text)
        pdf_started = time.perf_counter()
        try:
            with storage_path(attachment.storage_key).open('rb') as stream:
                reader = PdfReader(stream)
                pages = len(reader.pages)
                if payload.pageNumber <= pages and opaque_font_mapping(reader.pages[payload.pageNumber-1]):
                    error(422, 'PDF_TEXT_UNRELIABLE', '无法可靠提取原文：来源页缺少可用文字映射，已阻止翻译。请使用带有效映射的 PDF 或经人工核对的 OCR 副本。')
                if payload.sourceLanguage == 'en' and payload.pageNumber <= pages:
                    model_input = model_input_text(payload.text, reader.pages[payload.pageNumber-1])
        except (OSError, ValueError, PdfReadError):
            error(422, 'PDF_UNAVAILABLE', '无法读取此 PDF，请检查文献文件')
        finally:
            metrics = current_timing.get()
            if metrics is not None: metrics.pdf_ms = (time.perf_counter()-pdf_started)*1000
        if payload.pageNumber > pages:
            error(422, 'INVALID_PAGE', '来源页码超出 PDF 范围')
        # Release DB transaction before waiting on an external service.
        owner = session.user_id
        file_sha256 = attachment.sha256  # Snapshot before rollback expires ORM attributes.
        profile_revision = None
        if payload.modelSource == 'user':
            from .user_models import snapshot
            if not payload.modelRevision: error(409,'MODEL_PROFILE_CHANGED','请重新加载个人模型配置后再翻译')
            try: resolver,profile_revision = snapshot(db,owner,payload.modelRevision)
            except ModelFailure as failure: error(failure.status,failure.code,failure.message)
        db.rollback()
        with rate_lock:
            now = time.monotonic()
            for user in list(attempts):
                while attempts[user] and attempts[user][0] <= now - 60: attempts[user].popleft()
                if not attempts[user]: del attempts[user]
            if len(attempts[owner]) >= 20: error(429, 'TRANSLATION_RATE_LIMIT', '翻译请求过于频繁，请稍后重试')
        if not slots.acquire(blocking=False):
            error(429, 'TRANSLATION_BUSY', '本地翻译请求已达并发上限，请等待当前请求结束后再试。')
        try:
            # Count admitted model attempts only. Busy rejections do not consume
            # the per-user provider budget. Recheck under lock after admission.
            with rate_lock:
                if len(attempts[owner]) >= 20: error(429, 'TRANSLATION_RATE_LIMIT', '翻译请求过于频繁，请稍后重试')
                attempts[owner].append(time.monotonic())
            if payload.modelSource == 'mock':
                from .translation_modes import translate_mock
                translated = await translate_mock(model_input.text,payload.sourceLanguage,payload.targetLanguage)
            else:
                translated = await run_connected(request, translate_text(model_input.text, payload.sourceLanguage, payload.targetLanguage, None, user_id=owner, resolver=resolver))
        except ModelFailure as failure:
            error(failure.status, failure.code, failure.message)
        finally:
            slots.release()
        if profile_revision:
            from .user_models import require_unchanged
            require_unchanged(db,owner,profile_revision)
        result = {'originalText': payload.text, 'translatedText': translated, 'source': {
            'documentId': document_id, 'pageNumber': payload.pageNumber,
            'sourceLanguage': payload.sourceLanguage, 'targetLanguage': payload.targetLanguage,
            'contextRevision': payload.contextRevision, 'sourceType': 'translation'}}
        if profile_revision: result['modelConfiguration'] = {'source':'user','revision':profile_revision}
        if payload.modelSource == 'mock': result['modelConfiguration'] = {'source':'mock'}
        if model_input.joins:
            result.update(modelInputText=model_input.text, normalizationCount=model_input.joins)
        result['translationProof'] = issue_translation_proof(owner, file_sha256, result, origin='isolated_mock' if payload.modelSource == 'mock' else None)
        return result
    return router
