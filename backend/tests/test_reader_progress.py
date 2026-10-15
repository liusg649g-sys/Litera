from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from app.database import SessionLocal
from app.main import app
from app.models import DocumentFile, ReadingProgress
from app import documents
from test_documents import logged, pdf, upload
from test_auth import register, login


def test_progress_compatibility_and_real_pdf_validation(logged, pdf):
    doc = upload(logged, pdf).json(); path = '/api/v1/documents/' + doc['id']
    assert logged.get(path + '/progress').json() == dict(documentId=doc['id'], pageNumber=None,
        zoom=None, viewMode='continuous', zoomMode='fit-width', lastReadAt=None, version=0)
    state = dict(pageNumber=1, zoom=5, zoomMode='custom', viewMode='spread', version=0)
    saved = logged.put(path + '/progress', json=state)
    assert saved.status_code == 200
    assert saved.json()['version'] == 1 and saved.json()['zoom'] == 5
    assert logged.get(path).json()['pageCount'] == 1
    assert logged.get(path).json()['version'] == 1
    assert logged.get(path + '/content?download=true').content == pdf
    for old in ({}, {'pageNumber': None, 'zoom': None}, {'version': 3}):
        response = logged.put(path + '/progress', json=old)
        assert response.status_code == 200
        assert response.json()['pageNumber'] == 1 and response.json()['zoom'] == 5
        assert response.json()['viewMode'] == 'spread'
    assert logged.put(path + '/progress', json=state).status_code == 409
    assert logged.put(path + '/progress', json={'zoom': .5, 'version': 4}).json()['zoom'] == .5
    opened_at = logged.get(path + '/progress').json()['lastReadAt']
    assert logged.put(path + '/progress', json={'zoom': 1, 'version': 5, 'recordOpen': False}).json()['lastReadAt'] == opened_at
    assert logged.get(path).json()['lastReadAt'] == opened_at


@pytest.mark.parametrize('values', [dict(pageNumber=0), dict(pageNumber=2), dict(pageNumber=True),
    dict(pageNumber=1.5), dict(pageNumber='1'), dict(zoom=.49), dict(zoom=5.01), dict(zoom=True),
    dict(zoom='1'), dict(viewMode='double'), dict(zoomMode='auto'), dict(viewMode=None), dict(zoomMode=None)])
def test_invalid_progress_is_atomic(logged, pdf, values):
    doc = upload(logged, pdf).json(); path = '/api/v1/documents/' + doc['id']
    response = logged.put(path + '/progress', json={'version': 0, **values})
    assert response.status_code == 422, response.text
    assert logged.get(path + '/progress').json()['version'] == 0
    assert logged.get('/api/v1/reading-history').json()['total'] == 0


def test_progress_owner_csrf_missing_file_and_session(logged, pdf):
    doc = upload(logged, pdf).json(); path = '/api/v1/documents/' + doc['id'] + '/progress'
    assert logged.put(path, json={'pageNumber': 1}).status_code == 422
    assert logged.put(path, json={}, headers={'Origin': 'http://evil.invalid'}).status_code == 403
    with TestClient(app, headers={'Origin': 'http://localhost:8080'}) as other:
        assert other.get(path).status_code == 401
        register(other, 'other@example.com'); other.headers['X-CSRF-Token'] = login(other, 'other@example.com').json()['csrfToken']
        assert other.get(path).status_code == 404
        assert other.put(path, json={'pageNumber': 1, 'version': 0}).status_code == 404
    with SessionLocal() as db:
        file = db.scalar(select(DocumentFile).where(DocumentFile.document_id == doc['id']))
        original = documents.storage_path(file.storage_key)
    with patch.object(Path, 'is_file', return_value=False):
        assert logged.put(path, json={}).status_code == 404
    with patch('app.library.PdfReader', side_effect=ValueError('corrupt')):
        assert logged.put(path, json={'version': 0, 'pageNumber': 1}).status_code == 422
    assert original.read_bytes() == pdf
    assert logged.get(path).json()['version'] == 0


def test_two_reader_cas_writers(logged, pdf):
    doc = upload(logged, pdf).json(); path = '/api/v1/documents/' + doc['id'] + '/progress'
    cookies = dict(logged.cookies); headers = dict(logged.headers)
    def send(zoom):
        with TestClient(app, headers=headers, cookies=cookies) as client:
            return client.put(path, json={'pageNumber': 1, 'zoom': zoom, 'version': 0}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(send, [1, 2])) == [200, 409]
    assert logged.get(path).json()['version'] == 1


def test_upgrade_from_0003_preserves_progress_and_original(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from app.config import get_settings
    url = 'sqlite:///' + str(tmp_path / 'reader-upgrade.db')
    monkeypatch.setattr(get_settings(), 'database_url', url)
    config = Config('alembic.ini'); command.upgrade(config, '0003_library')
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users VALUES ('owner','old@example.com','hash','Old',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        conn.execute(text("INSERT INTO documents (id,owner_id,title,authors,keywords,parse_status,version,created_at,updated_at) VALUES ('doc','owner','Old paper','[]','[]','not_requested',7,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        conn.execute(text("INSERT INTO reading_progress (document_id,owner_id,page_number,zoom,last_read_at,version) VALUES ('doc','owner',1,'1.25',CURRENT_TIMESTAMP,9)"))
    command.upgrade(config, 'head')
    with engine.connect() as conn:
        row = conn.execute(text('SELECT * FROM reading_progress')).mappings().one()
        assert row['version'] == 9 and row['zoom'] == '1.25' and row['page_number'] == 1
        assert row['view_mode'] is None and row['zoom_mode'] is None
        assert conn.execute(text("SELECT version FROM documents WHERE id='doc'")).scalar() == 7
    engine.dispose()


def test_mysql_incremental_ddl_compiles_without_connecting(monkeypatch, capsys):
    from alembic import command
    from alembic.config import Config
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), 'database_url', 'mysql+pymysql://test:unused@127.0.0.1/litera_test')
    command.upgrade(Config('alembic.ini'), '0003_library:0004_reader_progress', sql=True)
    ddl = capsys.readouterr().out
    assert 'ALTER TABLE reading_progress ADD COLUMN view_mode VARCHAR(16)' in ddl
    assert 'ALTER TABLE reading_progress ADD COLUMN zoom_mode VARCHAR(16)' in ddl
    assert 'DROP TABLE' not in ddl and 'CREATE TABLE' not in ddl
