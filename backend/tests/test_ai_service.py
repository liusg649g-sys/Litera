import asyncio
from types import SimpleNamespace
import pytest
from pydantic import SecretStr
from app.ai_service import ModelProfile, ModelService, ModelFailure, DeveloperProfileResolver

class FakeAdapter:
    def __init__(self): self.seen=[]
    async def complete(self,messages,profile):
        self.seen.append((profile.owner_user_id,profile.model))
        return 'Mock '+profile.model

def profile(provider='a',owner='one',verified=True,scope='user'):
    return ModelProfile(provider,'https://model.example/v1',owner+'-model',SecretStr('private-key-'+owner),scope,owner if scope=='user' else None,verified)

def test_providers_switch_without_business_changes():
    first,second=FakeAdapter(),FakeAdapter();service=ModelService({'a':first,'b':second})
    assert asyncio.run(service.complete([{'role':'user','content':'sample'}],'one',profile()))=='Mock one-model'
    assert asyncio.run(service.complete([{'role':'user','content':'sample'}],'two',profile('b','two')))=='Mock two-model'
    assert first.seen==[('one','one-model')] and second.seen==[('two','two-model')]

def test_user_credentials_cannot_cross_principals_or_enter_repr():
    adapter=FakeAdapter();service=ModelService({'a':adapter});p=profile()
    assert 'private-key-one' not in repr(p)
    with pytest.raises(ModelFailure) as failure:asyncio.run(service.complete([],'two',p))
    assert failure.value.status==403 and not adapter.seen
    with pytest.raises(ModelFailure):asyncio.run(service.complete([],'',p))

@pytest.mark.parametrize('configured',[profile(verified=False),profile('missing')])
def test_unverified_and_unsupported_profiles_never_call_adapter(configured):
    adapter=FakeAdapter()
    with pytest.raises(ModelFailure) as failure:asyncio.run(ModelService({'a':adapter}).complete([],'one',configured))
    assert failure.value.code=='MODEL_NOT_CONFIGURED' and not adapter.seen

def test_uniform_layer_rejects_secret_echo_from_any_adapter():
    class Unsafe:
        async def complete(self,messages,config):return config.api_key.get_secret_value()
    with pytest.raises(ModelFailure) as failure:asyncio.run(ModelService({'a':Unsafe()}).complete([],'one',profile()))
    assert failure.value.code=='MODEL_INVALID_RESPONSE'
    assert 'private-key' not in failure.value.message

def test_developer_config_is_explicit_not_a_user_credential_store():
    s=SimpleNamespace(translation_provider='a',translation_base_url='https://model.example/v1',translation_model='local-model',translation_api_key=SecretStr('developer-private-key'),translation_model_verified=False)
    resolver=DeveloperProfileResolver(s);config=resolver.resolve('one','translation')
    assert config.scope=='developer' and config.owner_user_id is None and not config.verified
    with pytest.raises(ModelFailure):resolver.resolve('','translation')
    with pytest.raises(ModelFailure):resolver.resolve('one','unimplemented-capability')


def test_unified_configuration_and_legacy_aliases(tmp_path,monkeypatch):
    from app.config import ModelSettings
    names=['AI_PROVIDER','AI_BASE_URL','AI_MODEL','AI_API_KEY','AI_MODEL_VERIFIED','TRANSLATION_PROVIDER','TRANSLATION_BASE_URL','TRANSLATION_MODEL','TRANSLATION_API_KEY','TRANSLATION_MODEL_VERIFIED']
    for name in names:monkeypatch.delenv(name,raising=False)
    path=tmp_path/'developer.env';path.write_text('AI_MODEL=unified-model\nTRANSLATION_MODEL=legacy-model\nAI_API_KEY=private-key\nAI_MODEL_VERIFIED=true\n')
    settings=ModelSettings(_env_file=path)
    assert settings.model==settings.translation_model=='unified-model' and settings.verified
    assert 'private-key' not in repr(settings)
    assert ModelSettings(_env_file=None).verified is False


def test_output_budget_is_sent_and_truncated_response_is_not_success(monkeypatch):
    import httpx, json
    from dataclasses import replace
    from app import ai_service
    original=httpx.AsyncClient
    def reply(request):
        assert json.loads(request.content)['max_tokens']==128
        return httpx.Response(200,json={'choices':[{'message':{'content':'partial text'},'finish_reason':'length'}]})
    monkeypatch.setattr(ai_service.httpx,'AsyncClient',lambda **kwargs: original(**{**kwargs,'transport':httpx.MockTransport(reply)}))
    with pytest.raises(ModelFailure) as error:
        asyncio.run(ai_service.OpenAICompatible().complete([],replace(profile(),max_output_tokens=128)))
    assert error.value.code=='MODEL_OUTPUT_LIMIT'


def test_invalid_output_budget_never_connects():
    from dataclasses import replace
    from app.ai_service import OpenAICompatible
    with pytest.raises(ModelFailure) as error:
        asyncio.run(OpenAICompatible().complete([],replace(profile(),max_output_tokens=50000)))
    assert error.value.code=='MODEL_CONFIG'


def test_synthetic_probe_limits_calls_and_does_not_change_verification():
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('verify_model',Path(__file__).resolve().parents[2]/'scripts/verify_model.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    settings=SimpleNamespace(translation_provider='openai_compatible',translation_base_url='https://model.example/v1',translation_model='test-model',translation_api_key=SecretStr('private-probe-key'),translation_model_verified=False)
    class MockProbe:
        def __init__(self):self.calls=[]
        async def complete(self,messages,p):
            assert p.max_output_tokens==128 and not p.verified
            self.calls.append(messages)
            return 'Mock translation'
    adapter=MockProbe();results=asyncio.run(module.probe(settings,adapter))
    assert len(adapter.calls)==2 and len(results)==2 and not settings.translation_model_verified
    assert [result['sourceLanguage'] for result in results]==['en','zh']
    class FailingProbe:
        def __init__(self):self.calls=0
        async def complete(self,*args):
            self.calls+=1
            raise ModelFailure('MODEL_AUTH','safe error')
    adapter=FailingProbe()
    with pytest.raises(ModelFailure):asyncio.run(module.probe(settings,adapter))
    assert adapter.calls==1


@pytest.mark.parametrize('choice',[None,[], 'not-an-object', {'message':None}])
def test_invalid_choice_shape_is_a_safe_failure(monkeypatch,choice,caplog):
    import httpx
    from app import ai_service
    original=httpx.AsyncClient
    monkeypatch.setattr(ai_service.httpx,'AsyncClient',lambda **kwargs: original(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'choices':[choice]})),**kwargs))
    with pytest.raises(ModelFailure) as error:
        asyncio.run(ai_service.OpenAICompatible().complete([],profile()))
    assert error.value.code=='MODEL_INVALID_RESPONSE'
    assert 'private-key' not in error.value.message and 'private-key' not in caplog.text
