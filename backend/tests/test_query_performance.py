"""Performance gate: N+1 and per-statement duration on representative list
endpoints. Uses the isolated temporary SQLite database, never a business DB.
Thresholds are intentionally conservative for a fixed 50-row fixture and are
recorded in reports/query-performance.json for review.
"""
import hashlib
import json
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import event

from app.database import SessionLocal, engine
from app.models import Document, DocumentFile, DocumentTag, Note, Tag
from test_documents import logged  # noqa: F401  (pytest fixture)

ROWS = 50
MAX_SELECTS = 12          # auth/session + count + page + batch tag/document queries
MAX_STATEMENT_MS = 100    # per SQL statement on the disposable SQLite fixture
REPORT = Path(__file__).resolve().parents[2] / "reports" / "query-performance.json"


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _seed(owner):
    now = _now()
    with SessionLocal() as db:
        tags = [Tag(id=str(uuid.uuid4()), owner_id=owner, name=f"tag-{i}",
                    normalized_name=f"tag-{i}", color="#FFFF00",
                    created_at=now, updated_at=now) for i in range(5)]
        db.add_all(tags)
        db.flush()
        document_ids = []
        for i in range(ROWS):
            document_id = str(uuid.uuid4())
            document_ids.append(document_id)
            db.add(Document(id=document_id, owner_id=owner, title=f"Performance paper {i:02d}",
                            authors=["Synthetic Author"], keywords=["perf"], year=2026,
                            version=1, parse_status="completed", created_at=now, updated_at=now))
            db.add(DocumentFile(id=str(uuid.uuid4()), document_id=document_id, owner_id=owner,
                                original_name=f"paper-{i:02d}.pdf",
                                storage_key=f"{document_id}.pdf",
                                sha256=hashlib.sha256(str(i).encode()).hexdigest(),
                                size_bytes=1024, mime_type="application/pdf"))
        db.flush()
        for document_id in document_ids:
            for tag in tags[:2]:
                db.add(DocumentTag(document_id=document_id, tag_id=tag.id, owner_id=owner))
        for i in range(ROWS):
            db.add(Note(id=str(uuid.uuid4()), owner_id=owner, title=f"Performance note {i:02d}",
                        content="Synthetic body", content_format="plain-text", version=1,
                        source_schema_version=1, sources=[], created_at=now, updated_at=now))
        db.commit()


@contextmanager
def _capture():
    samples = []

    def before(conn, cursor, statement, parameters, context, executemany):
        samples.append([statement, time.perf_counter(), None])

    def after(conn, cursor, statement, parameters, context, executemany):
        if samples:
            samples[-1][2] = time.perf_counter()

    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "after_cursor_execute", after)
    try:
        yield samples
    finally:
        event.remove(engine, "before_cursor_execute", before)
        event.remove(engine, "after_cursor_execute", after)


def _selects(samples):
    rows = []
    for statement, started, finished in samples:
        if not statement.lstrip().upper().startswith("SELECT"):
            continue
        duration_ms = ((finished or time.perf_counter()) - started) * 1000
        rows.append((statement, duration_ms))
    return rows


def _summary(samples):
    selects = _selects(samples)
    durations = sorted(duration for _, duration in selects)
    return {
        "selectCount": len(selects),
        "maxMs": round(durations[-1], 3) if durations else 0.0,
        "p95Ms": round(durations[min(len(durations) - 1, int(0.95 * len(durations)))], 3) if durations else 0.0,
    }


def _assert_gate(name, summary, expected_rows):
    assert summary["selectCount"] <= MAX_SELECTS, (
        f"{name}: {summary['selectCount']} SELECTs for {expected_rows} rows "
        f"(limit {MAX_SELECTS}); likely N+1")
    assert summary["maxMs"] <= MAX_STATEMENT_MS, (
        f"{name}: slowest statement {summary['maxMs']}ms (limit {MAX_STATEMENT_MS}ms)")


def test_list_endpoints_do_not_issue_per_row_queries(logged):
    owner = logged.get("/api/v1/users/me").json()["id"]
    _seed(owner)

    with _capture() as samples:
        documents = logged.get("/api/v1/documents", params={"pageSize": ROWS})
    assert documents.status_code == 200, documents.text
    assert len(documents.json()["items"]) == ROWS
    document_summary = _summary(samples)

    with _capture() as samples:
        notes = logged.get("/api/v1/notes", params={"pageSize": ROWS})
    assert notes.status_code == 200, notes.text
    assert len(notes.json()["items"]) == ROWS
    note_summary = _summary(samples)

    _assert_gate("GET /documents", document_summary, ROWS)
    _assert_gate("GET /notes", note_summary, ROWS)

    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps({
            "environment": {"database": "temporary SQLite", "rows": ROWS},
            "thresholds": {"maxSelects": MAX_SELECTS, "maxStatementMs": MAX_STATEMENT_MS},
            "documents": document_summary,
            "notes": note_summary,
        }, indent=2), encoding="utf-8")
    except OSError:
        pass
