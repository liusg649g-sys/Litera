"""One continuous two-user Change 01/02 API journey; never a business database."""
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import Annotation, AnnotationCommandReceipt, DocumentReaderState, ReaderAsset
from test_auth import register, login
from test_documents import logged, upload
from test_annotations import command, data
from test_reader_assets import asset, object_data
from export_samples import KINDS


def test_two_user_full_journey_13_types_conflict_export_restore_and_cleanup(logged, monkeypatch):
    from app import metadata_extraction
    # This journey is about P3 reader/notes state, not automatic extraction; keep
    # the uploaded document at its initial version for the CAS assertions.
    monkeypatch.setattr(metadata_extraction, "run_sync_layers", lambda _reader: (_ for _ in ()).throw(RuntimeError("disabled")))
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=(200, 300))
    for page in range(3):
        canvas.drawString(20, 270, f'C2 integrated real text page {page + 1}')
        canvas.showPage()
    canvas.save()
    original = buffer.getvalue()
    doc = upload(logged, original, 'C2 journey.pdf').json()
    path = '/api/v1/documents/' + doc['id']
    folder = logged.post('/api/v1/folders', json={'name': 'C2 research'}).json()
    tag = logged.post('/api/v1/tags', json={'name': 'C2 verified'}).json()
    edited = logged.patch(path, json={'version': 1, 'folderId': folder['id'], 'tagIds': [tag['id']]}).json()
    assert edited['folderId'] == folder['id'] and edited['tags'] == [tag]
    assert logged.get('/api/v1/documents', params={'q': 'C2 journey'}).json()['total'] == 1
    assert logged.get(path + '/content', headers={'Range': 'bytes=0-99'}).content == original[:100]
    version = 0
    for mode in ('continuous', 'single', 'spread'):
        saved = logged.put(path + '/progress', json={'version': version, 'pageNumber': 2, 'zoom': 1.75, 'viewMode': mode, 'zoomMode': 'custom', 'recordOpen': mode == 'continuous'})
        assert saved.status_code == 200, saved.text
        version = saved.json()['version']
    revision = 0
    items = []
    for kind in KINDS:
        aid = asset(logged, path)['assetId'] if kind in ('image', 'signature') else None
        value = data(kind) if kind in KINDS[:6] else object_data(kind, aid)
        created = logged.post(path + '/annotations', json=command(revision, annotation=value))
        assert created.status_code == 201, created.text
        revision += 1
        item = created.json()['annotation']
        updated = logged.patch(path + '/annotations/' + item['id'], json=command(revision, version=item['version'], changes={'color': '#9B0000'}))
        assert updated.status_code == 200, updated.text
        revision += 1
        saved = updated.json()['annotation']
        # Actual persisted compensation: delete -> restore -> delete -> restore.
        for _ in range(2):
            assert logged.request('DELETE', path + '/annotations/' + saved['id'], json=command(revision, version=saved['version'])).status_code == 200
            revision += 1
            restored = logged.post(path + '/annotation-commands', json=command(revision, operation='restore', annotation=saved))
            assert restored.status_code == 200, restored.text
            revision += 1
            saved = restored.json()['annotation']
        items.append(saved)
    snapshot = logged.get(path + '/annotations').json()
    assert len(snapshot['items']) == 13 and snapshot['annotationRevision'] == revision
    assert logged.patch(path + '/annotations/' + items[0]['id'], json=command(0, version=1, changes={'color': '#123456'})).status_code == 409
    assert logged.get(path + '/annotations').json() == snapshot
    with TestClient(app, headers={'Origin': 'http://localhost:8080'}) as other:
        assert register(other, 'c2-other@example.com').status_code == 201
        other.headers['X-CSRF-Token'] = login(other, 'c2-other@example.com').json()['csrfToken']
        for suffix in ('', '/content', '/progress', '/annotations', '/reader-assets'):
            assert other.get(path + suffix).status_code == 404
        assert other.post(path + '/annotated-pdf', json={'expectedAnnotationRevision': revision}).status_code == 404
        assert other.post(path + '/annotations', json=command(revision, annotation=data('comment'))).status_code == 404
        assert other.get('/api/v1/documents').json()['total'] == 0
        export = logged.post(path + '/annotated-pdf', json={'expectedAnnotationRevision': revision})
        assert export.status_code == 200, export.text
        exported = PdfReader(BytesIO(export.content))
        assert len(exported.pages) == 3
        assert exported.metadata['/LiteraAnnotationRevision'] == str(revision)
        assert logged.get(path + '/content?download=true').content == original
        assert logged.delete(path).status_code == 204
        assert logged.get(path + '/annotations').status_code == 404
        assert logged.post(path + '/annotated-pdf', json={'expectedAnnotationRevision': revision}).status_code == 404
        assert other.post('/api/v1/trash/documents/' + doc['id'] + '/restore').status_code == 404
        assert logged.post('/api/v1/trash/documents/' + doc['id'] + '/restore').status_code == 200
        assert logged.get(path + '/annotations').json() == snapshot
        assert logged.get(path + '/progress').json()['pageNumber'] == 2
        assert logged.get(path + '/content').content == original
        assert logged.delete(path).status_code == 204
        with patch.object(Path, 'unlink', side_effect=PermissionError('C2 injected lock')):
            cleanup = logged.delete('/api/v1/trash/documents/' + doc['id'])
        assert cleanup.status_code == 202 and cleanup.json()['status'] == 'failed'
        job = cleanup.json()['jobId']
        assert other.post('/api/v1/cleanup-jobs/' + job + '/retry').status_code == 404
        assert logged.post('/api/v1/cleanup-jobs/' + job + '/retry').status_code == 204
        assert logged.get('/api/v1/cleanup-jobs/' + job).json()['status'] == 'completed'
    with SessionLocal() as db:
        for model in (Annotation, AnnotationCommandReceipt, DocumentReaderState, ReaderAsset):
            assert db.scalar(select(func.count()).select_from(model)) == 0
