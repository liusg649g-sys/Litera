from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.database import SessionLocal
from app.main import app
from app.models import CleanupJob, Document, DocumentFile, DocumentTag, ReadingProgress
from app import documents
from app.library import now
from test_auth import register, login
from test_documents import logged, pdf, upload

def create(client, path, name):
    response = client.post('/api/v1/' + path, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()

@pytest.mark.parametrize('path', ['folders', 'tags'])
def test_categories_validation_normalization_and_isolation(logged, path):
    item = create(logged, path, ' ＡBC ')
    assert item['name'] == 'ABC'
    assert logged.post('/api/v1/' + path, json={"name": 'abc'}).status_code == 409
    for value in ['', ' ', 'x' * 101, 'bad\nname']:
        assert logged.post('/api/v1/' + path, json={"name": value}).status_code == 422
    assert logged.patch(f'/api/v1/{path}/{item["id"]}', json={"name": '论文'}).json()['name'] == '论文'
    with TestClient(app, headers={"Origin": "http://localhost:8080"}) as other:
        register(other, 'other@example.com'); other.headers['X-CSRF-Token'] = login(other, 'other@example.com').json()['csrfToken']
        assert other.get('/api/v1/' + path).json() == []
        assert other.patch(f'/api/v1/{path}/{item["id"]}', json={"name": '越权'}).status_code == 404
        assert other.delete(f'/api/v1/{path}/{item["id"]}').status_code == 404
        assert create(other, path, '论文')['id'] != item['id']

def test_classification_deletion_keeps_active_and_trashed_documents(logged, pdf):
    folder = create(logged, 'folders', '研究'); tag = create(logged, 'tags', '视觉')
    doc = logged.post('/api/v1/documents', files={'file': ('a.pdf', pdf)}, data={'folderId': folder['id']}).json()
    assert doc['folderId'] == folder['id']
    edited = logged.patch('/api/v1/documents/' + doc['id'], json={'version': 1, 'tagIds': [tag['id'], tag['id']]}).json()
    assert edited['tags'] == [tag]
    assert logged.patch('/api/v1/documents/' + doc['id'], json={'version': 1, 'tagIds': []}).status_code == 409
    assert logged.delete('/api/v1/documents/' + doc['id']).status_code == 204
    assert logged.delete('/api/v1/folders/' + folder['id']).status_code == 204
    assert logged.delete('/api/v1/tags/' + tag['id']).status_code == 204
    restored = logged.post('/api/v1/trash/documents/' + doc['id'] + '/restore').json()
    assert restored['id'] == doc['id'] and restored['folderId'] is None and restored['tags'] == []
    assert logged.get('/api/v1/documents/' + doc['id'] + '/content').content == pdf

def test_cross_owner_associations_and_csrf(logged, pdf):
    doc = upload(logged, pdf).json()
    with TestClient(app, headers={'Origin': 'http://localhost:8080'}) as other:
        register(other, 'other@example.com'); other.headers['X-CSRF-Token'] = login(other, 'other@example.com').json()['csrfToken']
        folder = create(other, 'folders', '他人'); tag = create(other, 'tags', '他人')
        for data in ({'folderId': folder['id']}, {'tagIds': [tag['id']]}):
            assert logged.patch('/api/v1/documents/' + doc['id'], json={'version': 1, **data}).status_code == 404
        assert logged.post('/api/v1/documents', files={'file': ('b.pdf', pdf + b' ')}, data={'folderId': folder['id']}).status_code == 404
        for method, suffix in [('delete', '/documents/' + doc['id']), ('put', '/documents/' + doc['id'] + '/progress'), ('post', '/trash/documents/' + doc['id'] + '/restore')]:
            assert getattr(other, method)('/api/v1' + suffix, **({'json': {}} if method == 'put' else {})).status_code == 404
    assert logged.post('/api/v1/folders', json={'name': '新'}, headers={'Origin': 'http://evil.invalid'}).status_code == 403
    assert logged.get('/api/v1/documents/' + doc['id']).json()['version'] == 1

def test_combined_search_all_tags_and_stable_pages(logged, pdf):
    folder = create(logged, 'folders', '论文'); a = create(logged, 'tags', '一'); b = create(logged, 'tags', '二')
    ids = []
    for i in range(4):
        doc = upload(logged, pdf + b' ' * i, f'{i}.pdf').json(); ids.append(doc['id'])
        response = logged.patch('/api/v1/documents/' + doc['id'], json={'version': 1, 'authors': ['王小明'],
            'title': f'视觉{i}', 'year': 2020 + i, 'folderId': folder['id'], 'tagIds': [a['id'], b['id']] if i < 3 else [a['id']]})
        assert response.status_code == 200
    query = f"q=王小明&folderId={folder['id']}&tagIds={a['id']},{b['id']}&yearFrom=2021&yearTo=2023&sort=year&order=asc&pageSize=1"
    first = logged.get('/api/v1/documents?' + query).json()
    second = logged.get('/api/v1/documents?' + query + '&page=2').json()
    assert first['total'] == second['total'] == 2
    assert [first['items'][0]['id'], second['items'][0]['id']] == ids[1:3]
    assert logged.get('/api/v1/documents?q=%25').json()['total'] == 0
    for query in ['yearFrom=2026&yearTo=2020', 'yearFrom=abc', 'yearTo=0', 'q=' + 'x' * 501, 'tagIds=,', 'page=1&page=2', 'folderId=other']:
        assert logged.get('/api/v1/documents?' + query).status_code in (422, 404)

def test_reading_history_only_explicit_opens_and_no_duplicate_records(logged, pdf):
    a = upload(logged, pdf).json(); b = upload(logged, pdf + b' ').json()
    assert logged.get('/api/v1/documents/' + a['id'] + '/progress').json()['version'] == 0
    logged.get('/api/v1/documents/' + a['id'] + '/content')
    assert logged.get('/api/v1/reading-history').json()['total'] == 0
    for doc in (a, b, a):
        assert logged.put('/api/v1/documents/' + doc['id'] + '/progress', json={}).status_code == 200
    history = logged.get('/api/v1/reading-history').json()
    assert [item['document']['id'] for item in history['items']] == [a['id'], b['id']]
    assert history['items'][0]['progress']['version'] == 2
    assert logged.put('/api/v1/documents/' + a['id'] + '/progress', json={'version': 0}).status_code == 409
    assert logged.put('/api/v1/documents/' + a['id'] + '/progress', json={'pageNumber': 1, 'version': 2}).status_code == 200
    logged.delete('/api/v1/documents/' + a['id'])
    assert logged.get('/api/v1/reading-history').json()['total'] == 1

def test_full_lifecycle_and_durable_cleanup_failure_retry(logged, pdf):
    folder = create(logged, 'folders', '分类'); tag = create(logged, 'tags', '标签')
    doc = upload(logged, pdf).json(); id = doc['id']; url = '/api/v1/documents/' + id
    logged.patch(url, json={'version': 1, 'folderId': folder['id'], 'tagIds': [tag['id']], 'title': '原题录'})
    logged.put(url + '/progress', json={})
    assert logged.delete(url).status_code == logged.delete(url).status_code == 204
    for suffix in ('', '/content', '/progress'):
        assert logged.get(url + suffix).status_code == 404
    assert upload(logged, pdf).json()['error']['details']['inTrash']
    restored = logged.post('/api/v1/trash/documents/' + id + '/restore').json()
    assert restored['folderId'] == folder['id'] and restored['tags'] == [tag] and restored['title'] == '原题录'
    assert logged.get(url + '/content').content == pdf
    logged.delete(url)
    trash_url = '/api/v1/trash/documents/' + id
    with patch.object(Path, 'unlink', side_effect=PermissionError('locked file')):
        failed = logged.delete(trash_url)
    assert failed.status_code == 202 and failed.json()['status'] == 'failed'
    job = failed.json()['jobId']
    assert logged.get('/api/v1/cleanup-jobs/' + job).json()['errorCode'] == 'CLEANUP_FAILED'
    assert logged.get('/api/v1/trash/documents').json()['items'][0]['cleanupJob']['jobId'] == job
    assert logged.post(trash_url + '/restore').status_code == 409
    assert (documents.settings.pdf_storage_root / (id + '.pdf')).exists()
    with TestClient(app, headers={'Origin': 'http://localhost:8080'}) as other:
        register(other, 'other@example.com'); other.headers['X-CSRF-Token'] = login(other, 'other@example.com').json()['csrfToken']
        assert other.get('/api/v1/cleanup-jobs/' + job).status_code == 404
        assert other.post('/api/v1/cleanup-jobs/' + job + '/retry').status_code == 404
        assert other.delete(trash_url).status_code == 404
    assert logged.post('/api/v1/cleanup-jobs/' + job + '/retry').status_code == 204
    assert logged.get('/api/v1/cleanup-jobs/' + job).json()['status'] == 'completed'
    assert logged.post('/api/v1/cleanup-jobs/' + job + '/retry').status_code == 204
    assert logged.get(url).status_code == 404 and logged.get('/api/v1/trash/documents').json()['total'] == 0
    assert not (documents.settings.pdf_storage_root / (id + '.pdf')).exists()
    with SessionLocal() as db:
        for model in (Document, DocumentFile, DocumentTag, ReadingProgress):
            assert db.scalar(select(func.count()).select_from(model)) == 0
    assert upload(logged, pdf).status_code == 201

def test_cleanup_recovers_expired_running_job(logged, pdf):
    doc = upload(logged, pdf).json(); id = doc['id']; logged.delete('/api/v1/documents/' + id)
    with patch.object(Path, 'unlink', side_effect=PermissionError()):
        job_id = logged.delete('/api/v1/trash/documents/' + id).json()['jobId']
    with SessionLocal() as db:
        job = db.get(CleanupJob, job_id); job.status = 'running'; job.lease_expires_at = now() + timedelta(seconds=60); db.commit()
    assert logged.post('/api/v1/cleanup-jobs/' + job_id + '/retry').json()['status'] == 'running'
    with SessionLocal() as db:
        db.get(CleanupJob, job_id).lease_expires_at = now() - timedelta(seconds=1); db.commit()
    assert logged.post('/api/v1/cleanup-jobs/' + job_id + '/retry').status_code == 204

def test_upgrade_p2a_preserves_document_id_metadata_and_file_key(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, text
    url = 'sqlite:///' + str(tmp_path / 'p2a-upgrade.db')
    monkeypatch.setattr(documents.settings, 'database_url', url)
    config = Config('alembic.ini'); command.upgrade(config, '0002_documents')
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users VALUES ('owner','upgrade@example.com','hash','升级用户',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO documents (id,owner_id,title,authors,keywords,version,parse_status,created_at,updated_at) VALUES ('stable','owner','旧文献','[]','[]',7,'not_requested',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO document_files VALUES ('file','stable','owner','old.pdf','stable.pdf','digest',128,'application/pdf')"))
    command.upgrade(config, 'head')
    with engine.connect() as connection:
        row = connection.execute(text("SELECT id,title,version,folder_id,last_read_at,purge_job_id FROM documents")).one()
        assert tuple(row) == ('stable', '旧文献', 7, None, None, None)
        assert connection.execute(text('SELECT storage_key FROM document_files')).scalar() == 'stable.pdf'
        assert any(fk['referred_table'] == 'folders' for fk in inspect(engine).get_foreign_keys('documents'))
    engine.dispose()

def test_concurrent_first_opens_and_retries_are_serialized(logged, pdf):
    doc = upload(logged, pdf).json(); id = doc['id']
    cookies = dict(logged.cookies); csrf = logged.headers['X-CSRF-Token']
    def send(path):
        with TestClient(app, headers={'Origin': 'http://localhost:8080', 'X-CSRF-Token': csrf}, cookies=cookies) as client:
            return client.put(path, json={}) if path.endswith('/progress') else client.post(path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(send, ['/api/v1/documents/' + id + '/progress'] * 2))
    assert [response.status_code for response in responses] == [200, 200]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ReadingProgress)) == 1
        assert db.get(ReadingProgress, id).version == 2
    logged.delete('/api/v1/documents/' + id)
    with patch.object(Path, 'unlink', side_effect=PermissionError()):
        job = logged.delete('/api/v1/trash/documents/' + id).json()['jobId']
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(send, ['/api/v1/cleanup-jobs/' + job + '/retry'] * 2))
    assert all(response.status_code in (204, 202) for response in responses)
    assert logged.get('/api/v1/cleanup-jobs/' + job).json()['status'] == 'completed'
