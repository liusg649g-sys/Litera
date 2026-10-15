from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app import documents
from app.database import SessionLocal
from app.main import app
from app.models import Document, DocumentFile
from test_auth import register, login

@pytest.fixture
def pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=300)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()

@pytest.fixture
def logged(client):
    register(client)
    result = login(client).json()
    client.headers["X-CSRF-Token"] = result["csrfToken"]
    return client

def upload(client, data, name="论文.pdf"):
    return client.post("/api/v1/documents", files={"file": (name, data, "application/pdf")})

def test_upload_details_content_and_stable_id(logged, pdf):
    response = upload(logged, pdf)
    assert response.status_code == 201
    doc = response.json()
    assert doc["title"] == "论文" and doc["parseStatus"] == "not_requested"
    assert doc["authors"] == [] and doc["pageCount"] is None and doc["version"] == 1
    assert "storageKey" not in str(doc) and "ownerId" not in str(doc)
    assert logged.get("/api/v1/documents/" + doc["id"]).json() == doc
    assert logged.get("/api/v1/documents").json()["items"] == [doc]
    url = "/api/v1/documents/" + doc["id"] + "/content"
    content = logged.get(url)
    assert content.content == pdf and content.headers["content-type"] == "application/pdf"
    assert content.headers["content-disposition"].startswith("inline;")
    assert logged.get(url + "?download=true").headers["content-disposition"].startswith("attachment;")
    updated = logged.patch("/api/v1/documents/" + doc["id"], json={"version": 1, "title": " 新标题 ",
        "authors": [" 张三 "], "year": 2026, "abstract": "摘要", "keywords": ["科研"], "doi": "10.test/a"})
    assert updated.status_code == 200
    assert updated.json()["id"] == doc["id"] and updated.json()["version"] == 2
    assert updated.json()["title"] == "新标题" and updated.json()["authors"] == ["张三"]
    assert logged.get(url).content == pdf

@pytest.mark.parametrize("header,start,end", [("bytes=0-9", 0, 9), ("bytes=10-", 10, None), ("bytes=-8", -8, None), ("bytes=0-999999", 0, None)])
def test_ranges(logged, pdf, header, start, end):
    doc = upload(logged, pdf).json()
    response = logged.get(f'/api/v1/documents/{doc["id"]}/content', headers={"Range": header})
    assert response.status_code == 206
    assert response.content == pdf[start:end + 1 if end is not None else None]
    assert int(response.headers["content-length"]) == len(response.content)

@pytest.mark.parametrize("header", ["bytes=999999-", "bytes=-0", "bytes=10-1", "bytes=0-1,3-4", "invalid", "bytes=-", "bytes=" + "9" * 5000 + "-"])
def test_invalid_ranges(logged, pdf, header):
    doc = upload(logged, pdf).json()
    response = logged.get(f'/api/v1/documents/{doc["id"]}/content', headers={"Range": header})
    assert response.status_code == 416 and response.headers["content-range"] == f"bytes */{len(pdf)}"
    assert response.json()["error"]["code"] == "INVALID_RANGE"

def test_duplicate_including_deleted_and_cross_user(logged, pdf):
    doc = upload(logged, pdf).json()
    repeated = upload(logged, pdf, "另一个名字.pdf")
    assert repeated.status_code == 409
    assert repeated.json()["error"]["details"] == {"existingDocumentId": doc["id"], "inTrash": False}
    with SessionLocal() as db:
        db.get(Document, doc["id"]).deleted_at = datetime.now()
        db.commit()
    assert upload(logged, pdf).json()["error"]["details"]["inTrash"] is True
    assert logged.get(f'/api/v1/documents/{doc["id"]}/content').status_code == 404
    with TestClient(app, headers={"Origin": "http://localhost:8080"}) as other:
        register(other, "other@example.com")
        other.headers["X-CSRF-Token"] = login(other, "other@example.com").json()["csrfToken"]
        assert other.get("/api/v1/documents").json()["total"] == 0
        for suffix in ("", "/content"):
            assert other.get(f'/api/v1/documents/{doc["id"]}{suffix}').status_code == 404
        assert other.patch(f'/api/v1/documents/{doc["id"]}', json={"version": 1, "title": "越权"}).status_code == 404
        assert upload(other, pdf).status_code == 201

@pytest.mark.parametrize("payload", [{"title": ""}, {"title": None}, {"title": "   "}, {"year": 0},
    {"year": 10000}, {"year": 2.3}, {"authors": [" "]}, {"ownerId": "another"}, {"folderId": "other"}, {"tagIds": ["other"]}])
def test_invalid_edit(logged, pdf, payload):
    doc = upload(logged, pdf).json()
    response = logged.patch(f'/api/v1/documents/{doc["id"]}', json={"version": 1, **payload})
    assert response.status_code == (404 if {"folderId", "tagIds"} & set(payload) else 422)
    assert logged.get(f'/api/v1/documents/{doc["id"]}').json()["version"] == 1

def test_conflict_and_null_semantics(logged, pdf):
    doc = upload(logged, pdf).json()
    url = f'/api/v1/documents/{doc["id"]}'
    assert logged.patch(url, json={"version": 1, "year": 2020, "abstract": "a"}).status_code == 200
    assert logged.patch(url, json={"version": 1, "title": "旧版本"}).status_code == 409
    cleared = logged.patch(url, json={"version": 2, "year": None, "authors": None}).json()
    assert cleared["year"] is None and cleared["authors"] == [] and cleared["abstract"] == "a"

@pytest.mark.parametrize("data,name", [(b"hello", "test.pdf"), (b"%PDF-1.7 fake", "test.pdf"), (b"hello", "test.caj")])
def test_invalid_upload_no_resources(logged, data, name):
    assert upload(logged, data, name).status_code == 415
    assert logged.get("/api/v1/documents").json()["total"] == 0
    assert list(documents.settings.pdf_storage_root.iterdir()) == []

def test_encrypted_pdf_rejected(logged):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret")
    out = BytesIO()
    writer.write(out)
    assert upload(logged, out.getvalue()).json()["error"]["code"] == "ENCRYPTED_PDF"

def test_size_boundary_and_stream_bound(logged, pdf, monkeypatch):
    monkeypatch.setattr(documents.settings, "max_upload_bytes", len(pdf))
    assert upload(logged, pdf).status_code == 201
    assert upload(logged, pdf + b" ").status_code == 413
    # Larger than the envelope allowance, rejected during multipart ingestion.
    assert upload(logged, b"x" * (len(pdf) + 65537)).status_code == 413
    assert logged.get("/api/v1/library/config").json()["maxUploadBytes"] == len(pdf)

@pytest.mark.parametrize("fault", ["write", "publish", "flush", "commit"])
def test_disk_and_database_failure_compensation(logged, pdf, fault):
    if fault == "write":
        target, error = "app.documents.os.fsync", OSError("disk failure")
    elif fault == "publish":
        target, error = "app.documents.os.replace", OSError("publish failure")
    else:
        target, error = f"sqlalchemy.orm.Session.{fault}", OperationalError("statement", {}, Exception("DB failure"))
    with patch(target, side_effect=error):
        assert upload(logged, pdf).status_code == 500
    assert logged.get("/api/v1/documents").json()["total"] == 0
    assert list(documents.settings.pdf_storage_root.iterdir()) == []
    assert upload(logged, pdf).status_code == 201

def test_safe_filename_and_storage_path(logged, pdf):
    doc = upload(logged, pdf, "../../危险.pdf").json()
    assert doc["attachment"]["originalName"] == "危险.pdf"
    paths = list(documents.settings.pdf_storage_root.iterdir())
    assert [p.name for p in paths] == [doc["id"] + ".pdf"]
    with pytest.raises(ValueError):
        documents.storage_path("../outside.pdf")

def test_list_validation_stable_pagination_and_no_history(logged, pdf):
    ids = [upload(logged, pdf + b" " * i, f"文献{i}.pdf").json()["id"] for i in range(3)]
    one = logged.get("/api/v1/documents?sort=title&order=asc&pageSize=2").json()
    two = logged.get("/api/v1/documents?sort=title&order=asc&pageSize=2&page=2").json()
    assert one["total"] == two["total"] == 3
    assert [d["id"] for d in one["items"] + two["items"]] == ids
    assert all(d["lastReadAt"] is None for d in one["items"])
    assert logged.get("/api/v1/documents?page=99").json()["items"] == []
    for query in ("page=0", "pageSize=101", "sort=ownerId", "order=bad", "ownerId=another"):
        assert logged.get("/api/v1/documents?" + query).status_code == 422
    assert logged.get("/api/v1/documents?q=test").json()["total"] == 0

def test_auth_and_csrf_before_upload(client, pdf):
    assert upload(client, pdf).status_code == 401
    register(client)
    login(client)
    assert upload(client, pdf).status_code == 403
    assert client.get("/api/v1/documents").json()["total"] == 0

def test_upload_fields_and_openapi(logged, pdf):
    assert logged.post('/api/v1/documents', files={"file": ("a.pdf", pdf)}, data={"folderId": "other"}).status_code == 404
    assert logged.post('/api/v1/documents', files={"file": ("a.pdf", pdf)}, data={"ownerId": "other"}).status_code == 422
    assert logged.post('/api/v1/documents', json={"file": "fake"}).status_code == 415
    schema = logged.get('/api/openapi.json').json()
    assert schema['paths']['/api/v1/documents']['post']['requestBody']['content']['multipart/form-data']['schema']['properties']['file']['format'] == 'binary'

def test_concurrent_duplicate_single_file(logged, pdf):
    cookies = dict(logged.cookies)
    headers = dict(logged.headers)
    def submit(_):
        with TestClient(app, headers=headers, cookies=cookies) as caller:
            return upload(caller, pdf).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit, range(2))) == [201, 409]
    assert logged.get("/api/v1/documents").json()["total"] == 1
    assert len(list(documents.settings.pdf_storage_root.iterdir())) == 1

def test_concurrent_cas_only_one_writer(logged, pdf):
    doc = upload(logged, pdf).json()
    cookies, headers = dict(logged.cookies), dict(logged.headers)
    def edit(title):
        with TestClient(app, headers=headers, cookies=cookies) as caller:
            return caller.patch(f'/api/v1/documents/{doc["id"]}', json={"version": 1, "title": title}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit, ["A", "B"])) == [200, 409]
    assert logged.get(f'/api/v1/documents/{doc["id"]}').json()["version"] == 2

def test_commit_acknowledgement_loss_preserves_committed_file(logged, pdf):
    from sqlalchemy.orm import Session
    original = Session.commit
    def acknowledged_late(db):
        original(db)
        raise OperationalError("commit", {}, Exception("ack lost"))
    with patch("sqlalchemy.orm.Session.commit", acknowledged_late):
        assert upload(logged, pdf).status_code == 500
    doc = logged.get("/api/v1/documents").json()["items"][0]
    assert logged.get(f'/api/v1/documents/{doc["id"]}/content').content == pdf
    assert upload(logged, pdf).status_code == 409

def test_upgrade_from_auth_preserves_user(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    url = "sqlite:///" + str(tmp_path / "upgrade.db")
    monkeypatch.setattr(documents.settings, "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0001_auth")
    isolated = create_engine(url)
    with isolated.begin() as conn:
        conn.execute(text("INSERT INTO users (id,email,password_hash,display_name,created_at,updated_at) VALUES ('existing','existing@example.com','hash','Existing',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    command.upgrade(config, "head")
    with isolated.connect() as conn:
        assert conn.execute(text("SELECT display_name FROM users WHERE id='existing'")).scalar() == "Existing"
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0004_reader_progress"
    isolated.dispose()
