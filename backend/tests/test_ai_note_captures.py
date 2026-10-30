"""Real HTTP + temporary SQLite + synthetic PDF; fixed Mock QA only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.answer_sources import get_answer_resolver, AnswerResolutionError
from app.database import SessionLocal
from app.main import app
from app.models import Note, DocumentFile
from sqlalchemy import select
from test_documents import logged, upload
from test_auth import login, register
from test_notes import create
from test_note_captures import send, assert_error
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from mock_answer_fixture import FixedMockAnswers, PDF_BYTES, QUOTE, ANSWER


@pytest.fixture
def fixture(logged):
    document = upload(logged, PDF_BYTES, 'Isolated Mock QA.pdf').json()
    resolver = FixedMockAnswers()
    app.dependency_overrides[get_answer_resolver] = lambda: resolver
    try:
        with SessionLocal() as db:
            from app.models import Document
            owner=db.get(Document,document['id']).owner_id
            records=resolver.records(db, owner, document['id'])
        # Close the short-lived lookup session; no external QA or model call.
        yield document, resolver, records
    finally:
        app.dependency_overrides.pop(get_answer_resolver, None)


def body(record, note=None, **changes):
    source=dict(kind='ai_answer', answerId=record.answerId, answerRevision=record.answerRevision,
                historical=False, confirmHistorical=False, confirmUncited=False)
    source.update(changes)
    return dict(operationId=str(uuid4()), noteId=note['id'] if note else str(uuid4()),
        newNoteTitle=None if note else 'AI fixture note', version=note['version'] if note else None,
        associationMode='link', source=source)


def count_blocks(note_id):
    with SessionLocal() as db:
        note=db.get(Note,note_id)
        return len(note.sources) if note else 0


def test_default_resolver_is_qa_backed_and_no_mock_routes(logged):
    cfg=logged.get('/api/v1/notes/capture-config').json()
    assert cfg['aiAnswerCapture']==dict(available=True,isolatedMock=False)
    assert 'ai_answer' in cfg['supportedSourceKinds']
    assert not any('mock-answers' in path for path in app.openapi()['paths'])
    class Ref: answerId=str(uuid4());answerRevision=1
    assert_error(send(logged,body(Ref())), 'AI_ANSWER_NOT_FOUND',404)
    assert logged.get('/api/v1/notes/answer-preview/not-a-uuid?revision=1').status_code==422


def test_preview_allowlist_cited_new_and_replay(logged,fixture):
    doc,resolver,records=fixture;record=records[0]
    preview=logged.get(f'/api/v1/notes/answer-preview/{record.answerId}?revision=1')
    assert preview.status_code==200,preview.text
    assert 'ownerId' not in preview.json() and 'API_KEY' not in preview.text
    request=body(record);response=send(logged,request)
    assert response.status_code==201,response.text
    block=response.json()['note']['sources'][0]
    assert block['kind']=='ai_answer' and 'originalText' not in block and 'source' not in block
    assert block['question']==record.question and block['answer']==ANSWER
    assert block['answerRef']['provenance']=='isolated_mock'
    assert block['citations'][0]['quote']==QUOTE and block['citations'][0]['pageNumber']==1
    assert block['contextDocument']['documentId']==doc['id']
    assert send(logged,request).status_code==200 and count_blocks(request['noteId'])==1
    # Retry returns the committed immutable block even if source service is now unavailable.
    resolver.available=False
    assert send(logged,request).status_code==200
    reloaded=logged.get('/api/v1/notes/'+request['noteId']).json()
    assert reloaded['sources']==response.json()['note']['sources']


@pytest.mark.parametrize('target',['current','other'])
def test_existing_note_cas_dedup_and_no_relink(logged,fixture,target):
    doc,_,records=fixture
    note=create(logged,doc['id'],title=target)
    request=body(records[0],note);response=send(logged,request)
    assert response.status_code==201,response.text
    other=body(records[0],note)
    duplicate=send(logged,other)
    assert duplicate.status_code==200 and duplicate.json()['deduplicated'] is True
    assert count_blocks(note['id'])==1
    # A second save with a new operation does not undo explicit unlinking.
    assert logged.delete(f"/api/v1/notes/{note['id']}/documents/{doc['id']}").status_code==200
    duplicate=send(logged,other)
    assert duplicate.status_code==200 and duplicate.json()['linked'] is False


def test_uncited_requires_confirmation_and_has_no_page(logged,fixture):
    doc,_,records=fixture;request=body(records[1])
    assert_error(send(logged,request),'AI_UNCITED_CONFIRMATION_REQUIRED')
    assert count_blocks(request['noteId'])==0
    request['source']['confirmUncited']=True
    saved=send(logged,request);assert saved.status_code==201,saved.text
    block=saved.json()['note']['sources'][0]
    assert block['evidenceState']=='none' and block['citations']==[] and block['uncitedAcknowledged']
    assert 'pageNumber' not in block['contextDocument']


@pytest.mark.parametrize('field,value',[
 ('answer','forged answer'),('question','forged question'),('citations',[]),
 ('documentId',str(uuid4())),('ownerId',str(uuid4())),('evidenceState','verified'),('provenance','model_api')])
def test_browser_cannot_forge_authoritative_fields(logged,fixture,field,value):
    request=body(fixture[2][0]);request['source'][field]=value
    assert send(logged,request).status_code==422
    assert count_blocks(request['noteId'])==0


@pytest.mark.parametrize('damage,code,status',[
 ('wrong_doc','AI_EVIDENCE_INVALID',422),('wrong_quote','PDF_TEXT_NOT_FOUND',422),
 ('wrong_page','INVALID_PAGE',422),('wrong_hash','AI_SOURCE_CHANGED',409),
 ('bad_chunk','AI_EVIDENCE_INVALID',422),('expired','AI_ANSWER_EXPIRED',409),
 ('stale','AI_ANSWER_STALE',409),('service','AI_ANSWER_UNAVAILABLE',503),
 ('owner','AI_ANSWER_NOT_FOUND',404),('false_verified','AI_EVIDENCE_INVALID',422),
 ('none_with_cites','AI_EVIDENCE_INVALID',422),('evidence_failure','AI_ANSWER_UNAVAILABLE',503),
])
def test_source_failure_never_downgrades(logged,fixture,monkeypatch,damage,code,status,caplog):
    doc,resolver,records=fixture;record=records[0].model_copy(deep=True)
    secret='fake-secret-canary-should-never-leak'
    if damage=='wrong_doc':record.citations[0].documentId=str(uuid4())
    if damage=='wrong_quote':record.citations[0].quote='This invented quote is not in the PDF.'
    if damage=='wrong_page':record.citations[0].pageNumber=8
    if damage=='wrong_hash':record.fileSha256='a'*64
    if damage=='expired':record.expiresAt=datetime.now(timezone.utc)-timedelta(seconds=1)
    if damage=='owner':record.ownerId=str(uuid4())
    if damage=='false_verified':record.citations=[]
    if damage=='none_with_cites':record.evidenceState='none'
    if damage=='bad_chunk':monkeypatch.setattr(resolver,'verify_citation',lambda *a:False)
    elif damage=='evidence_failure':
        def verify(*args):raise RuntimeError(secret)
        monkeypatch.setattr(resolver,'verify_citation',verify)
    else:monkeypatch.setattr(resolver,'verify_citation',lambda *a:True)
    def resolve(*args):
        if damage=='stale':raise AnswerResolutionError('stale')
        if damage=='service':raise HTTPException(503,secret)
        return record
    monkeypatch.setattr(resolver,'resolve',resolve)
    request=body(records[0],confirmUncited=True)
    response=send(logged,request)
    assert_error(response,code,status)
    assert secret not in response.text and secret not in caplog.text
    assert count_blocks(request['noteId'])==0


def test_answer_and_note_owner_isolation(logged,fixture,client):
    doc,_,records=fixture;note=create(logged,doc['id'])
    register(client,'other@example.com');token=login(client,'other@example.com').json()['csrfToken'];client.headers['X-CSRF-Token']=token
    assert_error(send(client,body(records[0])), 'AI_ANSWER_NOT_FOUND',404)
    assert_error(send(client,body(records[0],note)), 'NOTE_NOT_FOUND',404)


def test_version_conflict_does_not_overwrite_draft_and_search(logged,fixture):
    doc,_,records=fixture;note=create(logged,doc['id']);request=body(records[0],note)
    updated=logged.patch('/api/v1/notes/'+note['id'],json={'version':note['version'],'title':'Edited','content':'User draft retained'})
    assert updated.status_code==200
    assert_error(send(logged,request),'NOTE_VERSION_CONFLICT',409)
    request['version']=updated.json()['version']
    saved=send(logged,request);assert saved.status_code==201,saved.text
    assert saved.json()['note']['content']=='User draft retained'
    for term,field in [('synthetic','ai_question'),('artificial fixture','ai_answer'),('only to test','source_original')]:
        result=logged.get('/api/v1/notes/search',params={'q':term})
        assert result.status_code==200,result.text
        assert result.json()['total']==1
        assert any(m['field']==field for m in result.json()['items'][0]['matches'])


def test_historical_confirm_and_fingerprint(logged,fixture):
    request=body(fixture[2][0],historical=True)
    assert send(logged,request).status_code==422
    request['source']['confirmHistorical']=True
    assert send(logged,request).status_code==201
    request['associationMode']='keep'
    assert_error(send(logged,request),'NOTE_CAPTURE_CONFLICT',409)
