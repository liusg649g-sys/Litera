import asyncio
from types import SimpleNamespace
import httpx
import pytest
from pydantic import SecretStr
from fastapi.testclient import TestClient
from app import translations, model_service, ai_service
from app.main import app
from test_documents import pdf, logged, upload
from test_auth import register, login


async def adapter_call(settings):
    # Protocol-only unit test; application callers use ModelService and scoped resolution.
    profile=ai_service.ModelProfile('openai_compatible',settings.translation_base_url,settings.translation_model,settings.translation_api_key)
    return await ai_service.OpenAICompatible().complete([{'role':'user','content':'source'}],profile)

@pytest.fixture(autouse=True)
def reset_translation_limits():
    translations.attempts.clear()
    yield
    translations.attempts.clear()

def payload(**changes):
    return dict(text='A scientific paragraph.', sourceLanguage='en', targetLanguage='zh', pageNumber=1, contextRevision=7, **changes)

def test_translation_permission_direction_and_source(logged, pdf, monkeypatch):
    doc = upload(logged, pdf).json()
    calls=[]
    async def fake(text,source,target,settings,**kwargs):
        calls.append((text,source,target)); return 'Mock translation'
    monkeypatch.setattr(translations, 'translate_text', fake)
    for source,target in [('en','zh'),('zh','en')]:
        body=payload();body.update(sourceLanguage=source,targetLanguage=target)
        response=logged.post(f'/api/v1/documents/{doc["id"]}/translations',json=body)
        assert response.status_code==200
        result=response.json();assert result['originalText']==body['text']
        assert result['source']==dict(documentId=doc['id'],pageNumber=1,sourceLanguage=source,targetLanguage=target,contextRevision=7,sourceType='translation')
        assert calls[-1]==(body['text'],source,target)
    with TestClient(app,headers={'Origin':'http://localhost:8080'}) as other:
        assert other.post(f'/api/v1/documents/{doc["id"]}/translations',json=payload()).status_code==401
        register(other,'other-translation@example.com')
        other.headers['X-CSRF-Token']=login(other,'other-translation@example.com').json()['csrfToken']
        assert other.post(f'/api/v1/documents/{doc["id"]}/translations',json=payload()).status_code==404
    assert len(calls)==2

@pytest.mark.parametrize('changes',[{'text':''},{'text':'  '},{'text':'a'*6001},{'pageNumber':0},{'pageNumber':2},{'sourceLanguage':'fr'},{'targetLanguage':'en'},{'contextRevision':-1}])
def test_translation_validation(logged,pdf,changes):
    doc=upload(logged,pdf).json();body=payload();body.update(changes)
    assert logged.post(f'/api/v1/documents/{doc["id"]}/translations',json=body).status_code==422

def test_translation_csrf_and_not_configured(logged,pdf,monkeypatch):
    doc=upload(logged,pdf).json();url=f'/api/v1/documents/{doc["id"]}/translations'
    assert logged.post(url,json=payload(),headers={'X-CSRF-Token':'invalid'}).status_code==403
    monkeypatch.setattr(translations,'get_settings',lambda:SimpleNamespace(translation_provider='openai_compatible',translation_api_key=None))
    response=logged.post(url,json=payload())
    assert response.status_code==503 and response.json()['error']['code']=='TRANSLATION_NOT_CONFIGURED'

def test_translation_rate_and_concurrency(logged,pdf,monkeypatch):
    doc=upload(logged,pdf).json();url=f'/api/v1/documents/{doc["id"]}/translations'
    async def fake(*args,**kwargs):return 'Mock'
    monkeypatch.setattr(translations,'translate_text',fake)
    assert translations.slots.acquire(False) and translations.slots.acquire(False)
    try: assert logged.post(url,json=payload()).json()['error']['code']=='TRANSLATION_BUSY'
    finally:translations.slots.release();translations.slots.release()
    assert not translations.attempts[logged.get("/api/v1/auth/session").json()["user"]["id"]]
    for _ in range(20):assert logged.post(url,json=payload()).status_code==200
    assert logged.post(url,json=payload()).json()['error']['code']=='TRANSLATION_RATE_LIMIT'

@pytest.mark.parametrize('status,body,expected',[
    (401,{},'MODEL_AUTH'),(403,{},'MODEL_AUTH'),(402,{},'MODEL_QUOTA'),(429,{},'MODEL_QUOTA'),(500,{},'MODEL_UNAVAILABLE'),
    (200,{},'MODEL_INVALID_RESPONSE'),(200,{'choices':[{'message':{'content':''}}]},'MODEL_INVALID_RESPONSE'),
    (200,{'choices':[{'message':{'content':'unit-test-private-token'}}]},'MODEL_INVALID_RESPONSE'),
])
def test_adapter_errors_do_not_leak_credentials(status,body,expected,monkeypatch,caplog):
    secret='unit-test-private-token'
    settings=SimpleNamespace(translation_base_url='https://model.example/v1',translation_model='test-model',translation_api_key=SecretStr(secret))
    original=httpx.AsyncClient
    def handle(request):
        assert request.headers['Authorization']=='Bearer '+secret
        return httpx.Response(status,json=body)
    monkeypatch.setattr(ai_service.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handle),**kwargs))
    with pytest.raises(model_service.ModelFailure) as error:
        asyncio.run(adapter_call(settings))
    assert error.value.code==expected
    assert secret not in str(error.value) and secret not in error.value.message and secret not in caplog.text

def test_adapter_success_and_timeout(monkeypatch):
    settings=SimpleNamespace(translation_base_url='https://model.example/v1',translation_model='test-model',translation_api_key=SecretStr('test-private-token'))
    original=httpx.AsyncClient
    def good(request):return httpx.Response(200,json={'choices':[{'message':{'content':' translated text '}}]})
    monkeypatch.setattr(ai_service.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(good),**kwargs))
    assert asyncio.run(adapter_call(settings))=='translated text'
    def timeout(request):raise httpx.ReadTimeout('private upstream details')
    monkeypatch.setattr(ai_service.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(timeout),**kwargs))
    with pytest.raises(model_service.ModelFailure) as error:asyncio.run(adapter_call(settings))
    assert error.value.code=='MODEL_TIMEOUT' and 'private upstream' not in error.value.message


def test_adapter_unavailable_and_invalid_transport_are_sanitized(monkeypatch,caplog):
    settings=SimpleNamespace(translation_base_url='https://model.example/v1',translation_model='test-model',translation_api_key=SecretStr('test-private-token'))
    original=httpx.AsyncClient
    def unavailable(request):raise httpx.ConnectError('test-private-token private upstream')
    monkeypatch.setattr(ai_service.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(unavailable),**kwargs))
    with pytest.raises(model_service.ModelFailure) as failure:asyncio.run(adapter_call(settings))
    assert failure.value.code=='MODEL_UNAVAILABLE'
    assert 'test-private-token' not in failure.value.message and 'test-private-token' not in caplog.text
    settings.translation_base_url='http://public-model.example/v1'
    with pytest.raises(model_service.ModelFailure) as failure:asyncio.run(adapter_call(settings))
    assert failure.value.code=='MODEL_CONFIG'


@pytest.mark.parametrize('status',[200,401,429])
def test_api_adapter_integration_never_returns_upstream_secret(logged,pdf,monkeypatch,caplog,status):
    doc=upload(logged,pdf).json();secret='translation-only-test-key'
    settings=SimpleNamespace(translation_model_verified=True,translation_provider='openai_compatible',translation_base_url='https://model.example/v1',translation_model='test-model',translation_api_key=SecretStr(secret))
    monkeypatch.setattr(translations,'get_settings',lambda:settings)
    original=httpx.AsyncClient
    def handle(request):
        assert str(request.url)=='https://model.example/v1/chat/completions'
        return httpx.Response(status,json={'choices':[{'message':{'content':'Mock integrated translation'}}]} if status==200 else {'error':secret})
    monkeypatch.setattr(ai_service.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handle),**kwargs))
    response=logged.post(f'/api/v1/documents/{doc["id"]}/translations',json=payload())
    assert response.status_code==(200 if status==200 else 429 if status==429 else 503)
    assert secret not in response.text and secret not in caplog.text
    assert response.headers['X-Translation-Gateway-Status']==str(status)
    assert all(name+';dur=' in response.headers['Server-Timing'] for name in ('translation','pdf','gateway'))
    assert secret not in str(response.headers)
    if status==200:assert response.json()['translatedText']=='Mock integrated translation'
    else:assert response.json()['error']['code']==('MODEL_QUOTA' if status==429 else 'MODEL_AUTH')


def test_model_file_is_ignored_in_test_environment(tmp_path,monkeypatch):
    from app.config import TranslationSettings,get_translation_settings
    # A supplied model file is supported, but the normal test entry cannot read private backend/.env.
    fake=tmp_path/'model.env';fake.write_text('TRANSLATION_MODEL=example-model\nTRANSLATION_API_KEY=test-private-key\n')
    configured=TranslationSettings(_env_file=fake)
    assert configured.translation_model=='example-model'
    monkeypatch.delenv('TRANSLATION_MODEL',raising=False)
    monkeypatch.delenv('TRANSLATION_API_KEY',raising=False)
    monkeypatch.setenv('APP_ENV','test');get_translation_settings.cache_clear()
    try:
        clean=get_translation_settings()
        assert clean.translation_api_key is None and clean.translation_model==''
    finally:get_translation_settings.cache_clear()


@pytest.mark.parametrize('wrong_owner',[False,True])
def test_request_scoped_user_resolver_can_replace_local_config(logged,pdf,monkeypatch,wrong_owner):
    doc=upload(logged,pdf).json();user=logged.get('/api/v1/auth/session').json()['user']['id']
    class Resolver:
        def resolve(self,principal_id,capability):
            assert principal_id==user and capability=='translation'
            return ai_service.ModelProfile('user-adapter','https://model.example/v1','private-user-model',SecretStr('only-this-user-key'),'user','other' if wrong_owner else user,True)
    class FakeAdapter:
        async def complete(self,messages,profile):return 'Mock user-scoped translation'
    monkeypatch.setattr(ai_service,'ADAPTERS',{'user-adapter':FakeAdapter()})
    app.dependency_overrides[translations.model_resolver]=lambda:Resolver()
    try:
        response=logged.post(f'/api/v1/documents/{doc["id"]}/translations',json=payload())
        assert response.status_code==(403 if wrong_owner else 200)
        assert 'only-this-user-key' not in response.text
        if not wrong_owner:assert response.json()['translatedText']=='Mock user-scoped translation'
    finally:app.dependency_overrides.pop(translations.model_resolver,None)


def test_pdf_read_failure_returns_safe_error(logged,pdf,monkeypatch):
    from pypdf.errors import PdfReadError
    doc=upload(logged,pdf).json()
    def damaged(*args,**kwargs):raise PdfReadError('private path and internal detail')
    monkeypatch.setattr(translations,'PdfReader',damaged)
    response=logged.post(f'/api/v1/documents/{doc["id"]}/translations',json=payload())
    assert response.status_code==422 and response.json()['error']['code']=='PDF_UNAVAILABLE'
    assert 'private path' not in response.text and 'Traceback' not in response.text


@pytest.mark.parametrize('text',['English \u0003 text','\ufffd','\ue001'])
def test_unreliable_characters_never_reach_model(logged,pdf,monkeypatch,text):
    from unittest.mock import AsyncMock
    fake=AsyncMock();monkeypatch.setattr(translations,'translate_text',fake)
    doc=upload(logged,pdf).json();body=payload();body['text']=text
    response=logged.post(f'/api/v1/documents/{doc["id"]}/translations',json=body)
    assert response.status_code==422 and response.json()['error']['code']=='PDF_TEXT_UNRELIABLE'
    fake.assert_not_called()

def test_opaque_font_mapping_blocks_even_printable_fragment(logged,monkeypatch):
    from io import BytesIO
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,ArrayObject,NumberObject
    from unittest.mock import AsyncMock
    writer=PdfWriter();page=writer.add_blank_page(width=200,height=300)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica'),NameObject('/Encoding'):DictionaryObject({NameObject('/Type'):NameObject('/Encoding'),NameObject('/Differences'):ArrayObject([NumberObject(1),NameObject('/G01'),NameObject('/G02')])})})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
    out=BytesIO();writer.write(out);doc=upload(logged,out.getvalue()).json()
    fake=AsyncMock();monkeypatch.setattr(translations,'translate_text',fake)
    body=payload();body['text']='123'
    response=logged.post(f'/api/v1/documents/{doc["id"]}/translations',json=body)
    assert response.status_code==422 and response.json()['error']['code']=='PDF_TEXT_UNRELIABLE'
    fake.assert_not_called()


@pytest.mark.parametrize('source,target,expected_joins',[('en','zh',3),('zh','en',0)])
def test_pdf_dehyphenation_uses_separate_model_text_and_preserves_raw(logged,monkeypatch,source,target,expected_joins):
    from test_pdf_text import line_pdf
    raw='Some disor-\nders and thera-\npies with ul-\ntrasound.'
    data=line_pdf([(40,700,'Some disor-'),(40,684,'ders and thera-'),(40,668,'pies with ul-'),(40,652,'trasound.')])
    doc=upload(logged,data).json();calls=[]
    async def fake(text,*args,**kwargs):calls.append(text);return 'Mock translation, not a real model'
    monkeypatch.setattr(translations,'translate_text',fake)
    body=payload();body.update(text=raw,sourceLanguage=source,targetLanguage=target)
    response=logged.post(f'/api/v1/documents/{doc["id"]}/translations',json=body)
    assert response.status_code==200
    result=response.json();assert result['originalText']==raw
    assert result['source']['documentId']==doc['id'] and result['source']['pageNumber']==1
    expected='Some disorders and therapies with ultrasound.' if expected_joins else raw
    assert calls==[expected]
    if expected_joins:
        assert result['modelInputText']==expected and result['normalizationCount']==expected_joins
    else:
        assert 'modelInputText' not in result and 'normalizationCount' not in result


def test_pdf_quality_guard_runs_before_optional_dehyphenation(logged,pdf,monkeypatch):
    from unittest.mock import Mock,AsyncMock
    doc=upload(logged,pdf).json();normalizer=Mock();model=AsyncMock()
    monkeypatch.setattr(translations,'model_input_text',normalizer)
    monkeypatch.setattr(translations,'translate_text',model)
    body=payload();body['text']='disor-\n\u0003ders'
    response=logged.post(f'/api/v1/documents/{doc["id"]}/translations',json=body)
    assert response.status_code==422 and response.json()['error']['code']=='PDF_TEXT_UNRELIABLE'
    normalizer.assert_not_called();model.assert_not_called()


def test_busy_has_local_timing_and_never_claims_gateway_status(logged,pdf,caplog):
    import logging
    caplog.set_level(logging.INFO,logger='uvicorn.error')
    doc=upload(logged,pdf).json();assert translations.slots.acquire(False) and translations.slots.acquire(False)
    try:
        response=logged.post(f'/api/v1/documents/{doc["id"]}/translations',json=payload())
    finally:translations.slots.release();translations.slots.release()
    assert response.status_code==429 and response.json()['error']['code']=='TRANSLATION_BUSY'
    assert response.headers['X-Translation-Gateway-Status']=='0'
    assert 'gateway;dur=0.00' in response.headers['Server-Timing']
    assert 'code=TRANSLATION_BUSY' in caplog.text and 'upstream_status=-' in caplog.text
    assert payload()['text'] not in caplog.text and doc['id'] not in caplog.text


def test_timing_context_does_not_leak_between_requests(logged,pdf,monkeypatch):
    from app.translation_runtime import current_timing
    doc=upload(logged,pdf).json();seen=[]
    async def fake(*args,**kwargs):
        metrics=current_timing.get();seen.append(metrics)
        assert metrics.gateway_calls==0 and metrics.gateway_status is None
        metrics.gateway_calls=1;metrics.gateway_status=200;metrics.gateway_ms=12.5
        return 'Mock timed'
    monkeypatch.setattr(translations,'translate_text',fake)
    for _ in range(2):
        response=logged.post(f'/api/v1/documents/{doc["id"]}/translations',json=payload())
        assert response.status_code==200 and response.headers['X-Translation-Gateway-Status']=='200'
    assert seen[0] is not seen[1] and current_timing.get() is None
