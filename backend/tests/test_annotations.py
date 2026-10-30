"""B1 real HTTP/database tests. SQLite by default; TEST_DATABASE_URL enables MySQL."""
import copy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.database import SessionLocal
from app.main import app
from app.models import Annotation, AnnotationCommandReceipt, DocumentReaderState
from test_auth import register, login
from test_documents import logged, pdf, upload


def data(kind="highlight"):
    pos = [{"pageNumber": 1, "rects": [{"x": .1, "y": .2, "width": .3, "height": .04}, {"x": .1, "y": .25, "width": .2, "height": .04}], "textQuote": "Real PDF text"}]
    geometry = {"kind": "box", "pageNumber": 1, "rect": {"x": .1, "y": .2, "width": .3, "height": .1}, "rotation": 0} if kind == "freeText" else {"kind": "anchor", "pageNumber": 1, "x": .1, "y": .2} if kind == "comment" else {"kind": "text", "positions": pos}
    return dict(id=str(uuid.uuid4()), type=kind, schemaVersion=1, pageNumber=1,
        position=pos if geometry['kind'] == 'text' else None, geometry=geometry,
        selectedText="Real PDF text" if geometry['kind'] == 'text' else None,
        content="中文正文\n第二行" if kind in ("comment", "freeText") else None,
        color="#F5D547", style={"opacity": .35, "fontSize": 14, "lineWidth": 1}, assetId=None, zIndex=0)


def command(revision=0, **kwargs):
    return dict(commandId=str(uuid.uuid4()), baseRevision=revision, **kwargs)


def test_character_offsets_roundtrip_and_legacy_geometry(logged, pdf):
    doc = upload(logged, pdf).json(); path = '/api/v1/documents/' + doc['id']
    value = data()
    value['position'][0]['rects'][0]['baseline'] = .8
    value['position'][0]['textRanges'] = [{'item': 2, 'start': 3, 'end': 8}]
    result = logged.post(path+'/annotations', json=command(annotation=value))
    assert result.status_code == 201, result.text
    assert logged.get(path+'/annotations').json()['items'][0]['position'] == value['position']
    invalid = data(); invalid['position'][0]['textRanges'] = [{'item': 1, 'start': 8, 'end': 3}]
    assert logged.post(path+'/annotations', json=command(1, annotation=invalid)).status_code == 422
    legacy = data()
    created = logged.post(path+'/annotations', json=command(1, annotation=legacy)).json()['annotation']
    assert created['position'] == legacy['position']
    assert logged.request('DELETE', path+'/annotations/'+created['id'], json=command(2,version=created['version'])).status_code == 200
    assert logged.post(path+'/annotation-commands', json=command(3,operation='restore',annotation=created)).status_code == 200


@pytest.mark.parametrize('kind', ['highlight', 'underline', 'squiggly', 'strikeout', 'comment', 'freeText'])
def test_six_types_crud_idempotency_and_real_compensation(logged, pdf, kind):
    doc = upload(logged, pdf).json(); path = '/api/v1/documents/' + doc['id']
    assert logged.get(path + '/annotations').json() == dict(items=[], annotationRevision=0)
    body = command(annotation=data(kind))
    response = logged.post(path + '/annotations', json=body)
    assert response.status_code == 201, response.text
    created = response.json(); item = created['annotation']; aid = item['id']
    assert created['annotationRevision'] == 1 and item['version'] == 1
    assert logged.post(path + '/annotations', json=body).json() == created
    assert logged.get(path + '/annotation-commands/' + body['commandId']).json() == created
    assert logged.get(path + '/annotations?pageNumber=1').json()['items'] == [item]
    assert logged.get(path + '/annotations?pageNumber=2').json()['items'] == []
    reused = {**body, 'annotation': {**body['annotation'], 'color': '#123456'}}
    assert logged.post(path + '/annotations', json=reused).status_code == 409
    changed = logged.patch(path + '/annotations/' + aid, json=command(1, version=1, changes={'color': '#123456', 'content': '更新正文', 'style': {'fontSize': 24, 'opacity': .8, 'lineWidth': 2}}))
    assert changed.status_code == 200, changed.text
    saved = changed.json()['annotation']; assert saved['version'] == 2 and saved['color'] == '#123456'
    deletion = command(2, version=2)
    assert logged.request('DELETE', path + '/annotations/' + aid, json=deletion).json()['annotationRevision'] == 3
    assert logged.request('DELETE', path + '/annotations/' + aid, json=deletion).status_code == 200
    assert logged.get(path + '/annotations').json()['items'] == []
    restored = logged.post(path + '/annotation-commands', json=command(3, operation='restore', annotation=saved))
    assert restored.status_code == 200, restored.text
    assert restored.json()['annotation']['version'] == 4
    assert restored.json()['annotation']['content'] == '更新正文'
    assert logged.get(path).json()['version'] == 1
    assert logged.get(path + '/progress').json()['version'] == 0
    assert logged.get(path + '/content?download=true').content == pdf


@pytest.mark.parametrize('change', [dict(pageNumber=2), dict(type='ink'), dict(schemaVersion=2), dict(color='red'),
    dict(color='#12345678'), dict(content='x'*20001), dict(assetId='asset'), dict(ownerId='other'),
    dict(pageNumber=True), dict(style={'fontSize': 0}), dict(style={'evil': 'script'}),
    dict(geometry={'kind':'anchor','pageNumber':1,'x':.2,'y':.2}),
    dict(position=None), dict(selectedText=''), dict(zIndex=-1)])
def test_validation_is_atomic(logged, pdf, change):
    doc = upload(logged, pdf).json(); path = '/api/v1/documents/' + doc['id']
    body = command(annotation={**data(), **change})
    response = logged.post(path+'/annotations', json=body)
    assert response.status_code == 422, response.text
    assert logged.get(path+'/annotations').json() == dict(items=[], annotationRevision=0)
    assert logged.get(path+'/annotation-commands/'+body['commandId']).status_code == 404


def test_bounds_nested_page_and_object_cas(logged, pdf):
    doc=upload(logged,pdf).json(); path='/api/v1/documents/'+doc['id']
    for invalid in ('bounds','page'):
        value=data()
        if invalid=='bounds': value['position'][0]['rects'][0]['width']=.95
        else: value['position'].append({**copy.deepcopy(value['position'][0]),'pageNumber':2})
        value['geometry']['positions']=value['position']
        assert logged.post(path+'/annotations',json=command(annotation=value)).status_code==422
        assert logged.get(path+'/annotations').json()['annotationRevision']==0
    item=logged.post(path+'/annotations',json=command(annotation=data())).json()['annotation']
    for revision, version in ((0,1),(1,3)):
        assert logged.patch(path+'/annotations/'+item['id'],json=command(revision,version=version,changes={'color':'#123456'})).status_code==409
    assert logged.patch(path+'/annotations/'+item['id'],json=command(1,version=1,changes={'type':'comment'})).status_code==422
    assert logged.patch(path+'/annotations/'+item['id'],json=command(1,version=1,changes={'geometry':item['geometry']})).status_code==422
    assert logged.get(path+'/annotations').json()['items']==[item]


def test_owner_document_csrf_and_lifecycle(logged, pdf):
    doc=upload(logged,pdf).json(); path='/api/v1/documents/'+doc['id']
    body=command(annotation=data('comment')); item=logged.post(path+'/annotations',json=body).json()['annotation']
    # Another document with distinct PDF bytes, same owner.
    other_doc=upload(logged,pdf+b'\n%other').json(); other_path='/api/v1/documents/'+other_doc['id']
    assert logged.patch(other_path+'/annotations/'+item['id'],json=command(version=1,changes={'color':'#123456'})).status_code==404
    assert logged.get(other_path+'/annotation-commands/'+body['commandId']).status_code==404
    assert logged.post(path+'/annotations',json=command(annotation=data()),headers={'Origin':'https://evil.invalid'}).status_code==403
    assert logged.post(path+'/annotations',json=command(annotation=data()),headers={'X-CSRF-Token':''}).status_code==403
    with TestClient(app,headers={'Origin':'http://localhost:8080'}) as other:
        assert other.get(path+'/annotations').status_code==401
        register(other,'second@example.com'); other.headers['X-CSRF-Token']=login(other,'second@example.com').json()['csrfToken']
        for suffix in ('/annotations','/annotation-commands/'+body['commandId']): assert other.get(path+suffix).status_code==404
        assert other.patch(path+'/annotations/'+item['id'],json=command(1,version=1,changes={'content':'stolen'})).status_code==404
        assert other.request('DELETE',path+'/annotations/'+item['id'],json=command(1,version=1)).status_code==404
        assert other.post(path+'/annotation-commands',json=command(1,operation='restore',annotation=item)).status_code==404
    assert logged.delete(path).status_code==204
    assert logged.get(path+'/annotations').status_code==404
    assert logged.post(path+'/annotations',json=command(1,annotation=data())).status_code==404
    assert logged.post('/api/v1/trash/documents/'+doc['id']+'/restore').status_code==200
    assert logged.get(path+'/annotations').json()['items']==[item]
    logged.delete(path)
    # DB cleanup failure is visible/retryable through the existing job.
    with patch('app.library.storage_path') as storage:
        storage.return_value.unlink.side_effect=OSError('injected')
        failed=logged.delete('/api/v1/trash/documents/'+doc['id'])
    assert failed.status_code==202
    job=failed.json()['jobId']
    assert logged.get('/api/v1/cleanup-jobs/'+job).json()['status']=='failed'
    with SessionLocal() as db: assert db.get(Annotation,item['id']) is not None
    assert logged.post('/api/v1/cleanup-jobs/'+job+'/retry').status_code==204
    with SessionLocal() as db:
        assert db.get(Annotation,item['id']) is None
        assert db.get(DocumentReaderState,doc['id']) is None
        assert db.get(AnnotationCommandReceipt,(doc['id'],body['commandId'])) is None


def test_concurrent_collection_writers_have_one_winner(logged, pdf):
    doc=upload(logged,pdf).json(); path='/api/v1/documents/'+doc['id']
    cookies=dict(logged.cookies); headers=dict(logged.headers)
    def write():
        with TestClient(app,headers=headers,cookies=cookies) as client:
            return client.post(path+'/annotations',json=command(annotation=data())).status_code
    with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(lambda _:write(),range(2)))
    assert sorted(statuses)==[201,409]
    assert len(logged.get(path+'/annotations').json()['items'])==1


def test_commit_failure_rolls_back_object_revision_and_receipt(logged, pdf):
    from sqlalchemy.orm import Session
    doc=upload(logged,pdf).json(); path='/api/v1/documents/'+doc['id']
    body=command(annotation=data())
    with patch.object(Session,'commit',side_effect=RuntimeError('injected transaction failure')):
        assert logged.post(path+'/annotations',json=body).status_code == 500
    assert logged.get(path+'/annotations').json()==dict(items=[],annotationRevision=0)
    assert logged.get(path+'/annotation-commands/'+body['commandId']).status_code==404
    assert logged.post(path+'/annotations',json=body).status_code==201


def test_restore_cannot_invent_or_overwrite_snapshot(logged, pdf):
    doc=upload(logged,pdf).json(); path='/api/v1/documents/'+doc['id']
    item=logged.post(path+'/annotations',json=command(annotation=data('freeText'))).json()['annotation']
    assert logged.post(path+'/annotation-commands',json=command(1,operation='restore',annotation=item)).status_code==409
    logged.request('DELETE',path+'/annotations/'+item['id'],json=command(1,version=1))
    assert logged.post(path+'/annotation-commands',json=command(2,operation='restore',annotation={**item,'documentId':'wrong-document'})).status_code==404
    altered={**item,'content':'forged'}
    assert logged.post(path+'/annotation-commands',json=command(2,operation='restore',annotation=altered)).status_code==422
    assert logged.get(path+'/annotations').json()['annotationRevision']==2
    assert logged.post(path+'/annotation-commands',json=command(2,operation='restore',annotation=item)).status_code==200


def test_partial_style_patch_preserves_other_properties(logged,pdf):
    doc=upload(logged,pdf).json();path='/api/v1/documents/'+doc['id']
    item=logged.post(path+'/annotations',json=command(annotation=data('freeText'))).json()['annotation']
    changed=logged.patch(path+'/annotations/'+item['id'],json=command(1,version=1,changes={'style':{'fontSize':30}}))
    assert changed.status_code==200
    assert changed.json()['annotation']['style']['fontSize']==30
    assert changed.json()['annotation']['style']['opacity']==.35


def test_b1_mysql_ddl_only_is_additive(monkeypatch,capsys):
    from alembic import command as alembic_command
    from alembic.config import Config
    from app.config import get_settings
    monkeypatch.setattr(get_settings(),'database_url','mysql+pymysql://test:unused@127.0.0.1/litera_test')
    alembic_command.upgrade(Config('alembic.ini'),'0004_reader_progress:0005_annotations',sql=True)
    ddl=capsys.readouterr().out
    for table in ('annotations','document_reader_state','annotation_command_receipts'): assert 'CREATE TABLE '+table in ddl
    assert 'selected_text MEDIUMTEXT' in ddl and 'content MEDIUMTEXT' in ddl
    assert 'DROP TABLE' not in ddl and 'ALTER TABLE documents' not in ddl


def test_unicode_text_capacity_and_plain_text_roundtrip(logged,pdf):
    doc=upload(logged,pdf).json();path='/api/v1/documents/'+doc['id'];value=data('freeText')
    value['content']='📚'*20000
    response=logged.post(path+'/annotations',json=command(annotation=value))
    assert response.status_code==201,response.text
    assert logged.get(path+'/annotations').json()['items'][0]['content']==value['content']


def test_upgrade_0004_keeps_existing_business_rows_and_pdf(tmp_path,monkeypatch):
    from alembic import command as ac
    from alembic.config import Config
    from sqlalchemy import create_engine
    from app.config import get_settings
    url='sqlite:///'+str(tmp_path/'upgrade.db')
    monkeypatch.setattr(get_settings(),'database_url',url)
    config=Config('alembic.ini');ac.upgrade(config,'0004_reader_progress')
    engine=create_engine(url)
    original=tmp_path/'original.pdf';original.write_bytes(b'%PDF-existing-original')
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id,email,password_hash,display_name,created_at,updated_at) VALUES ('owner','old@example.com','hash','Old',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        conn.execute(text("INSERT INTO documents (id,owner_id,title,authors,keywords,version,parse_status,created_at,updated_at) VALUES ('doc','owner','Original','[]','[]',7,'not_requested',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        conn.execute(text("INSERT INTO document_files (id,document_id,owner_id,original_name,storage_key,sha256,size_bytes,mime_type) VALUES ('file','doc','owner','old.pdf','unchanged.pdf','oldhash',22,'application/pdf')"))
        conn.execute(text("INSERT INTO reading_progress (document_id,owner_id,page_number,zoom,view_mode,zoom_mode,last_read_at,version) VALUES ('doc','owner',3,'1.75','spread','custom',CURRENT_TIMESTAMP,9)"))
        before={table:conn.execute(text('SELECT * FROM '+table)).mappings().all() for table in ('users','documents','document_files','reading_progress')}
    ac.upgrade(config,'head')
    with engine.connect() as conn:
        for table,rows in before.items():assert conn.execute(text('SELECT * FROM '+table)).mappings().all()==rows
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar()=='0010_qa_answers_indexes_vectors'
    assert original.read_bytes()==b'%PDF-existing-original'
    engine.dispose()


def test_expired_receipt_and_cleanup_db_failure_are_traceable(logged,pdf):
    from sqlalchemy.orm import Session
    doc=upload(logged,pdf).json();path='/api/v1/documents/'+doc['id']
    body=command(annotation=data('comment'));item=logged.post(path+'/annotations',json=body).json()['annotation']
    with SessionLocal() as db:
        db.get(AnnotationCommandReceipt,(doc['id'],body['commandId'])).expires_at=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(seconds=1);db.commit()
    assert logged.get(path+'/annotation-commands/'+body['commandId']).status_code==404
    assert logged.post(path+'/annotations',json=body).status_code==409
    assert len(logged.get(path+'/annotations').json()['items'])==1
    logged.delete(path)
    real_execute=Session.execute
    def execute(db,statement,*args,**kwargs):
        if str(statement).startswith('DELETE FROM annotations'):
            raise RuntimeError('injected annotation cleanup failure')
        return real_execute(db,statement,*args,**kwargs)
    with patch.object(Session,'execute',execute):
        failure=logged.delete('/api/v1/trash/documents/'+doc['id'])
    assert failure.status_code==202
    job=failure.json()['jobId'];assert logged.get('/api/v1/cleanup-jobs/'+job).json()['status']=='failed'
    with SessionLocal() as db:assert db.get(Annotation,item['id']) is not None
    assert logged.post('/api/v1/cleanup-jobs/'+job+'/retry').status_code==204
    with SessionLocal() as db:assert db.get(Annotation,item['id']) is None


def test_b2_keeps_b1_zero_rotation_receipt_fingerprint(logged,pdf):
    import hashlib,json
    from app.annotations import Create
    doc=upload(logged,pdf).json();path='/api/v1/documents/'+doc['id'];body=command(annotation=data('freeText'))
    response=logged.post(path+'/annotations',json=body);assert response.status_code==201
    legacy_payload=Create.model_validate(body).model_dump(exclude_unset=True)
    legacy_payload['annotation']['geometry']['rotation']=0
    fingerprint=hashlib.sha256(json.dumps(['create',None,legacy_payload],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    with SessionLocal() as db:
        row=db.get(AnnotationCommandReceipt,(doc['id'],body['commandId']));row.fingerprint=fingerprint;db.commit()
    assert logged.post(path+'/annotations',json=body).json()==response.json()
    for value in (0,0.0):
        body['annotation']['geometry']['rotation']=value
        assert type(Create.model_validate(body).model_dump()['annotation']['geometry']['rotation']) is int
