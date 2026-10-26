"""Isolated SQLite/AES-GCM + controlled HTTP only; no external model or real credentials."""
import asyncio
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
import socket
import sqlite3
from uuid import uuid4
import httpcore
import httpx
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from app import ai_service, model_network, translations, user_models
from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.model_secrets import WindowsSecretVault
from app.models import UserModelProfile
from test_auth import register, login
from test_documents import logged, upload
from test_note_captures import synthetic_pdf, TEXT, payload as capture_payload, send

KEY='synthetic-key-not-a-real-provider-secret'
class TestVault:
    __test__=False
    available=True
    scheme='isolated-aesgcm-test-only'
    def __init__(self):self.aes=AESGCM(AESGCM.generate_key(bit_length=256))
    def encrypt(self,owner,key):
        nonce=os.urandom(12);return nonce+self.aes.encrypt(nonce,key.encode(),owner.encode())
    def decrypt(self,owner,value):return self.aes.decrypt(value[:12],value[12:],owner.encode()).decode()

@pytest.fixture(autouse=True)
def enable(monkeypatch):
    monkeypatch.setattr(get_settings(),'user_models_enabled',True)
    monkeypatch.setattr(user_models,'get_secret_vault',lambda:TestVaultSingleton)
    user_models.probe_attempts.clear();translations.attempts.clear()
    yield
    user_models.probe_attempts.clear();translations.attempts.clear()
TestVaultSingleton=TestVault()

def body(profile=None,**changes):
    value={'provider':'openai_compatible','baseUrl':'https://model.example.com/v1','model':'mock-chat','apiKey':KEY,'expectedRevision':profile['revision'] if profile else None}
    value.update(changes);return value

def save(client,profile=None,**changes):
    response=client.put('/api/v1/user-model',json=body(profile,**changes))
    assert response.status_code==200,response.text
    assert KEY not in response.text
    return response.json()['profile']

@pytest.fixture
def gateway(monkeypatch):
    calls=[];original=httpx.AsyncClient
    async def handle(request):
        calls.append(request)
        return httpx.Response(200,json={'choices':[{'message':{'content':'[ISOLATED MOCK] model reply'},'finish_reason':'stop'}]})
    def factory(**options):
        options['transport']=httpx.MockTransport(handle)
        return original(**options)
    monkeypatch.setattr(ai_service.httpx,'AsyncClient',factory)
    return calls

def test_crud_encrypted_key_keep_replace_clear_and_delete(logged,gateway,caplog):
    assert logged.get('/api/v1/user-model').json()=={'available':True,'profile':None}
    profile=save(logged);assert not profile['verified'] and profile['hasApiKey']
    assert not gateway
    owner=logged.get('/api/v1/users/me').json()['id']
    with SessionLocal() as db:
        row=db.get(UserModelProfile,owner)
        assert row.encrypted_key!=KEY.encode() and KEY.encode() not in row.encrypted_key
        assert TestVaultSingleton.decrypt(owner,row.encrypted_key)==KEY
        with pytest.raises(Exception):TestVaultSingleton.decrypt('other-owner',row.encrypted_key)
    verified=logged.post('/api/v1/user-model/test',json={'expectedRevision':profile['revision']})
    assert verified.status_code==200 and verified.json()['profile']['verified'];assert len(gateway)==1
    request=json.loads(gateway[0].content);assert request['max_tokens']==32 and request['messages']==[{'role':'user','content':'Reply briefly with OK.'}]
    profile=save(logged,profile,apiKey=None,model='new-model',baseUrl='https://other.example.com/v1')
    assert profile['model']=='new-model' and profile['hasApiKey'] and not profile['verified']
    assert len(gateway)==1
    profile=save(logged,profile,apiKey='new-synthetic-key')
    with SessionLocal() as db:assert TestVaultSingleton.decrypt(owner,db.get(UserModelProfile,owner).encrypted_key)=='new-synthetic-key'
    profile=save(logged,profile,apiKey=None,clearKey=True)
    assert not profile['hasApiKey'] and not profile['verified']
    assert logged.post('/api/v1/user-model/test',json={'expectedRevision':profile['revision']}).json()['error']['code']=='MODEL_NOT_CONFIGURED'
    assert logged.request('DELETE','/api/v1/user-model',json={'expectedRevision':profile['revision']}).status_code==204
    assert logged.get('/api/v1/user-model').json()['profile'] is None
    assert KEY not in caplog.text and 'new-synthetic-key' not in caplog.text

@pytest.mark.parametrize('url',[
 'http://example.com/v1','https://127.0.0.1/v1','https://10.0.0.1/v1','https://169.254.169.254/latest',
 'https://[::1]/v1','https://[::ffff:127.0.0.1]/v1','https://100.64.0.1/v1','https://localhost/v1',
 'https://internal.local/v1','https://user:pass@example.com/v1','https://example.com:8443/v1',
 'https://example.com/v1?key=not-real','https://example.com/v1#x','https://example.com/%2e%2e/v1',
 'https://example.com/../v1','https://example.com\\@127.0.0.1/v1','https://2130706433/v1',
 'https://127.1/v1','https://0177.0.0.1/v1','https://example.com./v1',
])
def test_unsafe_urls_never_saved_or_called(logged,gateway,url):
    response=logged.put('/api/v1/user-model',json=body(baseUrl=url))
    assert response.status_code==422,response.text
    assert response.json()['error']['code']=='MODEL_URL_UNSAFE'
    assert not gateway and logged.get('/api/v1/user-model').json()['profile'] is None

@pytest.mark.parametrize('addresses',[['127.0.0.1'],['169.254.169.254'],['93.184.216.34','10.1.2.3'],['::1'],['64:ff9b::7f00:1']])
def test_dns_rebinding_and_mixed_answers_rejected(monkeypatch,addresses):
    async def run():
        async def answers(*args,**kwargs):return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443)) for ip in addresses]
        monkeypatch.setattr(asyncio.get_running_loop(),'getaddrinfo',answers)
        with pytest.raises(ai_service.ModelFailure) as exc:await model_network.resolve_public('model.example.com',443)
        assert exc.value.code=='MODEL_URL_UNSAFE'
    asyncio.run(run())

def test_actual_transport_pins_public_ip_preserves_tls_host_and_does_not_redirect(monkeypatch):
    writes=[];connects=[];tls=[]
    class Stream:
        async def write(self,data,timeout=None):writes.append(data)
        async def read(self,max_bytes,timeout=None):
            return b'HTTP/1.1 302 Found\r\nContent-Length: 0\r\nLocation: http://127.0.0.1/private\r\nConnection: close\r\n\r\n'
        async def start_tls(self,ssl_context,server_hostname,timeout=None):
            tls.append((server_hostname,ssl_context.check_hostname));return self
        def get_extra_info(self,name):return None
        async def aclose(self):pass
    async def resolve(host,port):assert host=='model.example.com';return ['93.184.216.34']
    async def connect(self,host,port,**kwargs):connects.append((host,port));return Stream()
    monkeypatch.setattr(model_network,'resolve_public',resolve)
    monkeypatch.setattr(model_network.AutoBackend,'connect_tcp',connect)
    profile=ai_service.ModelProfile('openai_compatible','https://model.example.com/v1','model',SecretStr(KEY),scope='user',owner_user_id='owner',verified=True)
    with pytest.raises(ai_service.ModelFailure) as exc:asyncio.run(ai_service.OpenAICompatible().complete([{'role':'user','content':'Synthetic'}],profile))
    assert exc.value.code=='MODEL_UNAVAILABLE'
    assert connects==[('93.184.216.34',443)] and tls==[('model.example.com',True)]
    assert b'POST /v1/chat/completions' in b''.join(writes)
    assert b'Host: model.example.com' in b''.join(writes)

@pytest.mark.parametrize('status,expected',[(401,'MODEL_AUTH'),(403,'MODEL_AUTH'),(404,'MODEL_NOT_FOUND'),(402,'MODEL_QUOTA'),(429,'MODEL_QUOTA'),(500,'MODEL_UNAVAILABLE'),(302,'MODEL_UNAVAILABLE'),(200,'MODEL_INVALID_RESPONSE')])
def test_probe_failure_no_echo_no_verification_no_fallback(logged,monkeypatch,status,expected,caplog):
    profile=save(logged);original=httpx.AsyncClient;calls=[]
    def handle(request):calls.append(request);return httpx.Response(status,json={'error':KEY,'choices':[]},headers={'Location':'http://127.0.0.1/'})
    monkeypatch.setattr(ai_service.httpx,'AsyncClient',lambda **kw:original(**{**kw,'transport':httpx.MockTransport(handle)}))
    response=logged.post('/api/v1/user-model/test',json={'expectedRevision':profile['revision']})
    assert response.json()['error']['code']==expected,response.text
    assert KEY not in response.text and KEY not in caplog.text and len(calls)==1
    assert not logged.get('/api/v1/user-model').json()['profile']['verified']

def test_probe_timeout_frequency_and_parallel_limits(logged,monkeypatch):
    profile=save(logged);calls=[]
    original=httpx.AsyncClient
    async def timeout(request):calls.append(1);raise httpx.ReadTimeout('synthetic upstream failure')
    monkeypatch.setattr(ai_service.httpx,'AsyncClient',lambda **kw:original(**{**kw,'transport':httpx.MockTransport(timeout)}))
    for _ in range(3):
        response=logged.post('/api/v1/user-model/test',json={'expectedRevision':profile['revision']})
        assert response.status_code==504 and response.json()['error']['code']=='MODEL_TIMEOUT'
    assert logged.post('/api/v1/user-model/test',json={'expectedRevision':profile['revision']}).status_code==429
    assert len(calls)==3
    user_models.probe_attempts.clear()
    assert user_models.probe_slots.acquire(False) and user_models.probe_slots.acquire(False)
    try:assert logged.post('/api/v1/user-model/test',json={'expectedRevision':profile['revision']}).json()['error']['code']=='MODEL_TEST_BUSY'
    finally:user_models.probe_slots.release();user_models.probe_slots.release()

def test_ownership_csrf_cas_and_aba(logged,gateway):
    a=save(logged)
    with TestClient(app,headers={'Origin':'http://localhost:8080'}) as b:
        register(b,'model-b@example.com');b.headers['X-CSRF-Token']=login(b,'model-b@example.com').json()['csrfToken']
        assert b.get('/api/v1/user-model').json()['profile'] is None
        assert b.post('/api/v1/user-model/test',json={'expectedRevision':a['revision']}).status_code==503
        assert b.request('DELETE','/api/v1/user-model',json={'expectedRevision':a['revision']}).status_code==409
        assert b.put('/api/v1/user-model',json=body(a)).status_code==409
        assert b.put('/api/v1/user-model',json=body(ownerId='forged')).status_code==422
        own=save(b,apiKey='account-b-synthetic-key')
        assert own['revision']!=a['revision']
        assert not gateway
    assert logged.put('/api/v1/user-model',json=body(a),headers={'X-CSRF-Token':'invalid'}).status_code==403
    new=save(logged,a,apiKey=None)
    assert logged.put('/api/v1/user-model',json=body(a)).status_code==409
    assert logged.request('DELETE','/api/v1/user-model',json={'expectedRevision':a['revision']}).status_code==409
    assert logged.request('DELETE','/api/v1/user-model',json={'expectedRevision':new['revision']}).status_code==204
    again=save(logged);assert again['revision']!=a['revision']
    assert logged.post('/api/v1/user-model/test',json={'expectedRevision':a['revision']}).status_code==409

def test_unauthenticated_and_expired_session(client,logged):
    from app.models import LoginSession
    from datetime import datetime,timedelta
    with TestClient(app,headers={'Origin':'http://localhost:8080'}) as c:
        for method,path,data in [('get','',None),('put','',body()),('delete','',{'expectedRevision':str(uuid4())}),('post','/test',{'expectedRevision':str(uuid4())})]:
            r=c.request(method,'/api/v1/user-model'+path,json=data);assert r.status_code==401
    with SessionLocal() as db:
        session=db.scalar(select(LoginSession));session.expires_at=datetime.now()-timedelta(days=1);db.commit()
    assert logged.get('/api/v1/user-model').status_code==401

def test_configuration_changed_during_probe_is_not_verified(logged,monkeypatch):
    profile=save(logged);owner=logged.get('/api/v1/users/me').json()['id']
    async def changed(*args):
        with SessionLocal() as db:row=db.get(UserModelProfile,owner);row.revision=str(uuid4());db.commit()
        return '[ISOLATED MOCK] OK'
    monkeypatch.setattr(ai_service.OpenAICompatible,'complete',changed)
    response=logged.post('/api/v1/user-model/test',json={'expectedRevision':profile['revision']})
    assert response.status_code==409
    assert not logged.get('/api/v1/user-model').json()['profile']['verified']

def test_user_translation_actual_resolver_receipt_and_note_save(logged,gateway):
    profile=save(logged)
    document=upload(logged,synthetic_pdf([TEXT]),'Public model fixture.pdf').json()
    request={'text':TEXT,'sourceLanguage':'en','targetLanguage':'zh','pageNumber':1,'contextRevision':4,'modelSource':'user','modelRevision':profile['revision']}
    endpoint='/api/v1/documents/'+document['id']+'/translations'
    assert logged.post(endpoint,json=request).status_code==503
    assert not gateway
    assert logged.post('/api/v1/user-model/test',json={'expectedRevision':profile['revision']}).status_code==200
    for source,target in [('en','zh'),('zh','en')]:
        request.update(sourceLanguage=source,targetLanguage=target)
        response=logged.post(endpoint,json=request);assert response.status_code==200,response.text
        result=response.json();assert result['modelConfiguration']=={'source':'user','revision':profile['revision']}
        assert KEY not in response.text and result['translationProof']['provenance']=='isolated_mock'
        content=json.loads(gateway[-1].content);assert content['model']=='mock-chat'
        assert gateway[-1].headers['authorization']=='Bearer '+KEY
    request.update(sourceLanguage='en',targetLanguage='zh')
    result=logged.post(endpoint,json=request).json()
    capture=capture_payload(document,kind='translation_excerpt',originalText=result['originalText'],translatedText=result['translatedText'],sourceLanguage='en',targetLanguage='zh',translationProof=result['translationProof'])
    saved=send(logged,capture);assert saved.status_code==201,saved.text
    assert saved.json()['note']['sources'][0]['translationProvenance']=='isolated_mock'
    updated=save(logged,profile,model='changed-model',apiKey=None)
    assert logged.post(endpoint,json=request).status_code==409
    request['modelRevision']=updated['revision']
    assert logged.post(endpoint,json=request).status_code==503
    assert logged.post('/api/v1/user-model/test',json={'expectedRevision':updated['revision']}).status_code==200
    assert logged.post(endpoint,json=request).status_code==200
    assert json.loads(gateway[-1].content)['model']=='changed-model'

def test_no_vault_no_plaintext_fallback(logged,monkeypatch,gateway):
    class Missing:available=False
    monkeypatch.setattr(user_models,'get_secret_vault',lambda:Missing())
    assert logged.get('/api/v1/user-model').json()=={'available':False,'profile':None}
    assert logged.put('/api/v1/user-model',json=body()).status_code==503
    assert not gateway

@pytest.mark.skipif(os.name!='nt',reason='Windows DPAPI capability only; no plaintext substitute')
def test_windows_dpapi_roundtrip_owner_bound_and_tamper():
    vault=WindowsSecretVault();cipher=vault.encrypt('synthetic-owner',KEY)
    assert KEY.encode() not in cipher and vault.decrypt('synthetic-owner',cipher)==KEY
    with pytest.raises(ai_service.ModelFailure):vault.decrypt('other-owner',cipher)
    with pytest.raises(ai_service.ModelFailure):vault.decrypt('synthetic-owner',cipher[:-1]+bytes([cipher[-1]^1]))


def test_user_translation_changed_during_request_rejected(logged,gateway,monkeypatch):
    profile=save(logged)
    assert logged.post('/api/v1/user-model/test',json={'expectedRevision':profile['revision']}).status_code==200
    document=upload(logged,synthetic_pdf([TEXT]),'Public stale model.pdf').json()
    owner=logged.get('/api/v1/users/me').json()['id']
    async def changed(*args):
        with SessionLocal() as db:
            row=db.get(UserModelProfile,owner);row.revision=str(uuid4());row.tested_revision=None;db.commit()
        return '[ISOLATED MOCK] old reply'
    monkeypatch.setattr(ai_service.OpenAICompatible,'complete',changed)
    response=logged.post('/api/v1/documents/'+document['id']+'/translations',json={'text':TEXT,'sourceLanguage':'en','targetLanguage':'zh','pageNumber':1,'contextRevision':1,'modelSource':'user','modelRevision':profile['revision']})
    assert response.status_code==409 and response.json()['error']['code']=='MODEL_PROFILE_CHANGED'
    assert 'translationProof' not in response.json()


def test_other_account_cannot_select_another_model_revision(logged,gateway):
    a=save(logged)
    with TestClient(app,headers={'Origin':'http://localhost:8080'}) as b:
        register(b,'other-model-owner@example.com');b.headers['X-CSRF-Token']=login(b,'other-model-owner@example.com').json()['csrfToken']
        doc=upload(b,synthetic_pdf([TEXT]),'Own document.pdf').json()
        own=save(b,apiKey='synthetic-other-account-key')
        assert b.post('/api/v1/user-model/test',json={'expectedRevision':own['revision']}).status_code==200
        count=len(gateway)
        data={'text':TEXT,'sourceLanguage':'en','targetLanguage':'zh','pageNumber':1,'contextRevision':1,'modelSource':'user','modelRevision':a['revision']}
        endpoint='/api/v1/documents/'+doc['id']+'/translations'
        assert b.post(endpoint,json=data).status_code==409 and len(gateway)==count
        data['modelRevision']=own['revision']
        assert b.post(endpoint,json=data).status_code==200
        assert gateway[-1].headers['authorization']=='Bearer synthetic-other-account-key'
