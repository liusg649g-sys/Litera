"""P3-A real HTTP/temporary database notes; no model or development data."""
from concurrent.futures import ThreadPoolExecutor
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app import notes
from app.main import app
from app.database import SessionLocal
from app.models import Note, NoteDocument
from test_documents import logged, pdf, upload
from test_auth import register, login


def note_payload(document=None, **changes):
    body={'id':str(uuid.uuid4()),'title':'Research note','content':'First paragraph.'}
    if document:body['documentId']=document
    body.update(changes);return body


def create(client, document=None, **changes):
    response=client.post('/api/v1/notes',json=note_payload(document,**changes))
    assert response.status_code==201,response.text
    return response.json()


def documents(client,pdf):
    first=upload(client,pdf,'A.pdf').json()
    second=upload(client,pdf+b'\n% independent second synthetic PDF\n','B.pdf').json()
    return first,second


def test_config_auth_and_missing_schema_are_read_only(logged,monkeypatch):
    assert logged.get('/api/v1/notes/config').json()=={'available':True,'contentMaxLength':100000,'titleMaxLength':200,'contentFormat':'plain-text'}
    monkeypatch.setattr(notes,'schema_available',lambda db:False)
    assert logged.get('/api/v1/notes/config').json()['available'] is False
    for response in (logged.get('/api/v1/notes'),logged.post('/api/v1/notes',json=note_payload())):
        assert response.status_code==503 and response.json()['error']['code']=='NOTES_NOT_READY'
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(Note))==0


def test_multiple_notes_and_many_documents_reuse_one_identity(logged,pdf):
    a,b=documents(logged,pdf)
    first=create(logged,a['id']);second=create(logged,a['id'],title='Another note')
    url=f'/api/v1/notes/{first["id"]}/documents/{b["id"]}'
    linked=logged.put(url);assert linked.status_code==200
    assert {d['id'] for d in linked.json()['documents']}=={a['id'],b['id']}
    assert logged.put(url).json()==linked.json()  # set-idempotent, no content version bump
    assert logged.get('/api/v1/notes',params={'documentId':a['id']}).json()['total']==2
    b_items=logged.get('/api/v1/notes',params={'documentId':b['id']}).json()['items']
    assert [item['id'] for item in b_items]==[first['id']] and 'content' not in b_items[0]
    updated=logged.patch(f'/api/v1/notes/{first["id"]}',json={'version':1,'title':'Shared identity','content':'Shared new body'}).json()
    assert updated['version']==2
    assert logged.get(f'/api/v1/notes/{first["id"]}').json()['content']=='Shared new body'
    unlinked=logged.delete(f'/api/v1/notes/{first["id"]}/documents/{a["id"]}')
    assert unlinked.status_code==200 and unlinked.json()['content']=='Shared new body'
    assert logged.delete(f'/api/v1/notes/{first["id"]}/documents/{a["id"]}').json()==unlinked.json()
    assert logged.get('/api/v1/notes',params={'documentId':a['id']}).json()['total']==1
    assert logged.get('/api/v1/notes',params={'documentId':b['id']}).json()['items'][0]['id']==first['id']
    logged.delete(url)
    assert logged.get('/api/v1/notes').json()['total']==2  # Unlinked note remains personal.
    assert logged.get(f'/api/v1/notes/{first["id"]}').json()['documents']==[]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Note))==2
        assert db.scalar(select(func.count()).select_from(NoteDocument))==1


def test_create_uuid_replay_never_duplicates_or_overwrites(logged,pdf):
    doc=upload(logged,pdf).json();body=note_payload(doc['id'])
    first=logged.post('/api/v1/notes',json=body)
    second=logged.post('/api/v1/notes',json=body)
    assert first.status_code==201 and second.status_code==200 and first.json()==second.json()
    assert first.json()['sources']==[] and first.json()['sourceSchemaVersion']==1
    assert first.json()['contentFormat']=='plain-text' and 'ownerId' not in first.json()
    patch=logged.patch('/api/v1/notes/'+body['id'],json={'version':1,'content':'Updated body'})
    assert patch.status_code==200
    assert logged.post('/api/v1/notes',json=body).status_code==409
    assert logged.get('/api/v1/notes/'+body['id']).json()['content']=='Updated body'
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Note))==1
        assert db.scalar(select(func.count()).select_from(NoteDocument))==1


def test_autosave_cas_exact_replay_and_persistence_after_login(logged):
    item=create(logged,title='Original',content='Original body')
    url='/api/v1/notes/'+item['id'];body={'version':1,'title':'Saved title','content':'Saved body'}
    saved=logged.patch(url,json=body)
    assert saved.status_code==200 and saved.json()['version']==2
    assert logged.patch(url,json=body).json()==saved.json()  # lost-ack replay
    assert logged.patch(url,json={'version':2,'content':'Saved body'}).json()['version']==2
    conflict=logged.patch(url,json={'version':1,'content':'Stale different body'})
    assert conflict.status_code==409 and conflict.json()['error']['code']=='NOTE_VERSION_CONFLICT'
    assert logged.patch(url,json={'version':99,'content':'Saved body'}).status_code==409
    assert logged.get(url).json()==saved.json()
    assert logged.post('/api/v1/auth/logout').status_code==204
    token=login(logged).json()['csrfToken'];logged.headers['X-CSRF-Token']=token
    assert logged.get(url).json()==saved.json()


def test_two_concurrent_editors_cannot_silently_overwrite(logged):
    item=create(logged);url='/api/v1/notes/'+item['id']
    # These independently scheduled writes use the same base snapshot.
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda content:logged.patch(url,json={'version':1,'content':content}),['Editor A','Editor B']))
    assert sorted(r.status_code for r in responses)==[200,409]
    result=logged.get(url).json();assert result['version']==2 and result['content'] in ('Editor A','Editor B')


def test_delete_version_confirmation_does_not_remove_documents(logged,pdf):
    a,b=documents(logged,pdf);item=create(logged,a['id'])
    logged.put(f'/api/v1/notes/{item["id"]}/documents/{b["id"]}')
    url='/api/v1/notes/'+item['id']
    assert logged.delete(url,params={'version':9}).status_code==409
    assert logged.get(url).status_code==200
    assert logged.delete(url,params={'version':1}).status_code==204
    assert logged.get(url).status_code==404 and logged.delete(url,params={'version':1}).status_code==404
    assert logged.get('/api/v1/documents/'+a['id']+'/content').content==pdf
    assert logged.get('/api/v1/documents/'+b['id']).status_code==200
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Note))==0
        assert db.scalar(select(func.count()).select_from(NoteDocument))==0


def test_document_trash_restore_and_purge_preserve_note_body(logged,pdf):
    a,b=documents(logged,pdf);item=create(logged,a['id'],content='Preserve across document deletion')
    note_url='/api/v1/notes/'+item['id'];logged.put(note_url+'/documents/'+b['id'])
    assert logged.delete('/api/v1/documents/'+a['id']).status_code==204
    assert logged.get('/api/v1/notes',params={'documentId':a['id']}).status_code==404
    assert [d['id'] for d in logged.get(note_url).json()['documents']]==[b['id']]
    assert logged.get('/api/v1/notes').json()['items'][0]['id']==item['id']
    assert logged.post('/api/v1/trash/documents/'+a['id']+'/restore').status_code==200
    assert len(logged.get(note_url).json()['documents'])==2
    logged.delete('/api/v1/documents/'+a['id'])
    assert logged.delete('/api/v1/trash/documents/'+a['id']).status_code==204
    final=logged.get(note_url).json()
    assert final['content']=='Preserve across document deletion'
    assert [d['id'] for d in final['documents']]==[b['id']]


def test_permissions_for_note_and_document_both_checked(logged,pdf):
    doc=upload(logged,pdf).json();item=create(logged,doc['id'])
    with TestClient(app,headers={'Origin':'http://localhost:8080'}) as other:
        assert other.get('/api/v1/notes/config').status_code==401
        assert register(other,'other-notes@example.com').status_code==201
        other.headers['X-CSRF-Token']=login(other,'other-notes@example.com').json()['csrfToken']
        otherdoc=upload(other,pdf).json();own=create(other,otherdoc['id'])
        path='/api/v1/notes/'+item['id']
        responses=[other.get(path),other.patch(path,json={'version':1,'content':'Attack'}),
                   other.delete(path,params={'version':1}),other.put(path+'/documents/'+otherdoc['id']),
                   other.delete(path+'/documents/'+otherdoc['id']),
                   other.put('/api/v1/notes/'+own['id']+'/documents/'+doc['id']),
                   other.delete('/api/v1/notes/'+own['id']+'/documents/'+doc['id']),
                   other.get('/api/v1/notes',params={'documentId':doc['id']}),
                   other.post('/api/v1/notes',json=note_payload(doc['id'])),
                   other.post('/api/v1/notes',json=note_payload(id=item['id']))]
        assert all(response.status_code==404 for response in responses)
        assert other.get('/api/v1/notes').json()['total']==1
    assert logged.get('/api/v1/notes/'+item['id']).json()['content']==item['content']


@pytest.mark.parametrize('changes',[{'ownerId':'attacker'},{'sources':[]},{'sourceType':'translation'},{'contentFormat':'html'},
    {'id':'not-a-uuid'},{'title':' '*3},{'title':'x'*201},{'content':'x'*100001}])
def test_create_rejects_forged_sources_and_invalid_fields(logged,changes):
    response=logged.post('/api/v1/notes',json=note_payload(**changes))
    assert response.status_code==422
    assert logged.get('/api/v1/notes').json()['total']==0


@pytest.mark.parametrize('body',[{'version':1},{'version':True,'content':'text'},{'version':1,'title':None},
    {'version':1,'content':None},{'version':1,'sources':[]},{'version':1,'ownerId':'other'}])
def test_patch_validation_preserves_original(logged,body):
    item=create(logged);url='/api/v1/notes/'+item['id']
    assert logged.patch(url,json=body).status_code==422
    assert logged.get(url).json()==item


def test_csrf_and_plain_text_roundtrip(logged,pdf):
    doc=upload(logged,pdf).json();value='<script>alert("not executed")</script>\nLiteral **text**'
    assert logged.post('/api/v1/notes',json=note_payload(),headers={'X-CSRF-Token':'wrong'}).status_code==403
    item=create(logged,doc['id'],content=value)
    assert item['content']==value
    url='/api/v1/notes/'+item['id']
    assert logged.put(url+'/documents/'+doc['id'],json={'ownerId':'other'}).status_code==422
    assert logged.delete(url+'/documents/'+doc['id'],headers={'X-CSRF-Token':'bad'}).status_code==403
    assert logged.get(url).json()['content']==value


def test_personal_note_summary_paging_is_not_full_text_search(logged):
    for title in ('One','Two','Three'):create(logged,title=title,content='Body not listed')
    first=logged.get('/api/v1/notes',params={'page':1,'pageSize':2}).json()
    second=logged.get('/api/v1/notes',params={'page':2,'pageSize':2}).json()
    assert first['total']==second['total']==3 and len(first['items'])==2 and len(second['items'])==1
    assert not ({item['id'] for item in first['items']} & {item['id'] for item in second['items']})
    assert all('content' not in item for item in first['items'])
    assert logged.get('/api/v1/notes?q=Body').status_code==422
    assert logged.get('/api/v1/notes?page=1&page=2').status_code==422
    assert logged.get('/api/v1/notes?pageSize=101').status_code==422



def test_schema_readiness_rejects_absent_and_partial_tables_without_ddl():
    from sqlalchemy import create_engine,inspect
    from sqlalchemy.orm import Session
    isolated=create_engine('sqlite://')
    try:
        with Session(isolated) as db:
            assert notes.schema_available(db) is False
            assert inspect(db.connection()).get_table_names()==[]
            db.connection().exec_driver_sql('CREATE TABLE notes (id TEXT PRIMARY KEY)')
            db.connection().exec_driver_sql('CREATE TABLE note_documents (note_id TEXT, document_id TEXT)')
            assert notes.schema_available(db) is False
            assert set(inspect(db.connection()).get_table_names())=={'notes','note_documents'}
            assert [column['name'] for column in inspect(db.connection()).get_columns('notes')]==['id']
    finally:isolated.dispose()


def test_unlink_preserves_only_other_document_across_relogin_and_delete(logged,pdf):
    a,b=documents(logged,pdf)
    item=create(logged,a['id'],title='Shared summary',content='Body must survive unlink and login')
    url='/api/v1/notes/'+item['id']
    linked=logged.put(url+'/documents/'+b['id'])
    assert linked.status_code==200
    baseline=linked.json()
    assert {document['id'] for document in baseline['documents']}=={a['id'],b['id']}

    removed=logged.delete(url+'/documents/'+a['id'])
    assert removed.status_code==200
    retained=removed.json()
    assert retained['documents']==[{'id':b['id'],'title':b['title']}]
    for field in ('id','title','content','version','createdAt','updatedAt'):
        assert retained[field]==baseline[field]
    assert logged.get('/api/v1/notes',params={'documentId':a['id']}).json()['items']==[]
    assert [note['id'] for note in logged.get('/api/v1/notes',params={'documentId':b['id']}).json()['items']]==[item['id']]
    with SessionLocal() as db:
        links=db.scalars(select(NoteDocument).where(NoteDocument.note_id==item['id'])).all()
        assert [(link.document_id,link.owner_id) for link in links]==[(b['id'],db.get(Note,item['id']).owner_id)]
        assert db.get(Note,item['id']).content==baseline['content']

    # Set-idempotent DELETE must not remove B's link or the independent body.
    repeated=logged.delete(url+'/documents/'+a['id'])
    assert repeated.status_code==200 and repeated.json()==retained
    assert logged.post('/api/v1/auth/logout').status_code==204
    logged.headers['X-CSRF-Token']=login(logged).json()['csrfToken']
    assert logged.get(url).json()==retained
    assert logged.get('/api/v1/notes',params={'documentId':a['id']}).json()['total']==0
    assert [note['id'] for note in logged.get('/api/v1/notes',params={'documentId':b['id']}).json()['items']]==[item['id']]

    assert logged.delete(url,params={'version':retained['version']}).status_code==204
    assert logged.get(url).status_code==404
    assert logged.get('/api/v1/notes',params={'documentId':b['id']}).json()['items']==[]
    with SessionLocal() as db:
        assert db.get(Note,item['id']) is None
        assert db.scalars(select(NoteDocument).where(NoteDocument.note_id==item['id'])).all()==[]
    assert logged.get('/api/v1/documents/'+a['id']).status_code==200
    assert logged.get('/api/v1/documents/'+b['id']).status_code==200
