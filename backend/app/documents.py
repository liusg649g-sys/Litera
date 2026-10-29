"""P2-A document API. Files never have a public/static storage URL."""
import hashlib
import logging
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import Field, field_validator, model_validator
from pypdf import PdfReader
from sqlalchemy import func, select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException

from .config import get_settings
from .database import get_db
from .models import Document, DocumentFile, LoginSession, Tag, DocumentTag, CleanupJob
from .schemas import InputModel

settings = get_settings()

def reject(status, code, message, details=None, headers=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    raise HTTPException(status, detail=error, headers=headers)

class UploadTooLarge(MultiPartException):
    def __init__(self):
        super().__init__("UPLOAD_TOO_LARGE")

class UploadLimitMiddleware:
    """Bound the entire multipart stream before Starlette can spool it to disk."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "POST" and (scope["path"] == "/api/v1/documents" or scope["path"].endswith("/reader-assets")):
            total = 0
            async def limited_receive():
                nonlocal total
                message = await receive()
                if message["type"] == "http.request":
                    total += len(message.get("body", b""))
                    if total > (5 * 1024 * 1024 if scope["path"].endswith("/reader-assets") else settings.max_upload_bytes) + 65536:
                        scope.setdefault("state", {})["upload_too_large"] = True
                        scope["state"]["upload_limit"] = 5 * 1024 * 1024 if scope["path"].endswith("/reader-assets") else settings.max_upload_bytes
                        raise UploadTooLarge()
                return message
            await self.app(scope, limited_receive, send)
        else:
            await self.app(scope, receive, send)

class DocumentPatch(InputModel):
    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    authors: list[Annotated[str, Field(min_length=1, max_length=200)]] | None = Field(default=None, max_length=100)
    abstract: str | None = Field(default=None, max_length=50000)
    keywords: list[Annotated[str, Field(min_length=1, max_length=100)]] | None = Field(default=None, max_length=100)
    year: int | None = Field(default=None, ge=1, le=9999, strict=True)
    journal: str | None = Field(default=None, max_length=500)
    doi: str | None = Field(default=None, max_length=255)
    folderId: str | None = Field(default=None, min_length=1, max_length=36)
    tagIds: list[Annotated[str, Field(min_length=1, max_length=36)]] | None = Field(default=None, max_length=100)

    @field_validator("title", "abstract", "journal", "doi")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if value is not None else None

    @field_validator("authors", "keywords")
    @classmethod
    def trim_list(cls, value):
        if value is not None:
            value = [item.strip() for item in value]
            if any(not item for item in value):
                raise ValueError("列表项不能为空")
        return value

    @model_validator(mode="after")
    def required_title(self):
        if "title" in self.model_fields_set and not self.title:
            raise ValueError("标题不能为空")
        return self

def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None

def document_dto(doc, attachment, db=None):
    tags = db.scalars(select(Tag).join(DocumentTag, DocumentTag.tag_id == Tag.id).where(
        DocumentTag.document_id == doc.id, DocumentTag.owner_id == doc.owner_id,
        Tag.owner_id == doc.owner_id).order_by(Tag.name, Tag.id)).all() if db else []
    job = db.scalar(select(CleanupJob).where(CleanupJob.id == doc.purge_job_id, CleanupJob.owner_id == doc.owner_id)) if db and doc.purge_job_id else None
    return {
        "id": doc.id, "title": doc.title, "authors": doc.authors, "abstract": doc.abstract,
        "keywords": doc.keywords, "year": doc.year, "journal": doc.journal, "doi": doc.doi,
        "folderId": doc.folder_id, "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in tags],
        "cleanupJob": {"jobId": job.id, "status": job.status, "errorCode": job.error_code} if job else None,
        "attachment": {"originalName": attachment.original_name, "sizeBytes": attachment.size_bytes,
                       "mimeType": attachment.mime_type, "sha256": attachment.sha256},
        "parseStatus": doc.parse_status, "extractionVersion": doc.extraction_version,
        "pageCount": doc.page_count, "version": doc.version,
        "createdAt": iso(doc.created_at), "updatedAt": iso(doc.updated_at),
        "lastReadAt": iso(doc.last_read_at), "deletedAt": iso(doc.deleted_at),
    }

def owned_document(db, owner_id, document_id, trash=False, lock=False):
    query = select(Document, DocumentFile).join(DocumentFile, DocumentFile.document_id == Document.id).where(
        Document.id == document_id, Document.owner_id == owner_id, DocumentFile.owner_id == owner_id,
        Document.deleted_at.is_not(None) if trash else Document.deleted_at.is_(None))
    result = db.execute(query.with_for_update() if lock else query).first()
    if result is None:
        reject(404, "DOCUMENT_NOT_FOUND", "文献不存在或不可访问")
    return result

def duplicate(db, owner_id, digest):
    return db.execute(select(Document.id, Document.deleted_at).join(DocumentFile, DocumentFile.document_id == Document.id)
        .where(DocumentFile.owner_id == owner_id, Document.owner_id == owner_id, DocumentFile.sha256 == digest)).first()

def reject_duplicate(existing):
    reject(409, "DUPLICATE_DOCUMENT", "该 PDF 已在你的文献库中" if existing.deleted_at is None else "该 PDF 已在回收站中，请恢复或完成永久删除后上传",
           {"existingDocumentId": existing.id, "inTrash": existing.deleted_at is not None})

def storage_path(key):
    root = settings.pdf_storage_root.resolve()
    path = (root / key).resolve()
    if path.parent != root or not re.fullmatch(r"[0-9a-f-]{36}\.pdf", key):
        raise ValueError("Invalid internal storage key")
    return path

def validate_pdf(path):
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            reject(415, "INVALID_PDF", "文件内容不是有效 PDF")
        stream.seek(0)
        try:
            reader = PdfReader(stream)
            # No text/metadata extraction. Encrypted files have no password flow in P2-A.
            if reader.is_encrypted:
                reject(415, "ENCRYPTED_PDF", "暂不支持加密 PDF，请先解密后上传")
            if len(reader.pages) < 1:
                reject(415, "INVALID_PDF", "PDF 至少需要一页")
        except HTTPException:
            raise
        except Exception:
            reject(415, "INVALID_PDF", "PDF 结构损坏或不受支持，请检查文件")

def save_upload(file, owner_id, db, folder_id=None):
    from .library import owned_category
    from .models import Folder
    if folder_id:
        owned_category(db, Folder, owner_id, folder_id, lock=True)
    original_name = (file.filename or "document.pdf").replace("\\", "/").rsplit("/", 1)[-1]
    original_name = "".join(c for c in original_name if ord(c) >= 32 and ord(c) != 127).strip()[:255] or "document.pdf"
    if not original_name.lower().endswith(".pdf"):
        reject(415, "INVALID_PDF", "仅支持本地 PDF 文件")
    root = settings.pdf_storage_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    temporary = None
    published = None
    document_id = str(uuid.uuid4())
    digest = hashlib.sha256()
    try:
        with tempfile.NamedTemporaryFile(prefix="upload-", suffix=".tmp", dir=root, delete=False) as output:
            temporary = Path(output.name)
            size = 0
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    reject(413, "UPLOAD_TOO_LARGE", "PDF 超过上传大小限制", {"maxUploadBytes": settings.max_upload_bytes})
                output.write(chunk)
                digest.update(chunk)
            output.flush()
            os.fsync(output.fileno())
        validate_pdf(temporary)
        existing = duplicate(db, owner_id, digest.hexdigest())
        if existing:
            reject_duplicate(existing)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        doc = Document(id=document_id, owner_id=owner_id, title=original_name[:-4].strip() or "未命名文献",
            authors=[], keywords=[], version=1, parse_status="not_requested", created_at=now, updated_at=now, folder_id=folder_id)
        attachment = DocumentFile(id=str(uuid.uuid4()), document_id=doc.id, owner_id=owner_id,
            original_name=original_name, storage_key=document_id + ".pdf", sha256=digest.hexdigest(),
            size_bytes=size, mime_type="application/pdf")
        db.add(doc)
        db.flush()
        db.add(attachment)
        # The unique constraint serializes concurrent same-user hashes before publication.
        db.flush()
        published = storage_path(attachment.storage_key)
        os.replace(temporary, published)
        db.commit()
        # ── 自动提取同步层（Layer 1 + Layer 2） ────────────────
        extraction_version = None
        extraction_candidates = {}
        try:
            import io
            from .metadata_extraction import run_sync_layers
            from .extraction import create_extraction_job, persist_extraction
            from pypdf import PdfReader
            pdf_bytes = published.read_bytes()
            reader = PdfReader(io.BytesIO(pdf_bytes))
            layer1, layer2, page_texts, _ = run_sync_layers(reader)
            file_hash = attachment.sha256
            db.expire_all()
            doc_refreshed = db.get(Document, document_id)
            job = create_extraction_job(db, owner_id, document_id, file_hash)
            merged = persist_extraction(db, job, doc_refreshed, layer1, layer2, page_texts)
            extraction_version = job.version_id
            extraction_candidates = merged.get("metadata", {})
        except Exception as exc:
            logging.warning("Sync extraction layers failed for %s: %s", document_id, exc)
        # ── 自动提取结束 ────────────────────────────────────────
        # Return database-normalized timestamps (MySQL DATETIME has second precision).
        db.refresh(doc)
        dto = document_dto(doc, attachment, db)
        # 在 dto 里补充提取相关字段（extraction_version 会在 persist_extraction 里更新 doc）
        if extraction_version:
            doc = db.get(Document, document_id)
            if doc:
                dto["extractionVersion"] = doc.extraction_version or extraction_version
                dto["parseStatus"] = doc.parse_status or "processing"
        return dto, extraction_version
    except Exception as error:
        db.rollback()
        if published and published.exists():
            # If commit acknowledgement was lost, never delete a committed row's PDF.
            try:
                committed = db.get(Document, document_id)
                if committed is None:
                    published.unlink()
            except Exception:
                logging.exception("Upload compensation needs reconciliation: %s", document_id)
        if isinstance(error, IntegrityError):
            existing = duplicate(db, owner_id, digest.hexdigest())
            if existing:
                reject_duplicate(existing)
        raise
    finally:
        if temporary and temporary.exists():
            temporary.unlink()

def create_document_router(current_session, require_csrf):
    from .library import create_library_router, document_page, validate_classification
    router = APIRouter(prefix="/api/v1", tags=["documents"])

    @router.get("/library/config")
    def library_config(session: LoginSession = Depends(current_session)):
        return {"maxUploadBytes": settings.max_upload_bytes}

    @router.post("/documents", status_code=201, openapi_extra={"requestBody": {
        "required": True, "content": {"multipart/form-data": {"schema": {
            "type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary"}, "folderId": {"type": "string", "maxLength": 36}}}}}}})
    async def upload(request: Request, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
            reject(415, "MULTIPART_REQUIRED", "请使用 multipart 上传 PDF")
        async with request.form(max_files=1, max_fields=1, max_part_size=65536) as form:
            if set(form) - {"file", "folderId"} or len(form.getlist("file")) != 1 or not isinstance(form.get("file"), UploadFile):
                reject(422, "INVALID_UPLOAD", "需要且仅允许一个 file 文件字段")
            folder_id = form.get("folderId")
            if folder_id is not None and (not isinstance(folder_id, str) or not folder_id or len(folder_id) > 36 or len(form.getlist("folderId")) != 1):
                reject(422, "INVALID_UPLOAD", "folderId 必须是文件夹 ID")
            dto, extraction_version = await run_in_threadpool(save_upload, form["file"], session.user_id, db, folder_id)
            # 触发异步 Layer 3
            if dto.get("extractionVersion"):
                import asyncio
                from .extraction import run_layer3_async
                asyncio.create_task(run_layer3_async(dto["id"], session.user_id))
            return dto

    @router.get("/documents")
    def list_documents(request: Request, page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                       sort: Literal["title", "year", "createdAt", "lastReadAt"] = "createdAt", order: Literal["asc", "desc"] = "desc",
                       session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        return document_page(db, session.user_id, request, page, pageSize, sort, order)

    @router.get("/documents/{document_id}")
    def detail(document_id: str, session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        return document_dto(*owned_document(db, session.user_id, document_id), db)

    @router.patch("/documents/{document_id}")
    def edit(document_id: str, payload: DocumentPatch, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        owned_document(db, session.user_id, document_id)
        values = payload.model_dump(exclude_unset=True, exclude={"version"})
        validate_classification(db, session.user_id, values)
        tag_ids = values.pop("tagIds", None)
        if "folderId" in values:
            values["folder_id"] = values.pop("folderId")
        # null clears optional values; arrays are represented as [], never JSON null.
        for key in ("authors", "keywords"):
            if key in values and values[key] is None:
                values[key] = []
        values.update(version=Document.version + 1, updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
        result = db.execute(update(Document).where(Document.id == document_id, Document.owner_id == session.user_id,
            Document.deleted_at.is_(None), Document.version == payload.version).values(**values))
        if result.rowcount != 1:
            db.rollback()
            reject(409, "VERSION_CONFLICT", "文献已被更新，请重新载入后再编辑")
        if "tagIds" in payload.model_fields_set:
            db.execute(delete(DocumentTag).where(DocumentTag.document_id == document_id, DocumentTag.owner_id == session.user_id))
            db.add_all([DocumentTag(document_id=document_id, tag_id=id, owner_id=session.user_id) for id in sorted(set(tag_ids or []))])
        db.commit()
        db.expire_all()
        return document_dto(*owned_document(db, session.user_id, document_id), db)

    @router.get("/documents/{document_id}/content")
    def content(document_id: str, request: Request, download: bool = False,
                session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        _, attachment = owned_document(db, session.user_id, document_id)
        path = storage_path(attachment.storage_key)
        if not path.is_file():
            reject(404, "PDF_NOT_FOUND", "PDF 文件暂不可用")
        size = path.stat().st_size
        start, end = 0, size - 1
        status = 200
        headers = {"Accept-Ranges": "bytes", "Content-Disposition":
            ("attachment" if download else "inline") + "; filename*=UTF-8''" + quote(attachment.original_name, safe=""),
            "X-Content-Type-Options": "nosniff"}
        requested_range = request.headers.get("range")
        if requested_range:
            match = re.fullmatch(r"bytes=(\d{0,20})-(\d{0,20})", requested_range.strip())
            valid = match is not None and any(match.groups())
            if valid:
                first, last = match.groups()
                if first:
                    start = int(first)
                    end = min(int(last), size - 1) if last else size - 1
                else:
                    suffix = int(last)
                    start = max(0, size - suffix)
                    valid = suffix > 0
                valid = valid and 0 <= start <= end < size
            if not valid:
                reject(416, "INVALID_RANGE", "请求的 PDF 字节范围不可用", headers={"Content-Range": f"bytes */{size}"})
            status = 206
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        headers["Content-Length"] = str(end - start + 1)
        def chunks():
            with path.open("rb") as stream:
                stream.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = stream.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        return StreamingResponse(chunks(), status_code=status, media_type="application/pdf", headers=headers)

    router.include_router(create_library_router(current_session, require_csrf))
    return router
