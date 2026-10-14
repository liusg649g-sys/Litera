"""Change 01 personal library; no parsing, reader or other module business."""
import logging
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import Field, field_validator
from sqlalchemy import String, cast, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .documents import document_dto, iso, owned_document, reject, storage_path
from .models import CleanupJob, Document, DocumentFile, DocumentTag, Folder, LoginSession, ReadingProgress, Tag
from .schemas import InputModel

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class CategoryInput(InputModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = unicodedata.normalize("NFKC", value).strip()
        if not value or len(value) > 100 or any(unicodedata.category(c).startswith("C") for c in value):
            raise ValueError("名称需要 1–100 个可见字符")
        return value

class TagInput(CategoryInput):
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")

class OpenProgress(InputModel):
    pageNumber: int | None = Field(default=None, ge=1, strict=True)
    zoom: float | None = Field(default=None, gt=0)
    version: int | None = Field(default=None, ge=0, strict=True)

def category_dto(item):
    result = {"id": item.id, "name": item.name}
    if isinstance(item, Tag):
        result["color"] = item.color
    return result

def owned_category(db, model, owner, id, lock=False):
    query = select(model).where(model.id == id, model.owner_id == owner)
    item = db.scalar(query.with_for_update() if lock else query)
    if item is None:
        reject(404, "CATEGORY_NOT_FOUND", "分类不存在或不可访问")
    return item

def validate_classification(db, owner, values):
    if values.get("folderId"):
        owned_category(db, Folder, owner, values["folderId"], lock=True)
    for id in sorted(set(values.get("tagIds") or [])):
        owned_category(db, Tag, owner, id, lock=True)

def document_page(db, owner, request, page, size, sort="createdAt", order="desc", mode="active"):
    params = request.query_params
    allowed = {"page", "pageSize"} if mode == "trash" else {"page", "pageSize", "sort", "order", "q", "folderId", "tagIds", "yearFrom", "yearTo"}
    if set(params) - allowed or any(len(params.getlist(key)) != 1 for key in params):
        reject(422, "INVALID_QUERY", "不支持或重复的查询参数")
    query = select(Document, DocumentFile).join(DocumentFile, DocumentFile.document_id == Document.id).where(
        Document.owner_id == owner, DocumentFile.owner_id == owner,
        Document.deleted_at.is_not(None) if mode == "trash" else Document.deleted_at.is_(None))
    if mode != "trash":
        text = params.get("q", "").strip()
        if len(text) > 500:
            reject(422, "INVALID_QUERY", "检索词最多 500 字符")
        if text:
            escaped = text.replace("!", "!!").replace("%", "!%").replace("_", "!_")
            pattern = "%" + escaped + "%"
            matches = [cast(column, String).ilike(pattern, escape="!") for column in
                (Document.title, Document.abstract, Document.doi, Document.journal)]
            for column in (Document.authors, Document.keywords):
                if db.bind.dialect.name == "sqlite":
                    elements = func.json_each(column).table_valued("value")
                    matches.append(select(elements.c.value).where(elements.c.value.ilike(pattern, escape="!")).correlate(Document).exists())
                else:
                    matches.append(cast(column, String).ilike(pattern, escape="!"))
            query = query.where(or_(*matches))
        if params.get("folderId"):
            owned_category(db, Folder, owner, params["folderId"])
            query = query.where(Document.folder_id == params["folderId"])
        ids = params.get("tagIds", "")
        if ids:
            ids = ids.split(",")
            if len(ids) > 100 or any(not id or len(id) > 36 for id in ids):
                reject(422, "INVALID_QUERY", "标签 ID 格式无效")
            for id in sorted(set(ids)):
                owned_category(db, Tag, owner, id)
                query = query.where(select(DocumentTag.document_id).where(
                    DocumentTag.document_id == Document.id, DocumentTag.owner_id == owner, DocumentTag.tag_id == id).exists())
        years = {}
        for key in ("yearFrom", "yearTo"):
            if key in params:
                if not re.fullmatch(r"[0-9]{1,4}", params[key]) or not 1 <= int(params[key]) <= 9999:
                    reject(422, "INVALID_QUERY", "年份必须是 1–9999 的整数")
                years[key] = int(params[key])
        if years.get("yearFrom", 1) > years.get("yearTo", 9999):
            reject(422, "INVALID_QUERY", "起始年份不能晚于结束年份")
        if "yearFrom" in years:
            query = query.where(Document.year >= years["yearFrom"])
        if "yearTo" in years:
            query = query.where(Document.year <= years["yearTo"])
    if mode == "recent":
        query = query.where(Document.last_read_at.is_not(None))
        column, order = Document.last_read_at, "desc"
    elif mode == "trash":
        column, order = Document.deleted_at, "desc"
    else:
        column = {"title": Document.title, "year": Document.year, "createdAt": Document.created_at, "lastReadAt": Document.last_read_at}[sort]
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(column.is_(None), column.asc() if order == "asc" else column.desc(), Document.id)
        .offset((page - 1) * size).limit(size)).all()
    items = [document_dto(doc, file, db) for doc, file in rows]
    if mode == "recent":
        items = [{"document": item, "progress": progress_dto(db.scalar(select(ReadingProgress).where(
            ReadingProgress.document_id == item["id"], ReadingProgress.owner_id == owner)), item["id"])} for item in items]
    return {"items": items, "page": page, "pageSize": size, "total": total}

def progress_dto(item, id):
    return {"documentId": id, "pageNumber": item.page_number if item else None,
        "zoom": float(item.zoom) if item and item.zoom else None,
        "lastReadAt": iso(item.last_read_at) if item else None, "version": item.version if item else 0}

def job_dto(job):
    return {"jobId": job.id, "documentId": job.document_id, "status": job.status,
        "errorCode": job.error_code, "attempts": job.attempts, "updatedAt": iso(job.updated_at)}

def owned_job(db, owner, id):
    job = db.scalar(select(CleanupJob).where(CleanupJob.id == id, CleanupJob.owner_id == owner))
    if job is None:
        reject(404, "CLEANUP_NOT_FOUND", "清理作业不存在或不可访问")
    return job

def run_cleanup(db, job):
    """Persist intent before touching the file; CAS claim makes retries restart-safe."""
    if job.status == "completed":
        return Response(status_code=204)
    timestamp = now()
    claimed = db.execute(update(CleanupJob).where(CleanupJob.id == job.id, CleanupJob.owner_id == job.owner_id,
        or_(CleanupJob.status.in_(["pending", "failed"]),
            (CleanupJob.status == "running") & (CleanupJob.lease_expires_at <= timestamp)))
        .values(status="running", attempts=CleanupJob.attempts + 1, error_code=None,
                lease_expires_at=timestamp + timedelta(seconds=60), updated_at=timestamp))
    db.commit()
    db.expire_all()
    job = db.get(CleanupJob, job.id)
    if claimed.rowcount != 1:
        return Response(status_code=204) if job.status == "completed" else job_response(job)
    attempt = job.attempts
    try:
        # Hold the job row write lock through file removal + DB cleanup. A lease
        # expiring during a slow filesystem operation cannot start a second worker.
        fenced = db.execute(update(CleanupJob).where(CleanupJob.id == job.id, CleanupJob.status == "running",
            CleanupJob.attempts == attempt).values(updated_at=now()))
        if fenced.rowcount != 1:
            db.rollback(); db.expire_all(); job = db.get(CleanupJob, job.id)
            return Response(status_code=204) if job.status == "completed" else job_response(job)
        # A missing file after an interrupted cleanup counts as already removed.
        storage_path(job.storage_key).unlink(missing_ok=True)
        db.execute(delete(DocumentTag).where(DocumentTag.document_id == job.document_id, DocumentTag.owner_id == job.owner_id))
        db.execute(delete(ReadingProgress).where(ReadingProgress.document_id == job.document_id, ReadingProgress.owner_id == job.owner_id))
        db.execute(delete(DocumentFile).where(DocumentFile.document_id == job.document_id, DocumentFile.owner_id == job.owner_id))
        db.execute(delete(Document).where(Document.id == job.document_id, Document.owner_id == job.owner_id, Document.purge_job_id == job.id))
        job.status = "completed"; job.storage_key = None; job.lease_expires_at = None; job.updated_at = now()
        db.commit()
        return Response(status_code=204)
    except Exception:
        db.rollback()
        logging.exception("PDF cleanup failed for job %s", job.id)
        db.execute(update(CleanupJob).where(CleanupJob.id == job.id, CleanupJob.status == "running", CleanupJob.attempts == attempt)
            .values(status="failed", error_code="CLEANUP_FAILED", lease_expires_at=None, updated_at=now()))
        db.commit()
        db.expire_all(); job = db.get(CleanupJob, job.id)
        if job.status == "completed":
            return Response(status_code=204)
        return job_response(job)

def job_response(job):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=202, content=job_dto(job))

def create_library_router(current_session, require_csrf):
    router = APIRouter(tags=["library"])

    def register_categories(model, path, schema):
        def listing(session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
            return [category_dto(row) for row in db.scalars(select(model).where(model.owner_id == session.user_id).order_by(model.name, model.id))]
        def writing(payload, session, db, id=None):
            item = owned_category(db, model, session.user_id, id, True) if id else model(
                id=str(uuid.uuid4()), owner_id=session.user_id, created_at=now())
            item.name = payload.name; item.normalized_name = payload.name.casefold(); item.updated_at = now()
            if model is Tag and (not id or "color" in payload.model_fields_set):
                item.color = payload.color
            db.add(item)
            try:
                db.commit()
            except IntegrityError:
                db.rollback(); reject(409, "CATEGORY_NAME_EXISTS", "你已使用这个分类名称")
            return category_dto(item)
        def creating(payload, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
            return writing(payload, session, db)
        def editing(id: str, payload, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
            return writing(payload, session, db, id)
        # FastAPI reads annotations at registration; use the exact DTO for each category.
        creating.__annotations__["payload"] = schema
        editing.__annotations__["payload"] = schema
        def removing(id: str, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
            item = owned_category(db, model, session.user_id, id, True)
            if model is Folder:
                db.execute(update(Document).where(Document.owner_id == session.user_id, Document.folder_id == id)
                    .values(folder_id=None, version=Document.version + 1, updated_at=now()))
            else:
                associated = select(DocumentTag.document_id).where(DocumentTag.owner_id == session.user_id, DocumentTag.tag_id == id)
                db.execute(update(Document).where(Document.owner_id == session.user_id, Document.id.in_(associated))
                    .values(version=Document.version + 1, updated_at=now()))
                db.execute(delete(DocumentTag).where(DocumentTag.owner_id == session.user_id, DocumentTag.tag_id == id))
            db.delete(item); db.commit()
            return Response(status_code=204)
        router.add_api_route(path, listing, methods=["GET"], name=f"list_{model.__tablename__}")
        router.add_api_route(path, creating, methods=["POST"], status_code=201, name=f"create_{model.__tablename__}")
        router.add_api_route(path + "/{id}", editing, methods=["PATCH"], name=f"edit_{model.__tablename__}")
        router.add_api_route(path + "/{id}", removing, methods=["DELETE"], name=f"delete_{model.__tablename__}")
    register_categories(Folder, "/folders", CategoryInput)
    register_categories(Tag, "/tags", TagInput)

    @router.get("/documents/{id}/progress")
    def progress(id: str, session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        owned_document(db, session.user_id, id)
        return progress_dto(db.scalar(select(ReadingProgress).where(ReadingProgress.document_id == id, ReadingProgress.owner_id == session.user_id)), id)

    @router.put("/documents/{id}/progress")
    def opened(id: str, payload: OpenProgress, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        if payload.pageNumber is not None or payload.zoom is not None:
            reject(503, "READER_NOT_READY", "实际页码与缩放将在在线阅读器开放")
        _, file = owned_document(db, session.user_id, id)
        if not storage_path(file.storage_key).is_file():
            reject(404, "PDF_NOT_FOUND", "PDF 文件暂不可用")
        # Updating the document serializes concurrent first opens on MySQL and SQLite.
        timestamp = now()
        result = db.execute(update(Document).where(Document.id == id, Document.owner_id == session.user_id, Document.deleted_at.is_(None))
            .values(last_read_at=timestamp))
        if result.rowcount != 1:
            db.rollback(); reject(404, "DOCUMENT_NOT_FOUND", "文献不存在或不可访问")
        item = db.scalar(select(ReadingProgress).where(ReadingProgress.document_id == id, ReadingProgress.owner_id == session.user_id))
        if payload.version is not None and payload.version != (item.version if item else 0):
            db.rollback(); reject(409, "VERSION_CONFLICT", "阅读记录已更新，请重新读取")
        if item is None:
            item = ReadingProgress(document_id=id, owner_id=session.user_id, version=0)
            db.add(item)
        item.last_read_at = timestamp; item.version += 1
        db.commit()
        return progress_dto(item, id)

    @router.get("/reading-history")
    def history(request: Request, page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                sort: Literal["title", "year", "createdAt", "lastReadAt"] = "lastReadAt", order: Literal["asc", "desc"] = "desc",
                session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        return document_page(db, session.user_id, request, page, pageSize, sort, order, "recent")

    @router.delete("/documents/{id}")
    def soft_delete(id: str, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        doc = db.scalar(select(Document).where(Document.id == id, Document.owner_id == session.user_id).with_for_update())
        if doc is None:
            reject(404, "DOCUMENT_NOT_FOUND", "文献不存在或不可访问")
        if doc.deleted_at is None:
            doc.deleted_at = now(); doc.updated_at = now(); doc.version += 1
        db.commit()
        return Response(status_code=204)

    @router.get("/trash/documents")
    def trash(request: Request, page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
              session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        return document_page(db, session.user_id, request, page, pageSize, mode="trash")

    @router.post("/trash/documents/{id}/restore")
    def restore(id: str, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        doc, file = owned_document(db, session.user_id, id, trash=True, lock=True)
        result = db.execute(update(Document).where(Document.id == id, Document.owner_id == session.user_id,
            Document.deleted_at.is_not(None), Document.purge_job_id.is_(None))
            .values(deleted_at=None, version=Document.version + 1, updated_at=now()))
        if result.rowcount != 1:
            db.rollback(); reject(409, "PURGE_STARTED", "永久清理已开始，不能恢复；可查看状态并重试清理")
        db.commit(); db.expire_all()
        return document_dto(*owned_document(db, session.user_id, id), db)

    @router.delete("/trash/documents/{id}")
    def purge(id: str, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        doc, file = owned_document(db, session.user_id, id, trash=True, lock=True)
        if doc.purge_job_id:
            return run_cleanup(db, owned_job(db, session.user_id, doc.purge_job_id))
        job_id = str(uuid.uuid4())
        result = db.execute(update(Document).where(Document.id == id, Document.owner_id == session.user_id,
            Document.deleted_at.is_not(None), Document.purge_job_id.is_(None)).values(purge_job_id=job_id))
        if result.rowcount != 1:
            db.rollback(); db.expire_all()
            doc, _ = owned_document(db, session.user_id, id, trash=True)
            if not doc.purge_job_id:
                reject(409, "DOCUMENT_STATE_CHANGED", "文献状态已变化，请刷新")
            return run_cleanup(db, owned_job(db, session.user_id, doc.purge_job_id))
        job = CleanupJob(id=job_id, owner_id=session.user_id, document_id=id, storage_key=file.storage_key,
            status="pending", attempts=0, created_at=now(), updated_at=now())
        db.add(job); db.commit()
        return run_cleanup(db, job)

    @router.get("/cleanup-jobs/{id}")
    def job_status(id: str, session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        return job_dto(owned_job(db, session.user_id, id))

    @router.post("/cleanup-jobs/{id}/retry")
    def retry(id: str, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        return run_cleanup(db, owned_job(db, session.user_id, id))

    return router
