"""Error-handling gate: each outcome has an audit row (success / failed / denied).
The model call is a controlled local fixture; no real provider is contacted.
"""
from sqlalchemy import func, select

from app import translations
from app.ai_service import ModelFailure
from app.database import SessionLocal
from app.models import AuditLog
from test_documents import logged, pdf, upload  # noqa: F401  (pytest fixtures)

PAYLOAD = {"text": "A scientific paragraph.", "sourceLanguage": "en",
           "targetLanguage": "zh", "pageNumber": 1, "contextRevision": 1}


def _count(status, action=None):
    with SessionLocal() as db:
        query = select(func.count()).select_from(AuditLog).where(AuditLog.status == status)
        if action:
            query = query.where(AuditLog.action == action)
        return db.scalar(query)


def test_denied_request_is_audited(client):
    before = _count("denied")
    response = client.get("/api/v1/documents")
    assert response.status_code == 401
    assert _count("denied") == before + 1


def test_translation_success_and_failure_each_write_one_audit_row(logged, pdf, monkeypatch):
    document = upload(logged, pdf).json()
    url = f'/api/v1/documents/{document["id"]}/translations'

    async def success(*args, **kwargs):
        return "Mock translation"

    monkeypatch.setattr(translations, "translate_text", success)
    assert logged.post(url, json=PAYLOAD).status_code == 200
    assert _count("success", "translate") == 1

    async def failure(*args, **kwargs):
        raise ModelFailure("MODEL_TIMEOUT", "synthetic upstream timeout", 504)

    monkeypatch.setattr(translations, "translate_text", failure)
    rejected = logged.post(url, json=PAYLOAD)
    assert rejected.status_code == 504
    assert rejected.json()["error"]["code"] == "MODEL_TIMEOUT"
    assert _count("failed", "translate") == 1
