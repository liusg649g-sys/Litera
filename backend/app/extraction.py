"""题录自动提取：持久化服务函数 + 4 个 API 端点。

三层提取引擎在 metadata_extraction.py；本文件负责：
- 把三层结果写入 extraction_jobs / extraction_results / document_pages / document_chunks
- 提供手动触发、候选查询、页/块查询端点
- 启动时扫描 processing 的 orphan job
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import (Document, DocumentChunk, DocumentFile, DocumentPage,
                      ExtractionJob, ExtractionResult, LoginSession)
from .documents import owned_document, storage_path, document_dto
from .metadata_extraction import (LayerResult, extract_heuristic, extract_from_pdf_metadata,
                                    extract_llm, merge_candidates, run_sync_layers)

logger = logging.getLogger(__name__)


# ── DTO ──────────────────────────────────────────────────────────

class ExtractionCandidatesDTO(BaseModel):
    documentId: str
    extractionVersion: str
    jobStatus: str                  # queued | processing | completed | failed
    errorCode: str | None = None
    metadata: dict                  # 合并后的候选
    fieldSources: dict              # 各层原始值
    warnings: list[str]


# ── 持久化服务函数 ───────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _jsonable(obj):
    """递归把 FieldCandidate/LayerResult 等 dataclass 转成纯 dict（便于 db JSON 列）。"""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _jsonable(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


# ── 自动回填正式题录 ─────────────────────────────────────────────

_BACKFILL_FIELDS = ("title", "authors", "abstract", "keywords", "year", "journal", "doi")


def _initial_metadata(doc_file: DocumentFile | None) -> dict:
    """上传初始值：title=原始文件名去 .pdf 后缀（与 save_upload 一致），authors/keywords=[]，其余 None。"""
    initial_title = None
    if doc_file is not None:
        initial_title = doc_file.original_name[:-4].strip() or "未命名文献"
    return {"title": initial_title, "authors": [], "keywords": [],
            "abstract": None, "year": None, "journal": None, "doi": None}


def backfill_document_metadata(db: Session, doc: Document, new_merged: dict,
                               prev_merged: dict | None = None) -> list[str]:
    """把最终合并值自动写入 documents 正式题录，返回实际更新的字段名列表。

    字段级保护：仅当字段当前值等于上传初始值或上一次自动写入值时才更新，
    用户手动修改过的字段跳过；有字段更新时递增 version，使过期 PATCH 返回 409。
    """
    doc_file = db.scalar(select(DocumentFile).where(DocumentFile.document_id == doc.id))
    initial = _initial_metadata(doc_file)
    prev_merged = prev_merged or {}
    updated_fields: list[str] = []
    for field in _BACKFILL_FIELDS:
        entry = new_merged.get(field)
        if not entry:
            continue
        new_value = entry.get("value")
        if new_value is None or new_value == [] or new_value == "":
            continue  # 不用空值覆盖任何现有值
        current = getattr(doc, field)
        prev_entry = prev_merged.get(field) or {}
        prev_value = prev_entry.get("value")
        if current != initial[field] and current != prev_value:
            continue  # 用户已手动修改，跳过
        if current == new_value:
            continue
        setattr(doc, field, new_value)
        updated_fields.append(field)
    if updated_fields:
        doc.version += 1
        doc.updated_at = _now()
        logger.info("Auto-backfilled document %s fields: %s", doc.id, updated_fields)
    return updated_fields


def create_extraction_job(db: Session, owner_id: str, document_id: str, file_hash: str) -> ExtractionJob:
    """创建新的 extraction_job；同 documentId+fileHash 已有 completed job 时复用版本。"""
    existing = db.scalar(select(ExtractionJob).where(
        ExtractionJob.owner_id == owner_id,
        ExtractionJob.document_id == document_id,
        ExtractionJob.file_hash == file_hash,
        ExtractionJob.status == "completed",
    ).order_by(ExtractionJob.created_at.desc()))
    if existing:
        return existing

    # 创建新版本
    version_id = str(uuid.uuid4())
    now = _now()
    job = ExtractionJob(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        document_id=document_id,
        file_hash=file_hash,
        status="queued",
        attempts=0,
        error_code=None,
        version_id=version_id,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.flush()
    return job


def persist_extraction(db: Session, job: ExtractionJob, doc: Document,
                         layer1: LayerResult, layer2: LayerResult,
                         page_texts: list[str]) -> dict:
    """执行同步层（Layer 1+2）+ 写 document_pages / document_chunks / extraction_results。

    返回 merge 后的 dict（含 metadata / fieldSources / warnings / hasText）。
    """
    now = _now()
    job.status = "processing"
    job.attempts += 1
    job.updated_at = now

    # 写页文本
    pages_inserted = 0
    page_offsets: list[int] = []  # 每页起始字符偏移（用于 chunk 的全局 char_offset）
    running_offset = 0
    for i, text in enumerate(page_texts):
        db.add(DocumentPage(
            id=str(uuid.uuid4()),
            owner_id=job.owner_id,
            document_id=job.document_id,
            extraction_version=job.version_id,
            page_number=i + 1,
            text=text or "",
        ))
        page_offsets.append(running_offset)
        running_offset += len(text or "") + 1  # +1 for newline between pages
        pages_inserted += 1
    db.flush()

    # 写 chunks（简单段落切分）
    chunk_idx = 0
    for page_i, text in enumerate(page_texts):
        if not text or not text.strip():
            continue
        page_start = page_offsets[page_i]
        paragraphs = [p for p in text.split("\n\n") if p.strip()]
        for para in paragraphs:
            # 目标 200-500 字符；超长段落按 500 硬切
            if len(para) <= 500:
                start_offset = text.find(para)
                end_offset = start_offset + len(para)
                db.add(DocumentChunk(
                    id=str(uuid.uuid4()),
                    owner_id=job.owner_id,
                    document_id=job.document_id,
                    extraction_version=job.version_id,
                    page_number=page_i + 1,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    text=para,
                ))
                chunk_idx += 1
            else:
                # 按 500 字符切
                pos = 0
                while pos < len(para):
                    seg = para[pos:pos + 500]
                    start_offset = text.find(seg, pos) if pos > 0 else text.find(seg)
                    if start_offset < 0:
                        start_offset = pos
                    end_offset = start_offset + len(seg)
                    db.add(DocumentChunk(
                        id=str(uuid.uuid4()),
                        owner_id=job.owner_id,
                        document_id=job.document_id,
                        extraction_version=job.version_id,
                        page_number=page_i + 1,
                        start_offset=start_offset,
                        end_offset=end_offset,
                        text=seg,
                    ))
                    chunk_idx += 1
                    pos += len(seg)
    db.flush()

    # 合并（Layer 3 还没回来，传 None）
    merged = merge_candidates(layer1, layer2, LayerResult(layer="llm"))

    # 写 extraction_results
    db.add(ExtractionResult(
        id=str(uuid.uuid4()),
        owner_id=job.owner_id,
        document_id=job.document_id,
        extraction_version=job.version_id,
        file_hash=job.file_hash,
        candidates=_jsonable(merged["metadata"]),
        field_sources=_jsonable(merged["fieldSources"]),
        warnings=list(merged["warnings"]),
        created_at=now,
    ))
    db.flush()

    # 临时置为 completed（Layer 3 回来时会更新）
    job.status = "completed"
    job.updated_at = now
    db.commit()

    # 更新 Document 的 extraction_version 和 parse_status
    db.refresh(job)
    doc = db.get(Document, job.document_id)
    if doc:
        db.refresh(doc)  # 重试路径下会话可能持有旧状态，刷新后再做字段级保护比较
        # 重试场景：取旧版本自动写入的候选值，用于字段级保护比较
        prev_candidates: dict = {}
        if doc.extraction_version and doc.extraction_version != job.version_id:
            old_result = db.scalar(select(ExtractionResult).where(
                ExtractionResult.owner_id == job.owner_id,
                ExtractionResult.document_id == doc.id,
                ExtractionResult.extraction_version == doc.extraction_version,
            ))
            if old_result:
                prev_candidates = old_result.candidates or {}
        doc.extraction_version = job.version_id
        doc.parse_status = "processing"  # Layer 3 还在跑
        backfill_document_metadata(db, doc, merged["metadata"], prev_candidates)
        doc.updated_at = now
        db.commit()

    return merged


def mark_job_failed(db: Session, job: ExtractionJob, error_code: str, warnings: list[str] | None = None):
    job.status = "failed"
    job.error_code = error_code
    job.updated_at = _now()
    doc = db.get(Document, job.document_id)
    if doc:
        doc.parse_status = "failed"
        doc.updated_at = job.updated_at
    if warnings:
        existing = db.scalar(select(ExtractionResult).where(
            ExtractionResult.owner_id == job.owner_id,
            ExtractionResult.document_id == job.document_id,
            ExtractionResult.extraction_version == job.version_id,
        ))
        if existing:
            existing.warnings = list(set(existing.warnings + warnings))
    db.commit()


def mark_job_completed_with_llm(db: Session, job: ExtractionJob, layer3: LayerResult,
                                  page_texts: list[str]):
    """Layer 3 完成后：合并新结果 + 更新 extraction_results + 更新 document_pages 的 chunk。"""
    now = _now()
    prev = db.scalar(select(ExtractionResult).where(
        ExtractionResult.owner_id == job.owner_id,
        ExtractionResult.document_id == job.document_id,
        ExtractionResult.extraction_version == job.version_id,
    ))
    if prev is None:
        return

    # 重新合并（这次包含 Layer 3）
    prev_candidates_snapshot = dict(prev.candidates or {})  # 上一次自动写入的值，用于字段级保护
    layer1 = LayerResult(layer="metadata")  # 旧的 fieldSources 里有，不用重跑
    layer2 = LayerResult(layer="heuristic")
    # 从 prev.field_sources 里还原 layer1/layer2 的原始结果
    for fname, entries in prev.field_sources.items():
        for entry in entries:
            src = entry.get("source")
            if src == "metadata" and fname not in layer1.fields:
                from .metadata_extraction import FieldCandidate
                layer1.fields[fname] = FieldCandidate(entry["value"], "metadata", entry["confidence"])
            elif src == "heuristic" and fname not in layer2.fields:
                from .metadata_extraction import FieldCandidate
                layer2.fields[fname] = FieldCandidate(entry["value"], "heuristic", entry["confidence"])
    merged = merge_candidates(layer1, layer2, layer3)

    prev.candidates = _jsonable(merged["metadata"])
    prev.field_sources = _jsonable(merged["fieldSources"])
    # 重跑后旧 attempt 的警告（如已修复的解析失败）不再保留，warnings 反映最近一次执行
    prev.warnings = list(dict.fromkeys(merged["warnings"] + layer3.warnings))
    prev.created_at = now
    db.flush()

    job.status = "completed"
    job.updated_at = now
    doc = db.get(Document, job.document_id)
    if doc:
        # 本会话在 LLM 调用（数秒）前就缓存了 doc，必须刷新到已提交状态，
        # 否则字段级保护比较用的是过期值，会覆盖期间用户并发的 PATCH
        db.refresh(doc)
        doc.parse_status = "completed"
        backfill_document_metadata(db, doc, merged["metadata"], prev_candidates_snapshot)
        doc.updated_at = now
    db.commit()

    # 05 的提取版本完成后异步构建 06 的检索索引；失败不影响本次提取结果。
    if doc is not None and doc.parse_status == "completed" and doc.extraction_version:
        try:
            from .rag import trigger_index_build
            trigger_index_build(doc.id, job.owner_id, doc.extraction_version)
        except Exception as exc:
            logger.warning("QA index trigger failed for %s: %s", job.document_id, exc)


# ── 异步触发 Layer 3 ──────────────────────────────────────────────

async def run_layer3_async(document_id: str, owner_id: str):
    """异步任务：执行 Layer 3，完成后更新 extraction_results 和 job 状态。"""
    from .database import SessionLocal
    from pypdf import PdfReader

    db = SessionLocal()
    try:
        doc = db.scalar(select(Document).where(Document.id == document_id, Document.owner_id == owner_id,
                                                Document.deleted_at.is_(None)))
        if doc is None:
            logger.warning("Layer 3 aborted: document %s no longer visible", document_id)
            return

        job = db.scalar(select(ExtractionJob).where(
            ExtractionJob.owner_id == owner_id,
            ExtractionJob.document_id == document_id,
            ExtractionJob.status.in_(["queued", "processing", "completed"]),
        ).order_by(ExtractionJob.created_at.desc()))
        if job is None:
            return

        # 读取 PDF 前 3 页文本
        try:
            import io
            pdf_path = storage_path(doc.id + ".pdf")
            pdf_bytes = pdf_path.read_bytes()
            reader = PdfReader(io.BytesIO(pdf_bytes))
            all_texts = []
            for page in reader.pages[:3]:
                try:
                    all_texts.append(page.extract_text() or "")
                except Exception:
                    all_texts.append("")
        except Exception as exc:
            mark_job_failed(db, job, "EXTRACTION_PDF_READ_ERROR", [str(exc)])
            return

        # 执行 Layer 3
        try:
            layer3 = await extract_llm(all_texts)
        except Exception as exc:
            # Layer 3 失败不算致命，Layer 1+2 已完成
            logger.warning("Layer 3 failed for %s: %s", document_id, exc)
            job = db.scalar(select(ExtractionJob).where(ExtractionJob.id == job.id))
            if job:
                mark_job_failed(db, job, "MODEL_UNAVAILABLE", [str(exc)])
            return

        mark_job_completed_with_llm(db, job, layer3, all_texts)
    finally:
        db.close()


# ── 启动时扫描 orphan job ─────────────────────────────────────────

def run_startup_scan(db: Session):
    """进程启动时把所有 processing 状态的 job 置为 failed。"""
    orphans = db.scalars(select(ExtractionJob).where(ExtractionJob.status.in_(["queued", "processing"]))).all()
    for job in orphans:
        job.status = "failed"
        job.error_code = "PROCESS_INTERRUPTED"
        job.updated_at = _now()
    if orphans:
        db.commit()
        logger.info("Marked %d orphan extraction jobs as failed", len(orphans))


# ── API 路由 ──────────────────────────────────────────────────────

def create_extraction_router(current_session, require_csrf) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["extraction"])

    @router.post("/documents/{document_id}/extract")
    async def trigger_extraction(document_id: str, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
        """手动触发或重试提取。同步端点跑在线程池里没有事件循环，必须用 async def + create_task。"""
        doc, doc_file = owned_document(db, session.user_id, document_id)
        job = create_extraction_job(db, session.user_id, doc.id, doc_file.sha256)
        if job.status == "completed":
            # 复用已完成版本：pages/results 已在该版本下落库，只需重跑 Layer 3
            # parse_status 置回 processing，让前端轮询能观察到这次重试
            doc.parse_status = "processing"
            doc.updated_at = _now()
            db.commit()
            asyncio.create_task(run_layer3_async(doc.id, session.user_id))
            return {"status": "triggered", "version": job.version_id, "jobStatus": "processing"}

        # 新任务（首次或上次失败）：完整重跑 Layer 1+2 并以新版本落库，保证 pages/results 与 version 一致
        import io
        from pypdf import PdfReader
        try:
            pdf_path = storage_path(doc_file.storage_key)
            reader = PdfReader(io.BytesIO(pdf_path.read_bytes()))
            layer1, layer2, page_texts, _ = run_sync_layers(reader)
        except Exception as exc:
            raise HTTPException(status_code=422, detail={
                "code": "EXTRACTION_PDF_READ_ERROR", "message": f"PDF 读取失败: {exc}"})
        persist_extraction(db, job, doc, layer1, layer2, page_texts)
        asyncio.create_task(run_layer3_async(doc.id, session.user_id))
        return {"status": "triggered", "version": job.version_id, "jobStatus": "processing"}

    @router.get("/documents/{document_id}/extraction-candidates")
    def get_candidates(document_id: str, session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        """返回 extraction_results + 最新 job 状态。"""
        doc, _ = owned_document(db, session.user_id, document_id)
        version = doc.extraction_version
        if not version:
            return {"documentId": document_id, "extractionVersion": None, "jobStatus": "not_requested",
                    "metadata": {}, "fieldSources": {}, "warnings": []}
        result = db.scalar(select(ExtractionResult).where(
            ExtractionResult.owner_id == session.user_id,
            ExtractionResult.document_id == document_id,
            ExtractionResult.extraction_version == version,
        ))
        job = db.scalar(select(ExtractionJob).where(
            ExtractionJob.owner_id == session.user_id,
            ExtractionJob.document_id == document_id,
            ExtractionJob.version_id == version,
        ))
        return {
            "documentId": document_id,
            "extractionVersion": version,
            "jobStatus": job.status if job else "not_requested",
            "errorCode": job.error_code if job else None,
            "metadata": result.candidates if result else {},
            "fieldSources": result.field_sources if result else {},
            "warnings": result.warnings if result else [],
        }

    @router.get("/documents/{document_id}/extraction-pages")
    def get_pages(document_id: str, version: str | None = Query(None),
                   session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        doc, _ = owned_document(db, session.user_id, document_id)
        target_version = version or doc.extraction_version
        if not target_version:
            return []
        pages = db.scalars(select(DocumentPage).where(
            DocumentPage.owner_id == session.user_id,
            DocumentPage.document_id == document_id,
            DocumentPage.extraction_version == target_version,
        ).order_by(DocumentPage.page_number)).all()
        return [{"pageNumber": p.page_number, "text": p.text} for p in pages]

    @router.get("/documents/{document_id}/extraction-chunks")
    def get_chunks(document_id: str, version: str | None = Query(None),
                    session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
        doc, _ = owned_document(db, session.user_id, document_id)
        target_version = version or doc.extraction_version
        if not target_version:
            return []
        chunks = db.scalars(select(DocumentChunk).where(
            DocumentChunk.owner_id == session.user_id,
            DocumentChunk.document_id == document_id,
            DocumentChunk.extraction_version == target_version,
        ).order_by(DocumentChunk.page_number, DocumentChunk.start_offset)).all()
        return [
            {"pageNumber": c.page_number, "startOffset": c.start_offset,
             "endOffset": c.end_offset, "text": c.text}
            for c in chunks
        ]

    return router
