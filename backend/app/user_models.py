"""Own model settings. No outbound request on read/save/delete; explicit saved-version probe."""
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import BoundedSemaphore, Lock
import time
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, SecretStr, field_validator
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .ai_service import ModelFailure, ModelProfile, ModelService
from .config import get_settings
from .database import get_db
from .model_network import validate_base
from .model_secrets import get_secret_vault
from .models import UserModelProfile
from .schemas import InputModel
from .translation_runtime import run_connected

probe_slots = BoundedSemaphore(2)
probe_lock = Lock()
probe_attempts = defaultdict(deque)

def fail(status, code, message): raise HTTPException(status, detail={'code':code,'message':message})
def model_error(exc): fail(exc.status, exc.code, exc.message)

def enabled(): return get_settings().user_models_enabled and get_secret_vault().available

def require_enabled():
    if not enabled(): fail(503,'USER_MODEL_DISABLED','此环境未启用安全的用户模型配置，请使用独立用户模型预览')

def view(row):
    return {'provider':row.provider,'baseUrl':row.base_url,'model':row.model,'hasApiKey':bool(row.encrypted_key),
        'revision':row.revision,'verified':bool(row.encrypted_key and row.tested_revision == row.revision and row.encryption_scheme == get_secret_vault().scheme)} if row else None

class SaveProfile(InputModel):
    provider: Literal['openai_compatible'] = 'openai_compatible'
    baseUrl: str = Field(min_length=1, max_length=2048)
    model: str = Field(min_length=1, max_length=200)
    apiKey: SecretStr | None = Field(default=None, repr=False)
    clearKey: bool = False
    expectedRevision: str | None = Field(default=None, max_length=36)

    @field_validator('baseUrl')
    @classmethod
    def safe_url(cls, value):
        # ModelFailure is converted by the route; do not put original input in validation errors.
        return value.strip()

    @field_validator('model')
    @classmethod
    def model_name(cls, value):
        if not value.strip() or any(ord(c)<32 or ord(c)==127 for c in value): raise ValueError('Invalid model name')
        return value.strip()

    @field_validator('apiKey')
    @classmethod
    def key_length(cls, value):
        if value is not None:
            key=value.get_secret_value()
            if not 1<=len(key)<=4096 or any(ord(c)<33 or ord(c)>126 for c in key): raise ValueError('Invalid API key')
        return value

class ProfileVersion(InputModel):
    expectedRevision: str = Field(min_length=36,max_length=36)

class SnapshotResolver:
    def __init__(self, profile): self.profile=profile
    def resolve(self, principal_id, capability):
        if principal_id != self.profile.owner_user_id or capability != 'translation':
            raise ModelFailure('MODEL_PROFILE_FORBIDDEN','不能使用其他用户的模型配置',403)
        return self.profile


def snapshot(db, owner, revision=None, probe=False):
    require_enabled()
    row=db.get(UserModelProfile,owner)
    if not row or not row.encrypted_key: raise ModelFailure('MODEL_NOT_CONFIGURED','模型未配置：请先保存自己的模型与密钥')
    if revision and revision != row.revision: raise ModelFailure('MODEL_PROFILE_CHANGED','模型配置已改变，请重新加载后再试',409)
    if not probe and row.tested_revision != row.revision: raise ModelFailure('MODEL_NOT_CONFIGURED','模型未配置：请先在设置中测试当前配置')
    vault=get_secret_vault()
    if row.encryption_scheme != vault.scheme: raise ModelFailure('MODEL_VAULT_UNAVAILABLE','密钥存储方式不可用，请重新配置')
    profile=ModelProfile(provider=row.provider,base_url=validate_base(row.base_url),model=row.model,
        api_key=SecretStr(vault.decrypt(owner,row.encrypted_key)),scope='user',owner_user_id=owner,verified=True,
        max_output_tokens=32 if probe else 2048)
    return SnapshotResolver(profile),row.revision


def require_unchanged(db,owner,revision):
    # End any old read snapshot before checking a concurrent edit/deletion.
    db.rollback()
    row=db.get(UserModelProfile,owner)
    if not row or row.revision != revision:
        fail(409,'MODEL_PROFILE_CHANGED','模型配置在请求期间已改变，旧结果未采用，请重新翻译')


def create_user_model_router(current_session,require_csrf):
    router=APIRouter(prefix='/api/v1/user-model',tags=['user-model'])

    @router.get('/options')
    def options(session=Depends(current_session)):
        import os
        settings=get_settings()
        mock=settings.translation_mock_enabled
        developer=not settings.unified_acceptance and os.environ.get('LITERA_DISABLE_DEVELOPER_MODEL')!='1'
        return {'mockEnabled':mock,'userEnabled':enabled(),'developerEnabled':developer,
            'defaultSource':'mock' if mock else 'user' if enabled() else 'developer',
            'unifiedAcceptance':settings.unified_acceptance}

    @router.get('')
    def read(session=Depends(current_session),db:Session=Depends(get_db)):
        if not enabled(): return {'available':False,'profile':None}
        return {'available':True,'profile':view(db.get(UserModelProfile,session.user_id))}

    @router.put('')
    def save(payload:SaveProfile,session=Depends(require_csrf),db:Session=Depends(get_db)):
        require_enabled()
        owner=session.user_id
        try: base=validate_base(payload.baseUrl)
        except ModelFailure as exc: model_error(exc)
        if payload.clearKey and payload.apiKey: fail(422,'MODEL_CONFIG','请分别选择更换密钥或清除密钥')
        row=db.get(UserModelProfile,owner)
        if (row.revision if row else None)!=payload.expectedRevision:
            fail(409,'MODEL_PROFILE_CHANGED','模型配置已在另一页面改变，请重新加载后保存')
        vault=get_secret_vault()
        if row and row.encrypted_key and row.encryption_scheme != vault.scheme and not (payload.apiKey or payload.clearKey):
            fail(503,'MODEL_VAULT_UNAVAILABLE','密钥存储方式已改变，请重新填写或清除原密钥')
        try:
            encrypted=vault.encrypt(owner,payload.apiKey.get_secret_value()) if payload.apiKey else (None if payload.clearKey else row.encrypted_key if row else None)
        except ModelFailure as exc: model_error(exc)
        values=dict(revision=str(uuid.uuid4()),provider=payload.provider,base_url=base,model=payload.model,
            encrypted_key=encrypted,encryption_scheme=vault.scheme,tested_revision=None,updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
        try:
            if row:
                if db.execute(update(UserModelProfile).where(UserModelProfile.owner_id==owner,UserModelProfile.revision==payload.expectedRevision).values(**values)).rowcount!=1:
                    db.rollback();fail(409,'MODEL_PROFILE_CHANGED','模型配置已改变，请重新加载')
            else: db.add(UserModelProfile(owner_id=owner,**values))
            db.commit()
        except IntegrityError:
            db.rollback();fail(409,'MODEL_PROFILE_CHANGED','模型配置已改变，请重新加载')
        db.expire_all()
        return {'available':True,'profile':view(db.get(UserModelProfile,owner))}

    @router.delete('',status_code=204)
    def remove(payload:ProfileVersion,session=Depends(require_csrf),db:Session=Depends(get_db)):
        require_enabled()
        if db.execute(delete(UserModelProfile).where(UserModelProfile.owner_id==session.user_id,UserModelProfile.revision==payload.expectedRevision)).rowcount!=1:
            db.rollback();fail(409,'MODEL_PROFILE_CHANGED','模型配置已改变或不存在，请重新加载')
        db.commit()

    @router.post('/test')
    async def probe(payload:ProfileVersion,request:Request,session=Depends(require_csrf),db:Session=Depends(get_db)):
        owner=session.user_id
        try: resolver,revision=snapshot(db,owner,payload.expectedRevision,probe=True)
        except ModelFailure as exc: model_error(exc)
        db.rollback()
        with probe_lock:
            now=time.monotonic()
            for key in list(probe_attempts):
                while probe_attempts[key] and probe_attempts[key][0]<=now-60:probe_attempts[key].popleft()
                if not probe_attempts[key]:del probe_attempts[key]
            if len(probe_attempts[owner])>=3:fail(429,'MODEL_TEST_RATE_LIMIT','每分钟最多测试3次，请稍后重试')
            if not probe_slots.acquire(blocking=False):fail(429,'MODEL_TEST_BUSY','模型测试并发已满，请稍后重试')
            probe_attempts[owner].append(now)
        try:
            async with asyncio.timeout(15):
                await run_connected(request,ModelService().complete([{'role':'user','content':'Reply briefly with OK.'}],owner,resolver.profile))
            require_unchanged(db,owner,revision)
            if db.execute(update(UserModelProfile).where(UserModelProfile.owner_id==owner,UserModelProfile.revision==revision).values(tested_revision=revision)).rowcount!=1:
                db.rollback();fail(409,'MODEL_PROFILE_CHANGED','模型配置已改变，请重新测试')
            db.commit()
            return {'status':'ok','profile':view(db.get(UserModelProfile,owner))}
        except TimeoutError: fail(504,'MODEL_TIMEOUT','模型测试超时，请稍后重试')
        except ModelFailure as exc: model_error(exc)
        finally: probe_slots.release()

    return router
