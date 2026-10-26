"""Synthetic keys only. AES is exercised on this OS; POSIX checks skip on Windows.
No existing model profile or real ciphertext is read or migrated.
"""
import base64,importlib.util,os,sqlite3
from pathlib import Path
from copy import copy
import pytest
from sqlalchemy import select
from app import model_secrets,user_models
from app.ai_service import ModelFailure
from app.config import get_settings
from app.database import SessionLocal,engine
from app.models import UserModelProfile
from test_documents import logged
from test_user_models import enable,gateway,save,KEY

@pytest.fixture
def keyfile(tmp_path):
    path=tmp_path/'synthetic-master.key';path.write_bytes(base64.urlsafe_b64encode(os.urandom(32)))
    path.chmod(0o600);return path

def test_aes_roundtrip_random_nonce_owner_binding_tamper_and_wrong_key(keyfile,tmp_path):
    vault=model_secrets.AesGcmFileVault(str(keyfile));assert vault.available
    a=vault.encrypt('owner',KEY);b=vault.encrypt('owner',KEY)
    assert a!=b and KEY.encode() not in a and vault.decrypt('owner',a)==KEY
    for owner,value in [('other',a),('owner',a[:-1]+bytes([a[-1]^1])),('owner',b'not-a-valid-envelope')]:
        with pytest.raises(ModelFailure) as exc:vault.decrypt(owner,value)
        assert exc.value.code=='MODEL_VAULT_UNAVAILABLE' and KEY not in str(exc.value)
    keyfile.write_bytes(base64.urlsafe_b64encode(os.urandom(32)))
    with pytest.raises(ModelFailure):vault.decrypt('owner',a)

@pytest.mark.parametrize('content',[b'',b'not base64!',base64.urlsafe_b64encode(b'too short'),b'x'*129])
def test_invalid_key_file_fails_closed_without_echo(tmp_path,content):
    file=tmp_path/'invalid.key';file.write_bytes(content);file.chmod(0o600)
    vault=model_secrets.AesGcmFileVault(str(file));assert not vault.available
    with pytest.raises(ModelFailure):vault.encrypt('owner',KEY)

def test_missing_relative_directory_paths_fail_closed(tmp_path):
    for value in ['', 'relative.key',str(tmp_path/'missing'),str(tmp_path)]:
        vault=model_secrets.AesGcmFileVault(value);assert not vault.available
        with pytest.raises(ModelFailure):vault.encrypt('owner',KEY)

@pytest.mark.skipif(os.name=='nt',reason='Actual POSIX mode/symlink enforcement requires Linux; crypto tests run on Windows')
def test_posix_rejects_world_readable_and_symlink_key(keyfile,tmp_path):
    vault=model_secrets.AesGcmFileVault(str(keyfile));keyfile.chmod(0o644);assert not vault.available
    keyfile.chmod(0o600);assert vault.available
    link=tmp_path/'link.key';link.symlink_to(keyfile)
    assert not model_secrets.AesGcmFileVault(str(link)).available

def test_selection_preserves_windows_auto_and_does_not_fall_back_for_explicit_aes(keyfile,monkeypatch):
    settings=get_settings();monkeypatch.setattr(settings,'user_model_master_key_file',str(keyfile));monkeypatch.setattr(settings,'user_model_secret_backend','auto')
    selected=model_secrets.get_secret_vault()
    assert isinstance(selected,model_secrets.WindowsSecretVault if os.name=='nt' else model_secrets.AesGcmFileVault)
    monkeypatch.setattr(settings,'user_model_secret_backend','aesgcm_file')
    assert isinstance(model_secrets.get_secret_vault(),model_secrets.AesGcmFileVault)
    monkeypatch.setattr(settings,'user_model_master_key_file','')
    assert not model_secrets.get_secret_vault().available

def test_existing_scheme_not_migrated_and_explicit_key_change_uses_aes_on_temporary_backup(logged,gateway,keyfile,tmp_path,monkeypatch):
    profile=save(logged);assert logged.post('/api/v1/user-model/test',json={'expectedRevision':profile['revision']}).status_code==200
    owner=logged.get('/api/v1/users/me').json()['id']
    with SessionLocal() as db:old=db.get(UserModelProfile,owner).encrypted_key
    backup=tmp_path/'synthetic-before.db';restored=tmp_path/'synthetic-restored.db'
    assert engine.url.get_backend_name()=='sqlite'
    with sqlite3.connect(Path(engine.url.database).as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(backup) as target:source.backup(target)
    restored.write_bytes(backup.read_bytes())
    with sqlite3.connect(restored.as_uri()+'?mode=ro',uri=True) as db:
        assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert db.execute('select encrypted_key from user_model_profiles').fetchone()[0]==old
    vault=model_secrets.AesGcmFileVault(str(keyfile));monkeypatch.setattr(user_models,'get_secret_vault',lambda:vault)
    assert not logged.get('/api/v1/user-model').json()['profile']['verified']
    refused=logged.post('/api/v1/user-model/test',json={'expectedRevision':profile['revision']});assert refused.status_code==503 and refused.json()['error']['code']=='MODEL_VAULT_UNAVAILABLE'
    with SessionLocal() as db:assert db.get(UserModelProfile,owner).encrypted_key==old
    updated=save(logged,profile,apiKey='synthetic-new-key')
    with SessionLocal() as db:
        row=db.get(UserModelProfile,owner);assert row.encryption_scheme==vault.scheme
        assert vault.decrypt(owner,row.encrypted_key)=='synthetic-new-key'
    assert logged.post('/api/v1/user-model/test',json={'expectedRevision':updated['revision']}).status_code==200
    assert len(gateway)==2 # refused old format never called a provider

def test_external_master_key_generator_is_exclusive_and_never_prints(tmp_path,capsys):
    spec=importlib.util.spec_from_file_location('init_model_key',Path(__file__).resolve().parents[2]/'scripts/init_model_key.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    file=tmp_path/'new.key';assert module.create_key(file)==file
    raw=file.read_bytes();assert len(base64.urlsafe_b64decode(raw))==32
    with pytest.raises(FileExistsError):module.create_key(file)
    assert file.read_bytes()==raw
    with pytest.raises(ValueError):module.create_key(module.ROOT/'unsafe.key')
    assert capsys.readouterr().out==''
