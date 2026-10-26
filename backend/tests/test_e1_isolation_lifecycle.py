"""P3-E1 combinations missing from stage tests: temporary SQLite/synthetic PDFs only.
No 5180/5177 DB or credentials, external calls, or production service mutation.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from io import BytesIO
from uuid import uuid4
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,text
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from app.main import app
from app.database import SessionLocal
from app.models import Note,NoteDocument,DocumentFile,LoginSession
from app.documents import storage_path
from app import translations
from app.answer_sources import get_answer_resolver
from test_auth import register,login
from test_documents import logged,upload
from test_notes import create
from test_note_captures import payload,send,assert_error
from test_ai_note_captures import body as ai_body,FixedMockAnswers,PDF_BYTES,QUOTE

ORIGIN={'Origin':'http://localhost:8080'}


@pytest.fixture(autouse=True)
def isolated_limits_and_resolver():
    translations.attempts.clear()
    yield
    translations.attempts.clear()
    app.dependency_overrides.pop(get_answer_resolver,None)


def sign_in(client,email):
    assert register(client,email).status_code==201
    client.headers['X-CSRF-Token']=login(client,email).json()['csrfToken']


def notes_snapshot():
    with SessionLocal() as db:
        return {model.__tablename__:[tuple(row) for row in db.execute(select(model.__table__).order_by(model.__table__.c[0]))]
                for model in (Note,NoteDocument,DocumentFile)}


def mock_translation(monkeypatch):
    seen=[]
    async def fake(raw,source,target,settings,**kwargs):
        seen.append((raw,source,target))
        return '[ISOLATED MOCK] translated test text'
    monkeypatch.setattr(translations,'translate_text',fake)
    return seen


def translate_capture(client,doc,note,monkeypatch):
    mock_translation(monkeypatch)
    response=client.post('/api/v1/documents/'+doc['id']+'/translations',json=dict(text=QUOTE,
        sourceLanguage='en',targetLanguage='zh',pageNumber=1,contextRevision=4))
    assert response.status_code==200,response.text
    result=response.json()
    return payload(doc,note,kind='translation_excerpt',originalText=QUOTE,
        translatedText=result['translatedText'],sourceLanguage='en',targetLanguage='zh',
        translationProof=result['translationProof'])


def test_same_pdf_hash_never_substitutes_for_account_ownership(logged,monkeypatch):
    a=logged;doc_a=upload(a,PDF_BYTES,'Shared bytes.pdf').json();note_a=create(a,doc_a['id'],content='A_ONLY')
    resolver=FixedMockAnswers();app.dependency_overrides[get_answer_resolver]=lambda:resolver
    with TestClient(app,headers=ORIGIN) as b:
        sign_in(b,'e1-b@example.com')
        doc_b=upload(b,PDF_BYTES,'Shared bytes.pdf').json();note_b=create(b,doc_b['id'],content='B_ONLY_PRIVATE_SENTINEL')
        b_capture=translate_capture(b,doc_b,note_b,monkeypatch)
        saved=send(b,b_capture);assert saved.status_code==201
        b_note=saved.json()['note']
        with SessionLocal() as db:record=resolver.records(db,db.get(Note,note_b['id']).owner_id,doc_b['id'])[0]
        saved_ai=send(b,ai_body(record,b_note));assert saved_ai.status_code==201
        b_note=saved_ai.json()['note'];before=notes_snapshot()
        # Both users own identical bytes: matching SHA256 cannot grant ownership.
        assert doc_a['attachment']['sha256']==doc_b['attachment']['sha256']
        url='/api/v1/notes/'+note_b['id']
        for response in [a.get(url),a.patch(url,json={'version':b_note['version'],'content':'Attack'}),
            a.delete(url,params={'version':b_note['version']}),a.put(url+'/documents/'+doc_a['id']),
            a.delete(url+'/documents/'+doc_b['id']),a.get('/api/v1/notes',params={'documentId':doc_b['id']}),
            a.post('/api/v1/documents/'+doc_b['id']+'/translations',json=dict(text=QUOTE,sourceLanguage='en',targetLanguage='zh',pageNumber=1,contextRevision=4)),
            a.get(f'/api/v1/notes/answer-preview/{record.answerId}?revision=1')]:
            assert response.status_code==404,response.text
            assert 'B_ONLY_PRIVATE_SENTINEL' not in response.text
        forged=deepcopy(b_capture);forged.update(operationId=str(uuid4()),noteId=note_a['id'],version=note_a['version'])
        forged['source']['documentId']=doc_a['id']
        assert_error(send(a,forged),'TRANSLATION_PROOF_INVALID')
        assert send(a,payload(doc_b,note_a,originalText=QUOTE)).status_code==404
        assert send(a,ai_body(record,note_a,confirmUncited=True)).status_code==404
        result=a.get('/api/v1/notes/search',params={'q':'B_ONLY_PRIVATE_SENTINEL'}).json()
        assert result['total']==0
        assert all(n['id']!=note_b['id'] for n in a.get('/api/v1/notes').json()['items'])
        assert notes_snapshot()==before


@pytest.mark.parametrize('state',['anonymous','expired','revoked'])
def test_note_capture_search_and_translation_reject_inactive_sessions(logged,state):
    doc=upload(logged,PDF_BYTES,'Session fixture.pdf').json();note=create(logged,doc['id'])
    client=logged
    if state=='anonymous':
        client=TestClient(app,headers=ORIGIN)
    else:
        with SessionLocal() as db:
            session=db.scalar(select(LoginSession))
            if state=='expired':session.expires_at=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(seconds=1)
            else:session.revoked_at=datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
    before=notes_snapshot();url='/api/v1/notes/'+note['id']
    responses=[client.get('/api/v1/notes'),client.get('/api/v1/notes/search',params={'q':'fixture'}),client.get(url),
        client.get('/api/v1/notes/capture-config'),client.patch(url,json={'version':1,'content':'Denied'}),
        client.delete(url,params={'version':1}),client.put(url+'/documents/'+doc['id']),client.delete(url+'/documents/'+doc['id']),
        client.post('/api/v1/notes',json={'id':str(uuid4()),'title':'Denied','content':''}),
        send(client,payload(doc,note,originalText=QUOTE)),
        client.post('/api/v1/documents/'+doc['id']+'/translations',json=dict(text=QUOTE,sourceLanguage='en',targetLanguage='zh',pageNumber=1,contextRevision=4)),
        client.get('/api/v1/notes/answer-preview/'+str(uuid4())+'?revision=1')]
    assert all(r.status_code==401 for r in responses),[(r.status_code,r.text) for r in responses]
    assert notes_snapshot()==before
    if state=='anonymous':client.close()


def test_all_source_kinds_survive_unlink_trash_restore_purge_and_identical_reupload(logged,monkeypatch):
    a=upload(logged,PDF_BYTES,'Source A.pdf').json()
    b=upload(logged,PDF_BYTES+b'\n% independent synthetic B\n','Source B.pdf').json()
    shared=create(logged,a['id'],title='Shared sources',content='Personal body survives')
    orphan=create(logged,a['id'],title='Only A note',content='Keep zero-link note too')
    assert len(logged.get('/api/v1/notes',params={'documentId':a['id']}).json()['items'])==2
    assert logged.put('/api/v1/notes/'+shared['id']+'/documents/'+b['id']).status_code==200
    resolver=FixedMockAnswers();app.dependency_overrides[get_answer_resolver]=lambda:resolver
    with SessionLocal() as db:
        owner=db.get(Note,shared['id']).owner_id;records=resolver.records(db,owner,a['id'])
        file=db.scalar(select(DocumentFile).where(DocumentFile.document_id==a['id']));original_file=storage_path(file.storage_key)
    for request in [payload(a,shared,originalText=QUOTE),translate_capture(logged,a,shared,monkeypatch),ai_body(records[0],shared),ai_body(records[1],shared,confirmUncited=True)]:
        request['version']=shared['version']
        response=send(logged,request);assert response.status_code==201,response.text
        shared=response.json()['note']
    response=send(logged,payload(a,orphan,originalText=QUOTE));assert response.status_code==201
    orphan=response.json()['note'];sources=deepcopy(shared['sources'])
    url='/api/v1/notes/'+shared['id']
    assert logged.delete(url+'/documents/'+a['id']).status_code==200
    assert logged.get(url).json()['sources']==sources
    assert logged.put(url+'/documents/'+a['id']).status_code==200
    assert logged.delete('/api/v1/documents/'+a['id']).status_code==204
    trashed=logged.get(url).json();assert trashed['sources']==sources and [d['id'] for d in trashed['documents']]==[b['id']]
    assert logged.get('/api/v1/documents/'+a['id']).status_code==404
    # Capture the exact adapter error, but finish all persistence checks before assertion.
    trashed_answer_status=logged.get(f'/api/v1/notes/answer-preview/{records[0].answerId}?revision=1').status_code
    assert send(logged,payload(a,trashed,originalText=QUOTE)).status_code==404
    assert logged.post('/api/v1/trash/documents/'+a['id']+'/restore').status_code==200
    assert {d['id'] for d in logged.get(url).json()['documents']}=={a['id'],b['id']}
    assert logged.get(url).json()['sources']==sources
    assert logged.delete('/api/v1/documents/'+a['id']).status_code==204
    assert logged.delete('/api/v1/trash/documents/'+a['id']).status_code==204
    assert not original_file.exists()
    final=logged.get(url).json();assert final['sources']==sources and final['content']=='Personal body survives'
    assert [d['id'] for d in final['documents']]==[b['id']]
    zero=logged.get('/api/v1/notes/'+orphan['id']).json();assert zero['documents']==[] and zero['sources']==orphan['sources']
    with SessionLocal() as db:
        assert list(db.execute(text('PRAGMA foreign_key_check')))==[]
        assert not db.scalars(select(NoteDocument).where(NoteDocument.document_id==a['id'])).all()
        assert db.get(Note,shared['id']) is not None and db.get(Note,orphan['id']) is not None
    new_a=upload(logged,PDF_BYTES,'Source A.pdf').json();assert new_a['id']!=a['id']
    assert new_a['attachment']['sha256']==a['attachment']['sha256']
    assert logged.get('/api/v1/documents/'+a['id']).status_code==404
    assert logged.get(url).json()['sources']==sources
    assert logged.get('/api/v1/notes',params={'documentId':new_a['id']}).json()['items']==[]
    assert logged.get(f'/api/v1/notes/answer-preview/{records[0].answerId}?revision=1').status_code==404
    assert logged.get('/api/v1/notes/search',params={'q':'synthetic PDF exists only'}).json()['total']==2
    assert trashed_answer_status==404, 'Soft-deleted Mock answer must be not found, not a source-service outage'


@pytest.mark.parametrize('source,target,selected',[
 ('en','zh','microscopy'),('en','zh','Optical microscopy supports research.'),
 ('en','zh','Optical microscopy supports research. It measures small structures.'),
 ('zh','en','显微镜'),('zh','en','显微镜用于科学研究。'),
 ('zh','en','显微镜用于科学研究。它可以观察微小结构。')])
def test_bilingual_word_sentence_paragraph_requests_use_real_pdf_text_and_mock_model(logged,monkeypatch,source,target,selected):
    stream=BytesIO();canvas=Canvas(stream,pagesize=(612,792));pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    canvas.setFont('Helvetica',11);canvas.drawString(40,720,'Optical microscopy supports research. It measures small structures.')
    canvas.setFont('STSong-Light',11);canvas.drawString(40,690,'显微镜用于科学研究。它可以观察微小结构。');canvas.save()
    raw=stream.getvalue();assert selected in PdfReader(BytesIO(raw)).pages[0].extract_text()
    doc=upload(logged,raw,'Bilingual synthetic.pdf').json();seen=mock_translation(monkeypatch)
    response=logged.post('/api/v1/documents/'+doc['id']+'/translations',json=dict(text=selected,
        sourceLanguage=source,targetLanguage=target,pageNumber=1,contextRevision=7))
    assert response.status_code==200,response.text
    assert seen==[(selected,source,target)]
    result=response.json();assert result['originalText']==selected
    assert result['source']['documentId']==doc['id'] and result['source']['pageNumber']==1
    assert (result['source']['sourceLanguage'],result['source']['targetLanguage'])==(source,target)
    assert result['translationProof']['provenance']=='isolated_mock'
