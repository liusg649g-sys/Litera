"""Independent worker process that consumes queued extraction_jobs and runs Layer 3.

Entrypoint: ``python -m app.extraction_worker`` (module runs via ``__main__`` guard).
Uses a standalone loop that polls the ``extraction_jobs`` table under
``FOR UPDATE SKIP LOCKED`` so multiple workers can run without stepping on
each other.  Database is treated as the job queue (the project deliberately
avoids Redis/RabbitMQ for this workload).

Retry policy: attempts++ on every failure; next_retry_at = NOW() + 2^attempts *
INTERVAL 5 SECOND; attempts <= 3 -> back to queued (re-schedule); else failed.
"""
from __future__ import annotations

import asyncio
import io
import logging
import sys
import time
from datetime import datetime, timezone

from sqlalchemy import select, update

from .audit import log_audit
from .database import SessionLocal
from .extraction import mark_job_completed_with_llm, mark_job_failed
from .metadata_extraction import extract_llm
from .models import Document, ExtractionJob
from .documents import storage_path

logger = logging.getLogger("extraction_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _read_pdf_first3(pdf_path) -> list[str] | None:
    """Try to read the first 3 pages' text; return None on hard read error."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_path.read_bytes()))
    except Exception as exc:
        logger.warning("PDF read error %s: %s", pdf_path, exc)
        return None
    out: list[str] = []
    for page in reader.pages[:3]:
        try:
            out.append(page.extract_text() or "")
        except Exception:
            out.append("")
    return out


async def _run_layer3_async(job: ExtractionJob, page_texts: list[str]) -> None:
    """Run Layer 3 in an event loop; on completion, finalise the DB state.

    Layer 1+2 are already persisted (persist_extraction ran in the API process).
    This is worker's sole responsibility.
    """
    db = SessionLocal()
    try:
        layer3 = await extract_llm(page_texts)
    except Exception as exc:
        # Layer 3 failure (ModelFailure or otherwise) is non-fatal for extraction:
        # Layer 1+2 results remain.  We bump attempts, apply exponential backoff,
        # and either re-queue or declare the job failed.
        logger.warning("Layer 3 failed for job %s (attempts %d): %s", job.id, job.attempts, exc)
        db.close()
        _schedule_retry(job.id, error_code=getattr(exc, "code", "MODEL_UNAVAILABLE"),
                        warnings=[str(exc)])
        return

    # Success path: refresh job (worker's session might be stale), finalise
    # extraction_results with the merged Layer 3 output, set status=completed,
    # backfill documents.parse_status=completed, and trigger QA index build.
    db = SessionLocal()
    try:
        fresh = db.get(ExtractionJob, job.id)
        doc = db.get(Document, job.document_id)
        if fresh is None or doc is None or doc.deleted_at is not None:
            logger.info("Job %s or document no longer visible; aborting finalisation", job.id)
            db.close()
            return
        mark_job_completed_with_llm(db, fresh, layer3, page_texts)
    finally:
        db.close()


def _schedule_retry(job_id: str, error_code: str, warnings: list[str] | None = None) -> None:
    """Increment attempts and re-queue with exponential backoff, or mark failed.

    Attempts start at 0 (first consumption).  After each failure: attempts++, and
    while attempts <= 3 we re-queue with backoff; on attempt 4+ we mark failed.
    """
    import datetime as _dt
    db = SessionLocal()
    try:
        job = db.get(ExtractionJob, job_id)
        if job is None:
            return
        job.attempts += 1
        if job.attempts > 3:
            mark_job_failed(db, job, error_code, warnings)
            logger.error("Job %s exhausted retries (%d); error=%s", job_id, job.attempts, error_code)
            return
        # Backoff: 5s, 10s, 20s (2**attempts * 5s)
        backoff_seconds = (2 ** job.attempts) * 5
        job.next_retry_at = _now() + _dt.timedelta(seconds=backoff_seconds)
        job.status = "queued"
        job.error_code = error_code
        job.updated_at = _now()
        doc = db.get(Document, job.document_id)
        if doc and doc.deleted_at is None:
            # parse_status 保持原值；mark_job_failed 会置 failed
            pass
        db.commit()
        logger.info("Job %s re-queued (attempt %d); next_retry_at=%s", job_id, job.attempts, job.next_retry_at)
    finally:
        db.close()


def _claim_job() -> ExtractionJob | None:
    """Grab the single oldest queued job that's due to run, under SKIP LOCKED."""
    db = SessionLocal()
    try:
        now = _now()
        stmt = (select(ExtractionJob)
                .where(ExtractionJob.status == "queued")
                .where((ExtractionJob.next_retry_at.is_(None))
                       | (ExtractionJob.next_retry_at <= now))
                .order_by(ExtractionJob.created_at)
                .limit(1)
                .with_for_update(skip_locked=True))
        job = db.scalar(stmt)
        if job is None:
            return None
        # Mark it processing and flush the lock row out of the queue.
        job.status = "processing"
        job.updated_at = _now()
        db.commit()
        # Refresh after commit so callers see the final status.
        db.refresh(job)
        return job
    finally:
        db.close()


def _safe_run(job: ExtractionJob) -> None:
    """Wrap one job's execution in broad try/except so unexpected errors don't crash the worker."""
    db = SessionLocal()
    try:
        job_check = db.get(ExtractionJob, job.id)
        if job_check is None or job_check.status != "processing":
            return  # somebody else re-processed it (shouldn't happen, but safe to bail)
        doc = db.get(Document, job_check.document_id)
        if doc is None or doc.deleted_at is not None:
            db.close()
            # Document vanished; mark job skipped.
            _schedule_retry(job.id, error_code="DOCUMENT_MISSING")
            return
        pdf_path = storage_path(doc.id + ".pdf")
        texts = _read_pdf_first3(pdf_path)
        db.close()
        if texts is None:
            _schedule_retry(job.id, error_code="EXTRACTION_PDF_READ_ERROR",
                            warnings=["PDF read failed on worker"])
            return
        asyncio.run(_run_layer3_async(job, texts))
    except Exception as exc:
        logger.exception("Worker crashed on job %s: %s", job.id, exc)
        db.close()
        _schedule_retry(job.id, error_code="WORKER_INTERNAL", warnings=[str(exc)])


def _recover_interrupted_jobs() -> None:
    """回收上次进程崩溃遗留的 processing 孤儿 job：置回 queued 并立即重新调度。

    单 worker 部署下，worker 启动时不存在合法的 processing 行（若以后跑多 worker，
    需改为按 updated_at 超时判断，避免误收其他实例正在执行的任务）。
    """
    db = SessionLocal()
    try:
        stale = db.scalars(select(ExtractionJob).where(ExtractionJob.status == "processing")).all()
        if not stale:
            return
        now = _now()
        for job in stale:
            job.status = "queued"
            job.next_retry_at = now
            job.updated_at = now
        db.commit()
        logger.info("Recovered %d interrupted job(s) back to queued", len(stale))
    finally:
        db.close()


def run_forever() -> None:
    logger.info("extraction-worker starting; polling every 1s")
    _recover_interrupted_jobs()
    idle_sleep = 1.0  # seconds
    busy_sleep = 0.05  # keep looping fast when there's work
    try:
        while True:
            job = _claim_job()
            if job is None:
                time.sleep(idle_sleep)
                continue
            # SEC-07: record start-of-extraction event.
            start_ns = time.perf_counter_ns()
            logger.info("Picked up job %s (attempts=%d)", job.id, job.attempts)
            log_audit(
                action="extract",
                target=job.document_id,
                status="processing",
                user_id=job.owner_id,
                skill="extract-llm",
                extra={"job_id": job.id, "attempts": job.attempts, "version_id": job.version_id},
            )
            _safe_run(job)
            # SEC-07: record completion after _safe_run persisted the final status.
            duration_ms = int((time.perf_counter_ns() - start_ns) / 1_000_000)
            _log_extraction_outcome(job.id, duration_ms)
            time.sleep(busy_sleep)
    except KeyboardInterrupt:
        logger.info("extraction-worker stopped by SIGINT")


def _log_extraction_outcome(job_id: str, duration_ms: int) -> None:
    """Read final job state and write a single completion audit row.

    We re-query because _safe_run may have committed status changes
    (completed / failed / DOCUMENT_MISSING).
    """
    db = SessionLocal()
    try:
        job = db.get(ExtractionJob, job_id)
        if job is None:
            return
        status_map = {
            "completed": "success",
            "failed": "failed",
            "queued": "partial",   # re-queued = backoff retry, not terminal
            "processing": "partial",
        }
        outcome = status_map.get(job.status, job.status)
        log_audit(
            action="extract",
            target=job.document_id,
            status=outcome,
            user_id=job.owner_id,
            skill="extract-llm",
            duration_ms=duration_ms,
            error_code=job.error_code,
            extra={"job_id": job.id, "attempts": job.attempts, "version_id": job.version_id},
        )
    except Exception as exc:
        logger.warning("audit outcome lookup failed for job %s: %s", job_id, exc)
    finally:
        db.close()


if __name__ == "__main__":
    run_forever()
