"""Private B1 annotations; one transaction owns object, collection CAS and receipt."""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import Field, TypeAdapter, ValidationError, field_validator, model_validator
from pypdf import PdfReader
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from .database import get_db
from .documents import iso, owned_document, reject, storage_path
from .models import Annotation, AnnotationCommandReceipt, Document, DocumentReaderState, LoginSession
from .schemas import InputModel

Number = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
Page = Annotated[int, Field(strict=True, ge=1)]
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]


class Rect(InputModel):
    x: Number
    y: Number
    width: Annotated[float, Field(strict=True, gt=0, le=1, allow_inf_nan=False)]
    height: Annotated[float, Field(strict=True, gt=0, le=1, allow_inf_nan=False)]
    baseline: Number | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def bounds(self):
        if self.x + self.width > 1.00000001 or self.y + self.height > 1.00000001:
            raise ValueError("矩形越出页面")
        return self


class TextRange(InputModel):
    item: int = Field(ge=0, strict=True)
    start: int = Field(ge=0, strict=True)
    end: int = Field(gt=0, strict=True)

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("字符范围为空或倒置")
        return self


class Position(InputModel):
    pageNumber: Page
    rects: list[Rect] = Field(min_length=1, max_length=2000)
    textQuote: str = Field(min_length=1, max_length=20000)
    textRanges: list[TextRange] | None = Field(default=None, max_length=2000, exclude_if=lambda value: value is None)


class TextGeometry(InputModel):
    kind: Literal["text"]
    positions: list[Position] = Field(min_length=1, max_length=500)


class BoxGeometry(InputModel):
    kind: Literal["box"]
    pageNumber: Page
    rect: Rect
    rotation: Literal[0] | Annotated[float, Field(strict=True, ge=-90, le=90, allow_inf_nan=False)] = 0

    @field_validator("rotation")
    @classmethod
    def legacy_zero(cls, value):
        # B1 receipts fingerprint integer zero. Preserve that representation
        # when widening the field for watermark angles, including 0.0 input.
        return 0 if value == 0 else value


class AnchorGeometry(InputModel):
    kind: Literal["anchor"]
    pageNumber: Page
    x: Number
    y: Number


class InkPoint(InputModel):
    x: Number
    y: Number

class PointsGeometry(InputModel):
    kind: Literal["points"]
    pageNumber: Page
    points: list[InkPoint] = Field(min_length=2, max_length=10000)

class Style(InputModel):
    stroke: Color | None = None
    fill: Color | None = None
    opacity: Annotated[float, Field(strict=True, gt=0, le=1, allow_inf_nan=False)] = 1
    lineWidth: Annotated[float, Field(strict=True, ge=.25, le=20, allow_inf_nan=False)] = 1
    fontSize: Annotated[float, Field(strict=True, ge=6, le=144, allow_inf_nan=False)] = 14


class AnnotationInput(InputModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1, max_length=36)
    type: Literal["highlight", "underline", "squiggly", "strikeout", "comment", "freeText", "ink", "rectangle", "circle", "ellipse", "signature", "watermark", "image"]
    schemaVersion: Literal[1] = 1
    pageNumber: Page
    position: list[Position] | None = None
    geometry: Annotated[TextGeometry | BoxGeometry | AnchorGeometry | PointsGeometry, Field(discriminator="kind")]
    style: Style = Field(default_factory=Style)
    assetId: Annotated[str, Field(min_length=1, max_length=36)] | None = None
    selectedText: str | None = Field(default=None, max_length=20000)
    content: str | None = Field(default=None, max_length=20000)
    color: Color = "#F5D547"
    zIndex: int = Field(default=0, ge=0, le=100000, strict=True)

    @model_validator(mode="after")
    def coherent(self):
        text = self.geometry.kind == "text"
        if self.type in ("rectangle", "circle", "ellipse", "signature", "watermark", "image") and self.geometry.kind != "box":
            raise ValueError("此对象需要矩形几何")
        if self.type == "ink" and self.geometry.kind != "points":
            raise ValueError("手绘需要笔迹点列")
        if self.geometry.kind == "points":
            if self.type != "ink" or len({(p.x, p.y) for p in self.geometry.points}) < 2:
                raise ValueError("无效笔迹")
        if self.geometry.kind == "box" and self.type != "watermark" and self.geometry.rotation != 0:
            raise ValueError("仅水印允许对象角度")
        if (self.assetId is not None) != (self.type in ("image", "signature")):
            raise ValueError("图片与签名必须关联本篇资产")
        if self.type in ("highlight", "underline", "squiggly", "strikeout") and not text:
            raise ValueError("文本标记需要真实文本锚点")
        if self.type == "freeText" and self.geometry.kind != "box":
            raise ValueError("自由文本需要矩形")
        if self.type == "comment" and self.geometry.kind not in ("text", "anchor"):
            raise ValueError("注释需要文本或页点")
        if text:
            if self.position != self.geometry.positions or not self.selectedText or not self.selectedText.strip():
                raise ValueError("文本位置与选区必须一致")
            if self.pageNumber != self.position[0].pageNumber:
                raise ValueError("起始页不一致")
        elif self.position is not None or self.pageNumber != self.geometry.pageNumber:
            raise ValueError("几何页码不一致")
        if self.type in ("comment", "freeText", "watermark") and not (self.content or "").strip():
            raise ValueError("请输入正文")
        if len(self.model_dump_json().encode()) > 1_048_576:
            raise ValueError("单个标注超出1MiB")
        return self


class Command(InputModel):
    commandId: str = Field(min_length=1, max_length=36)
    baseRevision: int = Field(ge=0, strict=True)


class Create(Command):
    annotation: AnnotationInput


class Edit(Command):
    version: int = Field(ge=1, strict=True)
    changes: dict


class Remove(Command):
    version: int = Field(ge=1, strict=True)


class Snapshot(AnnotationInput):
    documentId: str
    version: int = Field(ge=1, strict=True)
    createdAt: str
    updatedAt: str


class Restore(Command):
    operation: Literal["restore"]
    annotation: Snapshot


columns = {"schemaVersion": "schema_version", "pageNumber": "page_number", "selectedText": "selected_text", "assetId": "asset_id", "zIndex": "z_index"}


def dto(item):
    result = {key: getattr(item, columns.get(key, key)) for key in AnnotationInput.model_fields}
    return {**result, "documentId": item.document_id, "version": item.version,
            "createdAt": iso(item.created_at), "updatedAt": iso(item.updated_at)}


def create_annotation_router(current_session, require_csrf):
    router = APIRouter(prefix="/api/v1/documents/{id}")

    @router.get("/annotations")
    def listing(id: str, pageNumber: int | None = Query(None, ge=1), session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        # Lock keeps the returned revision and rows in the same collection snapshot.
        owned_document(db, session.user_id, id, lock=True)
        state = db.scalar(select(DocumentReaderState).where(DocumentReaderState.document_id == id, DocumentReaderState.owner_id == session.user_id).with_for_update())
        rows = db.scalars(select(Annotation).where(Annotation.document_id == id, Annotation.owner_id == session.user_id, Annotation.deleted_at.is_(None)).order_by(Annotation.page_number, Annotation.created_at, Annotation.id).with_for_update()).all()
        items = [dto(row) for row in rows]
        if pageNumber is not None:
            items = [a for a in items if a["pageNumber"] == pageNumber or any(p["pageNumber"] == pageNumber for p in a["position"] or [])]
        return {"items": items, "annotationRevision": state.annotation_revision if state else 0}

    @router.get("/annotation-commands/{command_id}")
    def receipt(id: str, command_id: str, session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        owned_document(db, session.user_id, id)
        row = db.scalar(select(AnnotationCommandReceipt).where(AnnotationCommandReceipt.document_id == id, AnnotationCommandReceipt.owner_id == session.user_id, AnnotationCommandReceipt.command_id == command_id))
        if not row or row.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
            reject(404, "COMMAND_NOT_FOUND", "命令收据不存在或已过期，请核对标注集合")
        return row.result

    def mutate(id, payload, operation, session, db, annotation_id=None):
        owner = session.user_id
        # A no-op UPDATE is a real write lock on SQLite and InnoDB, including first write.
        locked = db.execute(update(Document).where(Document.id == id, Document.owner_id == owner,
            Document.deleted_at.is_(None), Document.purge_job_id.is_(None)).values(version=Document.version))
        if locked.rowcount != 1:
            db.rollback(); reject(404, "DOCUMENT_NOT_FOUND", "文献不存在或不可访问")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Fingerprint the supplied payload, not a newly generated default annotation id.
        fingerprint = hashlib.sha256(json.dumps([operation, annotation_id, payload.model_dump(exclude_unset=True)], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        prior = db.scalar(select(AnnotationCommandReceipt).where(AnnotationCommandReceipt.document_id == id,
            AnnotationCommandReceipt.command_id == payload.commandId, AnnotationCommandReceipt.owner_id == owner).with_for_update())
        if prior:
            if prior.fingerprint != fingerprint:
                reject(409, "COMMAND_REUSED", "命令ID已用于不同操作")
            if prior.expires_at <= now:
                reject(409, "COMMAND_EXPIRED", "收据已过期，请重新核对集合")
            return prior.result
        doc, file = owned_document(db, owner, id, lock=True)
        state = db.scalar(select(DocumentReaderState).where(DocumentReaderState.document_id == id, DocumentReaderState.owner_id == owner).with_for_update())
        revision = state.annotation_revision if state else 0
        if revision != payload.baseRevision:
            reject(409, "ANNOTATION_CONFLICT", "批注集合已更新，本地草稿应保留", {"annotationRevision": revision})
        if state is None:
            state = DocumentReaderState(document_id=id, owner_id=owner, annotation_revision=0); db.add(state)
        annotation_id = annotation_id or payload.annotation.id
        row = db.scalar(select(Annotation).where(Annotation.id == annotation_id).with_for_update())
        if operation == "create":
            if row:
                if row.owner_id != owner or row.document_id != id:
                    reject(404, "ANNOTATION_NOT_FOUND", "标注不存在或不可访问")
                reject(409, "ANNOTATION_EXISTS", "标注ID已存在")
            data = payload.annotation
            row = Annotation(id=annotation_id, owner_id=owner, document_id=id, version=0, created_at=now)
        else:
            if not row or row.owner_id != owner or row.document_id != id or (operation != "restore" and row.deleted_at):
                reject(404, "ANNOTATION_NOT_FOUND", "标注不存在或不可访问")
            if operation == "restore":
                if payload.annotation.documentId != id:
                    reject(404, "ANNOTATION_NOT_FOUND", "标注不存在或不可访问")
                if not row.deleted_at or payload.annotation.version + 1 != row.version:
                    reject(409, "RESTORE_CONFLICT", "已删除对象的版本不匹配")
                original = {k: v for k, v in dto(row).items() if k in AnnotationInput.model_fields}
                data = AnnotationInput.model_validate(payload.annotation.model_dump(include=set(AnnotationInput.model_fields)))
                if original != data.model_dump():
                    reject(422, "INVALID_RESTORE", "仅可恢复原对象快照")
            else:
                if row.version != payload.version:
                    reject(409, "ANNOTATION_VERSION_CONFLICT", "标注已更新")
                if operation == "edit":
                    allowed = {"color", "content", "style", "geometry", "zIndex", "assetId"}
                    if set(payload.changes) - allowed or ("geometry" in payload.changes and row.geometry["kind"] == "text"):
                        reject(422, "INVALID_CHANGES", "类型和文本锚点不可修改")
                    try:
                        values = {**{k:v for k,v in dto(row).items() if k in AnnotationInput.model_fields}, **payload.changes}
                        if isinstance(payload.changes.get("style"), dict):
                            values["style"] = {**row.style, **payload.changes["style"]}
                        data = AnnotationInput.model_validate(values)
                    except ValidationError:
                        reject(422, "INVALID_ANNOTATION", "标注属性或几何无效")
                else:
                    data = None
        if data:
            if data.assetId:
                from .reader_assets import validate_asset
                asset = validate_asset(db, owner, id, data.assetId)
                asset.expires_at = None
            if data.type in ("circle", "image", "signature"):
                try:
                    physical_page = PdfReader(storage_path(file.storage_key)).pages[data.pageNumber-1]
                    crop = physical_page.cropbox
                    r = data.geometry.rect
                    ratio = r.width * float(crop.width) / (r.height * float(crop.height))
                    expected = 1 if data.type == "circle" else asset.width / asset.height
                    if abs(ratio / expected - 1) > .005:
                        reject(422, "INVALID_ASPECT", "圆形与图片须保持物理宽高比")
                except IndexError:
                    reject(422, "INVALID_PAGE", "标注页码超出PDF真实页数")
            if doc.page_count is None:
                try:
                    reader = PdfReader(storage_path(file.storage_key)); doc.page_count = len(reader.pages)
                except Exception:
                    reject(422, "INVALID_PDF", "无法验证PDF页数")
            pages = [p.pageNumber for p in data.position] if data.position else [data.pageNumber]
            if any(p > doc.page_count for p in pages):
                reject(422, "INVALID_PAGE", "标注页码超出PDF真实页数")
            if operation in ("create", "restore") and db.scalar(select(func.count()).select_from(Annotation).where(Annotation.document_id == id, Annotation.deleted_at.is_(None))) >= 10000:
                reject(422, "ANNOTATION_LIMIT", "本篇标注已达10000个")
            if row.asset_id and row.asset_id != data.assetId:
                from .models import ReaderAsset
                previous_asset = db.get(ReaderAsset, row.asset_id)
                other = db.scalar(select(Annotation.id).where(Annotation.asset_id == row.asset_id,
                    Annotation.id != row.id, Annotation.deleted_at.is_(None)))
                if previous_asset and not other:
                    previous_asset.expires_at = now + timedelta(hours=24)
            for key, value in data.model_dump().items():
                if key != "id": setattr(row, columns.get(key, key), value)
            row.deleted_at = None
        else:
            row.deleted_at = now
            if row.asset_id:
                from .models import ReaderAsset
                asset = db.get(ReaderAsset, row.asset_id)
                other = db.scalar(select(Annotation.id).where(Annotation.asset_id == row.asset_id,
                    Annotation.id != row.id, Annotation.deleted_at.is_(None)))
                if asset and not other:
                    asset.expires_at = now + timedelta(hours=24)
        row.version += 1; row.updated_at = now
        db.add(row)
        state.annotation_revision += 1
        result = {"commandId": payload.commandId, "annotationRevision": state.annotation_revision, "annotation": dto(row) if not row.deleted_at else None}
        db.add(AnnotationCommandReceipt(document_id=id, command_id=payload.commandId, owner_id=owner,
            fingerprint=fingerprint, result=result, expires_at=now + timedelta(hours=24)))
        # Prune expired receipts transactionally; old commands cannot pass the advanced CAS.
        db.execute(delete(AnnotationCommandReceipt).where(AnnotationCommandReceipt.document_id == id, AnnotationCommandReceipt.expires_at < now))
        db.commit()
        return result

    @router.post("/annotations", status_code=201)
    def create(id: str, payload: Create, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        return mutate(id, payload, "create", session, db)

    @router.patch("/annotations/{annotation_id}")
    def edit(id: str, annotation_id: str, payload: Edit, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        return mutate(id, payload, "edit", session, db, annotation_id)

    @router.delete("/annotations/{annotation_id}")
    def remove(id: str, annotation_id: str, payload: Remove, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        return mutate(id, payload, "delete", session, db, annotation_id)

    @router.post("/annotation-commands")
    def restore(id: str, payload: Restore, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        return mutate(id, payload, "restore", session, db)

    return router
