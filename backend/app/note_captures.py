"""Append-only, source-verified note excerpts in the existing notes.sources JSON.

Manual plain text remains independent. Coordinates are validated metadata only:
page-level provenance does not claim an exact, server-verified text location.
"""
import hashlib
import json
import os
from threading import Lock
from typing import Annotated, Literal
from uuid import UUID
from fastapi import Depends, Query, Response
import pypdfium2 as pdfium
from pydantic import Field, field_validator, model_validator
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .answer_sources import AiAnswerSource, get_answer_resolver, read_answer
from .config import get_settings
from .database import get_db
from .documents import iso, owned_document, reject, storage_path
from .models import LoginSession, Note, NoteDocument
from .notes import TITLE_LIMIT, dto, now, owned_note, ready, schema_available
from .pdf_source_validation import canonical_text, source_text_matches
from .schemas import InputModel
from .text_quality import opaque_font_mapping, unreliable_characters
from .translation_proof import TranslationProof, verify_translation_proof

ORIGINAL_LIMIT = 6000
TRANSLATED_LIMIT = 20000
BLOCK_LIMIT = 100
SOURCE_BYTES_LIMIT = 1024 * 1024
_PDFIUM_LOCK = Lock()  # PDFium's native API is not thread-safe within one process.


def canonical(text):
    return canonical_text(text)


class SelectionRect(InputModel):
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)
    width: float = Field(gt=0, le=1, allow_inf_nan=False)
    height: float = Field(gt=0, le=1, allow_inf_nan=False)
    baseline: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode='after')
    def bounds(self):
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError('Selection rectangle outside page')
        return self


class TextRange(InputModel):
    item: int = Field(ge=0, strict=True)
    start: int = Field(ge=0, strict=True)
    end: int = Field(ge=1, strict=True)

    @model_validator(mode='after')
    def ordered(self):
        if self.end <= self.start: raise ValueError('Invalid text range')
        return self


class SelectionPosition(InputModel):
    pageNumber: int = Field(ge=1, strict=True)
    rects: list[SelectionRect] = Field(min_length=1, max_length=512)
    textQuote: str = Field(min_length=1, max_length=ORIGINAL_LIMIT)
    textRanges: list[TextRange] | None = Field(default=None, max_length=1024)

    @field_validator('textQuote')
    @classmethod
    def quote_nonempty(cls, value):
        if not value.strip(): raise ValueError('Empty text quote')
        return value


class CaptureSource(InputModel):
    kind: Literal['pdf_excerpt', 'translation_excerpt']
    documentId: str = Field(min_length=1, max_length=36)
    pageNumber: int = Field(ge=1, strict=True)
    originalText: str = Field(min_length=1, max_length=ORIGINAL_LIMIT)
    positions: list[SelectionPosition] = Field(max_length=20)
    contextRevision: int = Field(ge=0, strict=True)
    translatedText: str | None = Field(default=None, min_length=1, max_length=TRANSLATED_LIMIT)
    sourceLanguage: Literal['en', 'zh'] | None = None
    targetLanguage: Literal['en', 'zh'] | None = None
    translationProof: TranslationProof | None = None
    modelInputText: str | None = Field(default=None, min_length=1, max_length=ORIGINAL_LIMIT)
    normalizationCount: int | None = Field(default=None, ge=1, strict=True)
    historical: bool = Field(default=False, strict=True)
    confirmHistorical: bool = Field(default=False, strict=True)

    @model_validator(mode='after')
    def source_contract(self):
        if not self.originalText.strip(): raise ValueError('Empty selection')
        pages = [position.pageNumber for position in self.positions]
        if pages and (pages != sorted(set(pages)) or pages[0] != self.pageNumber):
            raise ValueError('Selection pages must be unique, ordered and start at pageNumber')
        if sum(len(position.rects) for position in self.positions) > 512:
            raise ValueError('Too many selection rectangles')
        if self.positions and canonical(' '.join(position.textQuote for position in self.positions)) != canonical(self.originalText):
            raise ValueError('Selection quotes do not match original text')
        translation_fields = {'translatedText','sourceLanguage','targetLanguage','translationProof','modelInputText','normalizationCount'}
        if self.kind == 'pdf_excerpt':
            if translation_fields & self.model_fields_set or self.historical or self.confirmHistorical:
                raise ValueError('PDF excerpts cannot carry translation data')
        else:
            if not all((self.translatedText and self.translatedText.strip(), self.sourceLanguage,
                        self.targetLanguage, self.translationProof)):
                raise ValueError('Translation and its server receipt are required')
            if self.sourceLanguage == self.targetLanguage: raise ValueError('Different languages required')
            if (self.modelInputText is None) != (self.normalizationCount is None):
                raise ValueError('Normalized model input and count must be supplied together')
            if self.historical != self.confirmHistorical:
                raise ValueError('Historical translation requires explicit confirmation')
        return self


class CaptureInput(InputModel):
    operationId: str = Field(min_length=36, max_length=36)
    noteId: str = Field(min_length=36, max_length=36)
    version: int | None = Field(default=None, ge=1, strict=True)
    newNoteTitle: str | None = Field(default=None, min_length=1, max_length=TITLE_LIMIT)
    associationMode: Literal['link', 'keep']
    source: Annotated[CaptureSource | AiAnswerSource, Field(discriminator='kind')]

    @field_validator('operationId', 'noteId')
    @classmethod
    def valid_uuid(cls, value):
        return str(UUID(value))

    @field_validator('newNoteTitle')
    @classmethod
    def title_nonempty(cls, value):
        if value is not None:
            value = value.strip()
            if not value: raise ValueError('Title cannot be empty')
        return value

    @model_validator(mode='after')
    def note_contract(self):
        if (self.newNoteTitle is None) == (self.version is None):
            raise ValueError('Existing note requires version; new note requires title and no version')
        return self


def fingerprint(payload):
    # Version is a concurrency precondition, not the logical operation identity.
    value = payload.model_dump(exclude={'version'}, exclude_none=True)
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def checked_sources(item):
    if item.source_schema_version != 1 or item.content_format != 'plain-text' or not isinstance(item.sources, list):
        reject(409, 'NOTE_SOURCE_FORMAT_UNSUPPORTED', '笔记来源格式暂不支持，未修改原有内容。')
    return item.sources


def existing_capture(db, owner, payload, digest):
    item = db.get(Note, payload.noteId)
    if item is None: return None
    if item.owner_id != owner: reject(404, 'NOTE_NOT_FOUND', '笔记不存在或不可访问')
    sources = checked_sources(item)
    block = next((block for block in sources if isinstance(block, dict) and block.get('id') == payload.operationId), None)
    if block is not None:
        if block.get('requestFingerprint') != digest:
            reject(409, 'NOTE_CAPTURE_CONFLICT', '同一保存操作的内容发生变化，请重新选择后保存。')
        # Replay never recreates a relationship which was subsequently unlinked.
        document_id = block.get('contextDocument', {}).get('documentId') if block.get('kind') == 'ai_answer' else payload.source.documentId
        linked = db.get(NoteDocument, (item.id, document_id)) is not None
        return {'note': dto(db, item, True), 'blockId': block['id'], 'created': False,
                'linked': linked, 'replayed': True}
    return None


def validate_pdf_source(source, attachment):
    positions = [(position.pageNumber, position.textQuote) for position in source.positions]
    if not positions: positions = [(source.pageNumber, source.originalText)]
    if unreliable_characters(source.originalText) or any(unreliable_characters(text) for _, text in positions):
        reject(422, 'PDF_TEXT_UNRELIABLE', '无法可靠提取原文，已阻止保存。请使用有效文字映射或经人工核对的 OCR 副本。')
    try:
        path = storage_path(attachment.storage_key)
        with path.open('rb') as stream:
            reader = PdfReader(stream)
            for number, quote in positions:
                if number > len(reader.pages):
                    reject(422, 'INVALID_PAGE', '来源页码超出 PDF 范围')
                page = reader.pages[number - 1]
                if opaque_font_mapping(page):
                    reject(422, 'PDF_TEXT_UNRELIABLE', '来源页缺少可靠文字映射，已阻止保存。')
            pypdf_texts = {number: reader.pages[number - 1].extract_text() or '' for number, _ in positions}
        pdfium_texts = {}
        with _PDFIUM_LOCK:
            with pdfium.PdfDocument(path) as pdfium_document:
                for number in dict.fromkeys(number for number, _ in positions):
                    if number > len(pdfium_document):
                        reject(422, 'INVALID_PAGE', '来源页码超出 PDF 范围')
                    pdfium_page = pdfium_document[number - 1]
                    try:
                        pdfium_text_page = pdfium_page.get_textpage()
                        try:
                            pdfium_texts[number] = pdfium_text_page.get_text_range() or ''
                        finally:
                            pdfium_text_page.close()
                    finally:
                        pdfium_page.close()
        for number, quote in positions:
            reliable = [text for text in (pypdf_texts[number], pdfium_texts[number]) if text and not unreliable_characters(text)]
            if not reliable:
                reject(422, 'PDF_TEXT_UNRELIABLE', '来源页包含异常文字编码，已阻止保存。')
            if not source_text_matches(quote, reliable):
                reject(422, 'PDF_TEXT_NOT_FOUND', '无法在来源页可靠核对选区文字，未保存摘录。请重新选择可复制的正文。')
    except (OSError, ValueError, PdfReadError, pdfium.PdfiumError):
        reject(422, 'PDF_UNAVAILABLE', '无法读取此 PDF，请检查文献文件。')
    return [number for number, _ in positions]


def make_block(payload, digest, doc, attachment, owner):
    source = payload.source
    pages = validate_pdf_source(source, attachment)
    origin = None
    if source.kind == 'translation_excerpt':
        result = {'originalText': source.originalText, 'translatedText': source.translatedText,
                  'source': {'documentId': source.documentId, 'pageNumber': source.pageNumber,
                             'sourceLanguage': source.sourceLanguage, 'targetLanguage': source.targetLanguage,
                             'contextRevision': source.contextRevision}}
        for key in ('modelInputText', 'normalizationCount'):
            if getattr(source, key) is not None: result[key] = getattr(source, key)
        origin = verify_translation_proof(owner, attachment.sha256, result, source.translationProof)
    block = {'id': payload.operationId, 'kind': source.kind, 'createdAt': iso(now()),
             'originalText': source.originalText,
             'source': {'documentId': doc.id, 'title': doc.title, 'fileSha256': attachment.sha256,
                        'pageNumber': source.pageNumber, 'pageNumbers': pages,
                        'positions': [position.model_dump(exclude_none=True) for position in source.positions],
                        'contextRevision': source.contextRevision, 'precision': 'page'},
             'historical': source.historical, 'requestFingerprint': digest}
    if origin is not None:
        block.update(translatedText=source.translatedText, sourceLanguage=source.sourceLanguage,
                     targetLanguage=source.targetLanguage, translationProvenance=origin)
        for key in ('modelInputText', 'normalizationCount'):
            if getattr(source, key) is not None: block[key] = getattr(source, key)
    return block


def checked_answer(resolver, db, owner, source):
    record = read_answer(resolver, db, owner, source)
    doc, attachment = owned_document(db, owner, record.documentId, lock=True)
    # Read and hash actual bytes as well as the DB identity: never bind a quote
    # to a changed PDF merely because its metadata was not updated.
    if attachment.sha256 != record.fileSha256:
        reject(409, 'AI_SOURCE_CHANGED', '回答所属PDF版本已变化，未保存。')
    try:
        with storage_path(attachment.storage_key).open('rb') as stream:
            actual_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    except OSError:
        reject(422, 'PDF_UNAVAILABLE', '无法读取回答来源PDF，未保存。')
    if actual_hash != record.fileSha256:
        reject(409, 'AI_SOURCE_CHANGED', '回答所属PDF版本已变化，未保存。')
    if record.provenance == 'model_api' and record.evidenceState == 'verified' and doc.extraction_version != record.extractionVersion:
        reject(409, 'AI_SOURCE_CHANGED', '回答的解析版本与当前文献不一致，未保存。')
    for citation in record.citations:
        # D1 supports single-document answers. Multi-document QA evidence needs
        # a separately agreed contract; never infer permission from a title.
        if (citation.documentId != doc.id or citation.fileSha256 != attachment.sha256
                or citation.extractionVersion != record.extractionVersion):
            reject(422, 'AI_EVIDENCE_INVALID', '回答引用与文献或版本不一致，未保存。')
        try:
            verified = resolver.verify_citation(db, owner, record, citation)
        except Exception:
            reject(503, 'AI_ANSWER_UNAVAILABLE', '回答证据服务暂不可用，未保存。')
        if verified is not True:
            reject(422, 'AI_EVIDENCE_INVALID', '无法核验回答引用，未保存。')
        validate_pdf_source(CaptureSource(kind='pdf_excerpt', documentId=doc.id,
            pageNumber=citation.pageNumber, originalText=citation.quote, positions=[], contextRevision=record.contextRevision), attachment)
    return record, doc, attachment


def answer_snapshot(record, doc):
    # Strict public allowlist; internal ownership and service configuration never
    # reach the browser. PDF citations are separate from generated answer text.
    return dict(answerId=record.answerId, answerRevision=record.answerRevision,
        question=record.question, answer=record.answer, mode=record.mode, status=record.status,
        provenance=record.provenance, evidenceState=record.evidenceState,
        contextDocument=dict(documentId=doc.id, title=doc.title, fileSha256=record.fileSha256,
            contextRevision=record.contextRevision, extractionVersion=record.extractionVersion),
        citations=[dict(c.model_dump(), title=doc.title) for c in record.citations])


def make_answer_block(payload, digest, record, doc):
    if record.evidenceState == 'none' and not payload.source.confirmUncited:
        reject(422, 'AI_UNCITED_CONFIRMATION_REQUIRED', '该AI回答没有可信引用。请明确确认保存为未核实内容。')
    snapshot = answer_snapshot(record, doc)
    return dict(id=payload.operationId, kind='ai_answer', blockSchemaVersion=1, createdAt=iso(now()),
        question=record.question, answer=record.answer,
        answerRef={key:snapshot[key] for key in ('answerId','answerRevision','mode','status','provenance')},
        contextDocument=snapshot['contextDocument'], evidenceState=record.evidenceState,
        citations=snapshot['citations'], historical=payload.source.historical,
        uncitedAcknowledged=record.evidenceState == 'none' and payload.source.confirmUncited,
        requestFingerprint=digest)


def answer_duplicate(db, owner, payload, sources, record):
    block = next((b for b in sources if isinstance(b, dict) and b.get('kind') == 'ai_answer'
        and b.get('answerRef', {}).get('answerId') == record.answerId
        and b.get('answerRef', {}).get('answerRevision') == record.answerRevision), None)
    if block:
        return dict(note=dto(db, owned_note(db, owner, payload.noteId), True), blockId=block['id'],
            created=False, linked=db.get(NoteDocument,(payload.noteId,record.documentId)) is not None,
            replayed=True, deduplicated=True)
    return None


def add_capture_routes(router, current_session, require_csrf):
    @router.get('/capture-config')
    def capture_config(session: LoginSession = Depends(current_session), db: Session = Depends(get_db), resolver=Depends(get_answer_resolver)):
        return {'supportedSourceKinds': ['pdf_excerpt','translation_excerpt'] + (['ai_answer'] if resolver.available else []),
                'aiAnswerCapture': {'available': resolver.available, 'isolatedMock': resolver.isolated_mock}, 'available': schema_available(db), 'formatVersion': 1, 'maxOriginalLength': ORIGINAL_LIMIT,
                'maxTranslatedLength': TRANSLATED_LIMIT, 'maxBlocks': BLOCK_LIMIT, 'maxSourceBytes': SOURCE_BYTES_LIMIT,
                'isolatedTranslationMock': get_settings().app_env == 'test' and os.environ.get('LITERA_ISOLATED_TRANSLATION_MOCK') == '1'}

    @router.get('/answer-preview/{answer_id}')
    def preview_answer(answer_id: UUID, revision: int = Query(ge=1), session: LoginSession = Depends(current_session), db: Session = Depends(get_db), resolver=Depends(get_answer_resolver)):
        source = AiAnswerSource(kind='ai_answer', answerId=str(answer_id), answerRevision=revision)
        record, doc, _ = checked_answer(resolver, db, session.user_id, source)
        return answer_snapshot(record, doc)

    @router.post('/captures', status_code=201)
    def capture(payload: CaptureInput, response: Response, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db), resolver=Depends(get_answer_resolver)):
        ready(db)
        owner, digest = session.user_id, fingerprint(payload)
        replay = existing_capture(db, owner, payload, digest)
        if replay is not None:
            response.status_code = 200
            return replay
        # Authentication and the initial replay lookup are read-only. End their
        # consistent-read snapshot before current locking reads: under MySQL
        # REPEATABLE READ, a refreshed Note alone does not refresh later link DTOs.
        db.rollback()
        answer = None
        if isinstance(payload.source, AiAnswerSource):
            answer, doc, attachment = checked_answer(resolver, db, owner, payload.source)
        else:
            doc, attachment = owned_document(db, owner, payload.source.documentId, lock=True)
        if payload.newNoteTitle is None:
            item = owned_note(db, owner, payload.noteId, lock=True)
            # Another writer may have completed this operation while the lock waited.
            replay = existing_capture(db, owner, payload, digest)
            if replay is not None:
                response.status_code = 200
                return replay
            sources = checked_sources(item)
            duplicate = answer_duplicate(db, owner, payload, sources, answer) if answer else None
            if duplicate:
                response.status_code = 200
                return duplicate
            if item.version != payload.version:
                reject(409, 'NOTE_VERSION_CONFLICT', '笔记已被其他窗口更新，未插入摘录；请重新读取后保存。')
        else:
            item = db.get(Note, payload.noteId)
            if item is not None:
                replay = existing_capture(db, owner, payload, digest)
                if replay is not None:
                    response.status_code = 200
                    return replay
                reject(409, 'NOTE_CREATE_CONFLICT', '此笔记已存在，请重新读取后保存。')
            sources = []
        if len(sources) >= BLOCK_LIMIT:
            reject(422, 'NOTE_CAPTURE_LIMIT', '此笔记的摘录数量已达上限，请选择其他笔记。')
        block = make_answer_block(payload, digest, answer, doc) if answer else make_block(payload, digest, doc, attachment, owner)
        updated_sources = [*sources, block]
        if len(json.dumps(updated_sources, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) > SOURCE_BYTES_LIMIT:
            reject(422, 'NOTE_CAPTURE_LIMIT', '此笔记的来源内容已达上限，请选择其他笔记。')
        timestamp = now()
        created = payload.newNoteTitle is not None
        try:
            if created:
                item = Note(id=payload.noteId, owner_id=owner, title=payload.newNoteTitle, content='',
                            content_format='plain-text', version=1, source_schema_version=1,
                            sources=updated_sources, created_at=timestamp, updated_at=timestamp)
                db.add(item)
                db.flush()
            else:
                result = db.execute(update(Note).where(Note.id == payload.noteId, Note.owner_id == owner, Note.version == payload.version)
                                    .values(sources=updated_sources, version=Note.version + 1, updated_at=timestamp))
                if result.rowcount != 1:
                    db.rollback()
                    replay = existing_capture(db, owner, payload, digest)
                    if replay is not None:
                        response.status_code = 200
                        return replay
                    reject(409, 'NOTE_VERSION_CONFLICT', '笔记已被其他窗口更新，未插入摘录；请重新读取后保存。')
            linked = db.get(NoteDocument, (payload.noteId, doc.id)) is not None
            if payload.associationMode == 'link' and not linked:
                db.add(NoteDocument(note_id=payload.noteId, document_id=doc.id, owner_id=owner, created_at=timestamp))
                linked = True
            db.commit()
            db.refresh(item)
        except IntegrityError:
            db.rollback()
            replay = existing_capture(db, owner, payload, digest)
            if replay is not None:
                response.status_code = 200
                return replay
            reject(409, 'NOTE_CAPTURE_CONFLICT', '笔记或关联状态发生变化，未重复插入，请重新读取。')
        return {'note': dto(db, item, True), 'blockId': block['id'], 'created': created,
                'linked': linked, 'replayed': False}
