"""Unified modes: temporary SQLite and controlled HTTP transport. ZERO real model calls.
Production-like provenance is exercised with MockTransport, not a real provider.
"""
from copy import deepcopy
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.config import get_settings
from app.acceptance_site import mount_acceptance_site
from test_documents import logged, upload
from test_note_captures import synthetic_pdf, TEXT, payload, send
from test_user_models import enable, gateway, save, KEY

@pytest.fixture
def unified(monkeypatch):
    settings=get_settings()
    monkeypatch.setattr(settings,'app_env','development')
    monkeypatch.setattr(settings,'unified_acceptance',True)
    monkeypatch.setattr(settings,'translation_mock_enabled',True)
    return settings

def selection(**changes):
    value=dict(text=TEXT,sourceLanguage='en',targetLanguage='zh',pageNumber=1,contextRevision=4,modelSource='mock')
    value.update(changes);return value

def capture(client,doc,result):
    return send(client,payload(doc,kind='translation_excerpt',originalText=result['originalText'],translatedText=result['translatedText'],sourceLanguage='en',targetLanguage='zh',translationProof=result['translationProof']))

def test_unified_explicit_modes_keep_distinct_signed_provenance(logged,unified,gateway):
    options=logged.get('/api/v1/user-model/options').json()
    assert options==dict(mockEnabled=True,userEnabled=True,developerEnabled=False,defaultSource='mock',unifiedAcceptance=True)
    assert not gateway
    doc=upload(logged,synthetic_pdf([TEXT]),'Public combined-mode fixture.pdf').json()
    path='/api/v1/documents/'+doc['id']+'/translations'
    blocked=logged.post(path,json=selection(modelSource='developer'))
    assert blocked.status_code==403 and blocked.json()['error']['code']=='DEVELOPER_MODEL_DISABLED'
    mock=logged.post(path,json=selection());assert mock.status_code==200,mock.text
    fake=mock.json();assert fake['translationProof']['provenance']=='isolated_mock'
    assert fake['modelConfiguration']=={'source':'mock'} and 'Mock' in fake['translatedText']
    assert not gateway
    saved=capture(logged,doc,fake);assert saved.status_code==201,saved.text
    assert saved.json()['note']['sources'][0]['translationProvenance']=='isolated_mock'
    profile=save(logged)
    assert not gateway # saving a profile never calls a provider
    assert logged.post('/api/v1/user-model/test',json={'expectedRevision':profile['revision']}).status_code==200
    own=logged.post(path,json=selection(modelSource='user',modelRevision=profile['revision']))
    assert own.status_code==200,own.text
    real_branch=own.json()
    assert real_branch['translationProof']['provenance']=='model_api' # branch test only, transport is Mock
    assert real_branch['modelConfiguration']==dict(source='user',revision=profile['revision'])
    saved=capture(logged,doc,real_branch);assert saved.status_code==201,saved.text
    assert saved.json()['note']['sources'][0]['translationProvenance']=='model_api'
    assert len(gateway)==2 and KEY not in own.text and KEY not in saved.text
    for result in (fake,real_branch):
        forged=deepcopy(result)
        forged['translationProof']['provenance']='model_api' if result is fake else 'isolated_mock'
        rejected=capture(logged,doc,forged)
        assert rejected.status_code==422 and rejected.json()['error']['code']=='TRANSLATION_PROOF_INVALID'

def test_unified_mock_disabled_never_calls_model_and_personal_missing_never_falls_back(logged,unified,gateway,monkeypatch):
    doc=upload(logged,synthetic_pdf([TEXT]),'Explicit mode.pdf').json()
    path='/api/v1/documents/'+doc['id']+'/translations'
    monkeypatch.setattr(unified,'translation_mock_enabled',False)
    denied=logged.post(path,json=selection())
    assert denied.status_code==403 and denied.json()['error']['code']=='MOCK_DISABLED'
    assert logged.post(path,json=selection(modelSource='user',modelRevision='missing')).status_code!=200
    assert not gateway

def test_spa_routes_preserve_api_404_and_never_expose_files(tmp_path):
    web=tmp_path/'web';web.mkdir()
    (web/'index.html').write_text('<html>Unified frontend</html>')
    (web/'app.js').write_text('/* public bundle */')
    (tmp_path/'private.txt').write_text('not-public')
    app=FastAPI()
    @app.get('/api/v1/health')
    def health():return {'status':'ok'}
    mount_acceptance_site(app,web)
    with TestClient(app) as client:
        for path in ['/','/login','/settings/ai','/reader/synthetic']:
            response=client.get(path)
            assert response.status_code==200 and 'Unified frontend' in response.text,path
            assert response.headers['cache-control']=='no-store'
        assert client.get('/api/v1/health').json()=={'status':'ok'}
        for path in ['/api/v1/not-found','/missing.js','/private.txt','/..%2fprivate.txt']:
            response=client.get(path);assert response.status_code==404 and 'not-public' not in response.text,path
        assert client.get('/app.js').text=='/* public bundle */'
