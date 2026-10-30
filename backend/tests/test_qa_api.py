"""QA contract tests: HTTP envelope, citation verification, caching and lifecycle.

Isolated SQLite + synthetic rows; the model transport is replaced by a scripted
fake. No external gateway call and no real PDF is read.
"""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app import qa, rag
from app.ai_service import ModelFailure, ModelProfile
from app.database import SessionLocal
from app.models import Document, DocumentChunk, DocumentFile, QaAnswer, QaChunkVector, QaIndex
from test_documents import logged  # noqa: F401  (fixture)


CHUNKS = (
    ("c1", 1, 0, "引言 Lorem 研究背景，本文研究图神经网络。"),
    ("c2", 1, 12, "方法 Method 部分描述训练流程与损失函数。"),
    ("c3", 2, 0, "结果 Results 准确率提升。"),
    ("c4", 2, 10, "结论 Conclusion 本文方法有效。"),
)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def make_document(client, *, version="v1", parse_status="completed", index=None):
    owner = client.get("/api/v1/auth/session").json()["user"]["id"]
    document_id = str(uuid.uuid4())
    sha = uuid.uuid4().hex + uuid.uuid4().hex
    now = _now()
    ids = {label: str(uuid.uuid4()) for label, *_ in CHUNKS}
    with SessionLocal() as db:
        db.add(Document(id=document_id, owner_id=owner, title="QA fixture", authors=[], keywords=[],
                        version=1, parse_status=parse_status, extraction_version=version,
                        page_count=2, created_at=now, updated_at=now))
        db.add(DocumentFile(id=str(uuid.uuid4()), document_id=document_id, owner_id=owner,
                            original_name="qa.pdf", storage_key=str(uuid.uuid4()) + ".pdf",
                            sha256=sha, size_bytes=8, mime_type="application/pdf"))
        for label, page, offset, text in CHUNKS:
            db.add(DocumentChunk(id=ids[label], owner_id=owner, document_id=document_id,
                                 extraction_version=version, page_number=page,
                                 start_offset=offset, end_offset=offset + len(text), text=text))
        if index:
            db.add(QaIndex(id=str(uuid.uuid4()), owner_id=owner, document_id=document_id,
                           extraction_version=version, embedding_model="course-embedding",
                           dimension=4, status=index, chunk_count=len(CHUNKS),
                           is_active=index == "ready", created_at=now, updated_at=now))
            if index == "ready":
                for label, page, _, _ in CHUNKS:
                    db.add(QaChunkVector(id=str(uuid.uuid4()), owner_id=owner,
                                         document_id=document_id, extraction_version=version,
                                         chunk_id=ids[label], page_number=page,
                                         vector=rag.encode_vector([1.0, 0.0, 0.0, 0.0]),
                                         dimension=4, created_at=now))
        db.commit()
    return document_id, owner, sha, version, ids


class FakeModel:
    def __init__(self):
        self.embed_calls = 0
        self.complete_calls = 0
        self.replies = []
        self.error = None
        self.messages = []

    async def embed(self, texts, principal, profile):
        self.embed_calls += 1
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    async def complete(self, messages, principal, profile):
        self.complete_calls += 1
        self.messages.append(messages)
        if self.error:
            raise self.error
        assert self.replies, "unscripted model call"
        return self.replies.pop(0)


def profile(principal, capability):
    return ModelProfile(provider="openai_compatible", base_url="https://example.invalid/v1",
                        model="course-embedding" if capability == "embedding" else "course-chat",
                        api_key=SecretStr("unit-test-placeholder"), verified=True)


@pytest.fixture
def fake(monkeypatch):
    model = FakeModel()
    monkeypatch.setattr(qa, "model_service", lambda: model)
    monkeypatch.setattr(qa, "developer_profile", profile)
    return model


def switch_user(client, email="other@example.com"):
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456789",
                                               "displayName": "other"})
    data = client.post("/api/v1/auth/login",
                       json={"email": email, "password": "123456789"}).json()
    client.headers["X-CSRF-Token"] = data["csrfToken"]
    return data["user"]["id"]


def ask(client, document_id, **body):
    payload = {"mode": "question", "question": "本文方法有效吗？"}
    payload.update(body)
    return client.post(f"/api/v1/documents/{document_id}/qa", json=payload)


def test_empty_question_is_422_without_retrieval_or_model(logged, fake, monkeypatch):
    monkeypatch.setattr(rag, "trigger_index_build", lambda *args: False)
    document_id, *_ = make_document(logged)
    response = ask(logged, document_id, question="   ")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "QA_QUESTION_REQUIRED"
    assert fake.embed_calls == 0 and fake.complete_calls == 0


def test_other_users_document_is_404(logged):
    document_id, *_ = make_document(logged, index="ready")
    switch_user(logged)
    assert ask(logged, document_id).status_code == 404
    assert ask(logged, str(uuid.uuid4())).status_code == 404


def test_unready_extraction_and_index_states(logged, fake, monkeypatch):
    monkeypatch.setattr(rag, "trigger_index_build", lambda *args: False)
    document_id, *_ = make_document(logged, parse_status="processing")
    assert ask(logged, document_id).json()["error"]["code"] == "EXTRACTION_NOT_READY"
    document_id, *_ = make_document(logged, index="building")
    assert ask(logged, document_id).json()["error"]["code"] == "QA_INDEX_BUILDING"
    document_id, *_ = make_document(logged, index="failed")
    assert ask(logged, document_id).json()["error"]["code"] == "QA_INDEX_FAILED"
    assert fake.embed_calls == 0


def test_model_timeout_and_quota_map_to_standard_errors(logged, fake):
    document_id, *_ = make_document(logged, index="ready")
    fake.error = ModelFailure("MODEL_TIMEOUT", "模型超时", 504)
    response = ask(logged, document_id)
    assert response.status_code == 504 and response.json()["error"]["code"] == "MODEL_TIMEOUT"
    fake.error = ModelFailure("MODEL_QUOTA", "额度不足", 429)
    response = ask(logged, document_id)
    assert response.status_code == 429 and response.json()["error"]["code"] == "MODEL_QUOTA_LIMITED"


def test_fabricated_or_out_of_range_citation_is_not_published(logged, fake):
    document_id, *_ = make_document(logged, index="ready")
    fake.replies = ['{"sufficient": true, "answer": "答案[9]", "used": [9]}']
    response = ask(logged, document_id)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_evidence"
    assert body["citations"] == []
    assert "答案[9]" not in body["answer"]


def test_valid_citation_is_built_from_chunk_metadata(logged, fake):
    document_id, _, _, _, ids = make_document(logged, index="ready")
    fake.replies = ['{"sufficient": true, "answer": "本文方法有效[4]", "used": [4]}']
    response = ask(logged, document_id)
    body = response.json()
    assert response.status_code == 200 and body["status"] == "answered"
    assert len(body["citations"]) == 1
    citation = body["citations"][0]
    assert citation["chunkId"] == ids["c4"] and citation["pageNumber"] == 2
    assert citation["quote"] == "结论 Conclusion 本文方法有效。"
    assert citation["extractionVersion"] == "v1" and citation["documentId"] == document_id
    assert "[4]" in body["answer"]


def test_page_limited_question_only_accepts_that_page(logged, fake):
    document_id, *_ = make_document(logged, index="ready")
    fake.replies = ['{"sufficient": true, "answer": "见本页[1]", "used": [7]}']
    response = ask(logged, document_id, pageNumber=1)
    assert response.json()["status"] == "insufficient_evidence"
    fake.replies = ['{"sufficient": true, "answer": "见本页[1]", "used": [1]}']
    body = ask(logged, document_id, pageNumber=1).json()
    assert body["status"] == "answered" and body["citations"][0]["pageNumber"] == 1


def test_invalid_json_is_repaired_once_then_fails(logged, fake):
    document_id, *_ = make_document(logged, index="ready")
    fake.replies = ["not json at all", "still not json"]
    response = ask(logged, document_id)
    assert response.status_code == 502 and response.json()["error"]["code"] == "MODEL_FAILED"
    assert fake.complete_calls == 2


def test_summary_is_cached_per_extraction_version(logged, fake):
    document_id, *_ = make_document(logged, index="ready")
    fake.replies = ['{"sufficient": true, "answer": "摘要[1]", "used": [1]}']
    first = ask(logged, document_id, mode="summary").json()
    assert first["status"] == "answered" and first["cached"] is False and first["citations"]
    second = ask(logged, document_id, mode="summary").json()
    assert second["answerId"] == first["answerId"] and second["cached"] is True
    assert fake.complete_calls == 1


def test_analysis_sections_keep_all_keys_and_drop_unsupported_ones(logged, fake):
    document_id, *_ = make_document(logged, index="ready")
    fake.replies = ['{"sufficient": true, "answer": "摘要[1]", "used": [1], "sections": ['
                    '{"key": "background", "text": "背景[1]", "used": [1]},'
                    '{"key": "method", "text": "方法[2]", "used": [2]},'
                    '{"key": "results", "text": "伪造[99]", "used": [99]},'
                    '{"key": "conclusion", "text": "结论[4]", "used": [4]}]}']
    body = ask(logged, document_id, mode="analysis").json()
    assert body["status"] == "answered"
    assert [section["key"] for section in body["sections"]] == \
        ["background", "method", "results", "conclusion"]
    results = next(section for section in body["sections"] if section["key"] == "results")
    assert results["text"] == "未找到对应证据" and results["citations"] == []
    assert all(section["citations"] for section in body["sections"]
               if section["key"] in ("background", "method", "conclusion"))


def test_answer_retrieval_is_owner_scoped(logged, fake):
    document_id, *_ = make_document(logged, index="ready")
    fake.replies = ['{"sufficient": true, "answer": "答案[1]", "used": [1]}']
    answer_id = ask(logged, document_id).json()["answerId"]
    own = logged.get(f"/api/v1/documents/{document_id}/qa/{answer_id}")
    assert own.status_code == 200 and own.json()["cached"] is True
    switch_user(logged)
    assert logged.get(f"/api/v1/documents/{document_id}/qa/{answer_id}").status_code == 404
    assert logged.get(f"/api/v1/documents/{document_id}/qa/not-a-uuid").status_code == 404


def test_old_version_citations_remain_verifiable_after_reparse(logged, fake):
    document_id, owner, sha, version, _ = make_document(logged, index="ready")
    fake.replies = ['{"sufficient": true, "answer": "答案[3]", "used": [3]}']
    body = ask(logged, document_id).json()
    citation = body["citations"][0]
    with SessionLocal() as db:
        document = db.get(Document, document_id)
        document.extraction_version = "v2"
        for _, page, offset, text in CHUNKS:
            db.add(DocumentChunk(id=str(uuid.uuid4()), owner_id=owner, document_id=document_id,
                                 extraction_version="v2", page_number=page,
                                 start_offset=offset, end_offset=offset + len(text), text=text))
        db.commit()
    resolver = qa.QaAnswerResolver()
    with SessionLocal() as db:
        record = resolver.resolve(db, owner, body["answerId"], body["answerRevision"])
        assert record.extractionVersion == version
        from app.answer_sources import AnswerCitation
        assert resolver.verify_citation(db, owner, record, AnswerCitation(**citation, fileSha256=sha)) is True
        assert record.evidenceState == "verified"


def test_soft_delete_blocks_and_purge_removes_qa_rows(logged, fake):
    document_id, owner, sha, version, _ = make_document(logged, index="ready")
    fake.replies = ['{"sufficient": true, "answer": "答案[1]", "used": [1]}']
    answer_id = ask(logged, document_id).json()["answerId"]
    assert logged.delete(f"/api/v1/documents/{document_id}").status_code == 204
    assert ask(logged, document_id).status_code == 404
    assert logged.delete(f"/api/v1/trash/documents/{document_id}").status_code == 204
    with SessionLocal() as db:
        assert db.get(QaAnswer, answer_id) is None
        assert db.scalar(select(QaIndex).where(QaIndex.document_id == document_id)) is None
        assert db.scalar(select(QaChunkVector).where(QaChunkVector.document_id == document_id)) is None
