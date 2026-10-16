"""Private, decoded PNG/JPEG assets with durable cleanup intent and leases."""
import hashlib
import io
import re
from .config import get_settings
import logging
import uuid
import warnings
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from PIL import Image, ImageOps
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile
from starlette.concurrency import run_in_threadpool
from .database import get_db, SessionLocal
from .documents import owned_document, reject
from .models import Annotation, Document, ReaderAsset, LoginSession

def asset_storage_path(key):
    if not re.fullmatch(r"asset-[0-9a-f-]{36}\.(png|jpg)", key):
        raise ValueError("Invalid internal asset key")
    return get_settings().pdf_storage_root.resolve() / key
MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 20_000_000
MAX_DOCUMENT_BYTES = 50 * 1024 * 1024

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def asset_dto(row):
    return dict(assetId=row.id, mimeType=row.mime_type, width=row.width, height=row.height,
                sizeBytes=row.size_bytes, status=row.status, attempts=row.attempts, errorCode=row.error_code)

def lock_document(db, owner, id):
    result = db.execute(update(Document).where(Document.id == id, Document.owner_id == owner,
        Document.deleted_at.is_(None), Document.purge_job_id.is_(None)).values(version=Document.version))
    if result.rowcount != 1:
        reject(404, "DOCUMENT_NOT_FOUND", "文献不存在或不可访问")

def owned_asset(db, owner, document_id, asset_id):
    row = db.scalar(select(ReaderAsset).where(ReaderAsset.id == asset_id, ReaderAsset.owner_id == owner,
        ReaderAsset.document_id == document_id).with_for_update())
    if row is None:
        reject(404, "ASSET_NOT_FOUND", "图片资产不存在或不可访问")
    return row

def validate_asset(db, owner, document_id, asset_id):
    row = owned_asset(db, owner, document_id, asset_id)
    if row.status != "ready" or (row.expires_at and row.expires_at <= now()) or not asset_storage_path(row.storage_key).is_file():
        reject(422, "ASSET_UNAVAILABLE", "图片资产已失效，请重新上传；原草稿已保留")
    return row

def cleanup_asset(db, row):
    """Caller holds document lock; commit intent before deleting bytes, retry missing files."""
    if row.status == "deleted":
        return True
    row.status = "cleaning"; row.attempts += 1; row.error_code = None
    db.commit()
    try:
        asset_storage_path(row.storage_key).unlink(missing_ok=True)
        row.status = "deleted"; row.error_code = None
        db.commit()
        return True
    except OSError:
        row.status = "failed"; row.error_code = "ASSET_CLEANUP_FAILED"; db.commit()
        return False

def sweep_assets():
    # Startup + periodic scan. Each candidate is rechecked under the same document
    # lock as annotation commands, so attach/restore cannot race with collection.
    with SessionLocal() as db:
        candidates = db.scalars(select(ReaderAsset.id).where(ReaderAsset.status != "deleted",
            ReaderAsset.expires_at <= now())).all()
    for asset_id in candidates:
        try:
            with SessionLocal() as db:
                candidate = db.get(ReaderAsset, asset_id)
                if not candidate:
                    continue
                doc = db.scalar(select(Document).where(Document.id == candidate.document_id).with_for_update())
                if not doc or doc.purge_job_id:
                    continue  # document cleanup job owns these files
                locked = db.execute(update(Document).where(Document.id == doc.id, Document.purge_job_id.is_(None)).values(version=Document.version))
                if locked.rowcount != 1:
                    continue
                db.refresh(candidate, with_for_update=True)
                if not candidate.expires_at or candidate.expires_at > now():
                    continue
                active = db.scalar(select(Annotation.id).where(Annotation.asset_id == asset_id, Annotation.deleted_at.is_(None)))
                if active:
                    candidate.expires_at = None; db.commit(); continue
                cleanup_asset(db, candidate)
        except Exception:
            logging.exception("Reader asset sweep failed: %s", asset_id)

def decode(raw):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in ("PNG", "JPEG") or getattr(source, "n_frames", 1) != 1:
                    raise ValueError()
                w, h = source.size
                if w < 1 or h < 1 or w > 16384 or h > 16384 or w*h > MAX_PIXELS:
                    reject(422, "IMAGE_DIMENSIONS", "图片须不超过20M像素，单边不超过16384像素")
                source.verify()
            with Image.open(io.BytesIO(raw)) as source:
                source.load()  # verify alone does not decode JPEG pixels
                image = ImageOps.exif_transpose(source).convert("RGBA" if source.format == "PNG" else "RGB")
                output = io.BytesIO(); fmt = "PNG" if source.format == "PNG" else "JPEG"
                image.save(output, format=fmt)
                encoded = output.getvalue()
                if len(encoded) > MAX_BYTES:
                    reject(413, "ASSET_TOO_LARGE", "规范化后的图片超过5MiB")
                return encoded, image.width, image.height, fmt
    except (Image.DecompressionBombWarning, Image.DecompressionBombError):
        reject(422, "IMAGE_DIMENSIONS", "图片解码尺寸过大")
    except (OSError, ValueError, SyntaxError):
        reject(415, "INVALID_IMAGE", "请选择可完整解码的 PNG/JPEG 图片")

def create_asset_router(current_session, require_csrf):
    router = APIRouter(prefix="/api/v1/documents/{id}/reader-assets", tags=["reader-assets"])

    @router.post("", status_code=201)
    async def upload(id: str, request: Request, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        owned_document(db, session.user_id, id)
        async with request.form(max_files=1, max_fields=0, max_part_size=MAX_BYTES) as form:
            fields = list(form.multi_items())
            if len(fields) != 1 or fields[0][0] != "file" or not isinstance(fields[0][1], UploadFile):
                reject(422, "INVALID_UPLOAD", "仅接受一个file图片字段")
            raw = await fields[0][1].read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES:
            reject(413, "ASSET_TOO_LARGE", "单张图片不能超过5MiB")
        encoded, width, height, fmt = await run_in_threadpool(decode, raw)
        lock_document(db, session.user_id, id)
        total = db.scalar(select(func.coalesce(func.sum(ReaderAsset.size_bytes), 0)).where(
            ReaderAsset.document_id == id, ReaderAsset.status != "deleted"))
        if total + len(encoded) > MAX_DOCUMENT_BYTES:
            reject(413, "ASSET_DOCUMENT_LIMIT", "本篇图片资产已达50MiB，请清理未引用图片后重试")
        asset_id = str(uuid.uuid4())
        row = ReaderAsset(id=asset_id, owner_id=session.user_id, document_id=id,
            storage_key="asset-"+asset_id+(".png" if fmt == "PNG" else ".jpg"),
            sha256=hashlib.sha256(encoded).hexdigest(),
            mime_type="image/png" if fmt == "PNG" else "image/jpeg", width=width, height=height,
            size_bytes=len(encoded), status="uploading", attempts=0, created_at=now(), expires_at=now()+timedelta(hours=1))
        db.add(row); db.commit()  # durable ledger precedes file creation
        try:
            # Reacquire document lock after ledger commit; purge may have started.
            lock_document(db, session.user_id, id)
            db.refresh(row, with_for_update=True)
            if row.status != "uploading":
                reject(409, "ASSET_UPLOAD_CANCELED", "图片上传已被清理，请重新选择图片")
            target = asset_storage_path(row.storage_key); target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(encoded)
            row.status = "ready"; db.commit()
        except Exception:
            db.rollback()
            # Leave durable uploading intent for startup/periodic cleanup.
            raise
        return asset_dto(row)

    @router.get("")
    def listing(id: str, session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        owned_document(db, session.user_id, id)
        return {"items": [asset_dto(a) for a in db.scalars(select(ReaderAsset).where(
            ReaderAsset.document_id == id, ReaderAsset.owner_id == session.user_id, ReaderAsset.status != "deleted"))]}

    @router.get("/{asset_id}/content")
    def content(id: str, asset_id: str, session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        owned_document(db, session.user_id, id)
        row = validate_asset(db, session.user_id, id, asset_id)
        return FileResponse(asset_storage_path(row.storage_key), media_type=row.mime_type,
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})

    @router.delete("/{asset_id}")
    def remove(id: str, asset_id: str, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        lock_document(db, session.user_id, id)
        row = owned_asset(db, session.user_id, id, asset_id)
        if db.scalar(select(Annotation.id).where(Annotation.asset_id == asset_id, Annotation.deleted_at.is_(None))) or (db.scalar(select(Annotation.id).where(Annotation.asset_id == asset_id)) and (row.expires_at is None or row.expires_at > now())):
            reject(409, "ASSET_REFERENCED", "图片仍由对象或撤销快照引用，按24小时租约回收")
        if cleanup_asset(db, row):
            return Response(status_code=204)
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=202, content=asset_dto(row))
    return router
