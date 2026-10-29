import asyncio
from contextlib import asynccontextmanager
import hmac
import logging
import secrets
import time
import uuid
from threading import Lock
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from .config import get_settings
from .database import get_db
from .models import LoginSession, User
from .schemas import LoginInput, PasswordChangeInput, ProfileInput, RegisterInput, user_dto
from .security import csrf_token, dummy_hash, password_hasher, token_hash, verify_password
from .documents import UploadLimitMiddleware, create_document_router
from .annotations import create_annotation_router

from .reader_assets import create_asset_router, sweep_assets
from .pdf_exports import create_export_router, sweep_exports
from starlette.concurrency import run_in_threadpool

@asynccontextmanager
async def lifespan(app):
    # 启动时清理 orphan extraction jobs（进程重启导致 processing 状态丢失）
    try:
        from .database import SessionLocal
        from .extraction import run_startup_scan
        _db = SessionLocal()
        run_startup_scan(_db)
        _db.close()
    except Exception as exc:
        logging.warning("Startup orphan extraction scan failed: %s", exc)

    async def collect():
        while True:
            await run_in_threadpool(sweep_assets)
            await run_in_threadpool(sweep_exports)
            await asyncio.sleep(60)
    collector = asyncio.create_task(collect())
    try:
        yield
    finally:
        collector.cancel()
        try:
            await collector
        except asyncio.CancelledError:
            pass

settings = get_settings()
app = FastAPI(title="Litera API", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(UploadLimitMiddleware)
COOKIE_NAME = "litera_session"
auth_attempts = defaultdict(deque)
auth_attempts_lock = Lock()

def fail(status, code, message):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})

@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    try:
        response = await call_next(request)
    except Exception:
        logging.exception("Request failed: %s", request.state.request_id)
        response = JSONResponse(status_code=500, content={
            "error": {"code": "INTERNAL_ERROR", "message": "服务暂时不可用，请稍后重试"},
            "requestId": request.state.request_id})
    response.headers["X-Request-ID"] = request.state.request_id
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc):
    if getattr(request.state, "upload_too_large", False):
        return JSONResponse(status_code=413, content={"error": {
            "code": "UPLOAD_TOO_LARGE", "message": "上传请求超过大小限制",
            "details": {"maxUploadBytes": getattr(request.state, "upload_limit", settings.max_upload_bytes)}}, "requestId": request.state.request_id})
    error = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code,
                        content={"error": error, "requestId": request.state.request_id}, headers=exc.headers)

@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc):
    fields = [{"field": ".".join(str(part) for part in issue["loc"][1:]),
               "type": issue["type"]} for issue in exc.errors()]
    return JSONResponse(status_code=422, content={
        "error": {"code": "VALIDATION_ERROR", "message": "请检查输入内容", "details": {"fields": fields}},
        "requestId": request.state.request_id})

def require_origin(request: Request):
    if request.headers.get("origin") != settings.public_origin:
        fail(403, "INVALID_ORIGIN", "请求来源无效，请从 Litera 页面操作")

def rate_limit(request: Request):
    key = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    with auth_attempts_lock:
        now = time.monotonic()
        for address in list(auth_attempts):
            entries = auth_attempts[address]
            while entries and entries[0] <= now - settings.auth_rate_window_seconds:
                entries.popleft()
            if not entries:
                del auth_attempts[address]
        entries = auth_attempts[key]
        if len(entries) >= settings.auth_rate_limit:
            fail(429, "AUTH_RATE_LIMITED", "操作过于频繁，请稍后再试")
        entries.append(now)

def current_session(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if not token or len(token) > 128:
        fail(401, "UNAUTHENTICATED", "请先登录")
    session = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_hash(token)))
    if not session or session.revoked_at or session.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
        fail(401, "UNAUTHENTICATED", "登录已失效，请重新登录")
    return session

def require_csrf(request: Request, session: LoginSession = Depends(current_session)):
    require_origin(request)
    supplied = request.headers.get("x-csrf-token", "")
    if not hmac.compare_digest(supplied.encode(), csrf_token(session).encode()):
        fail(403, "INVALID_CSRF_TOKEN", "请求校验失败，请刷新页面后重试")
    return session

@app.get("/api/v1/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}

@app.post("/api/v1/auth/register", status_code=201, dependencies=[Depends(require_origin), Depends(rate_limit)])
def register(payload: RegisterInput, db: Session = Depends(get_db)):
    password = payload.password.get_secret_value()
    if not settings.password_min_length <= len(password) <= 128:
        fail(422, "INVALID_PASSWORD", f"密码长度应为 {settings.password_min_length}–128 个字符")
    normalized = str(payload.email).lower()
    if db.scalar(select(User).where(User.email == normalized)):
        fail(409, "EMAIL_EXISTS", "该邮箱已注册，请直接登录")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user = User(id=str(uuid.uuid4()), email=normalized, display_name=payload.display_name,
                password_hash=password_hasher.hash(password), created_at=now, updated_at=now)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "EMAIL_EXISTS", "该邮箱已注册，请直接登录")
    return user_dto(user)

@app.post("/api/v1/auth/login", dependencies=[Depends(require_origin), Depends(rate_limit)])
def login(payload: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    password = payload.password.get_secret_value()
    if len(password) > 128:
        fail(401, "INVALID_CREDENTIALS", "邮箱或密码不正确")
    # Serialize login with password changes: an old password must not mint a
    # session after a concurrent change has revoked the account's sessions.
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()).with_for_update())
    valid = verify_password(user.password_hash if user else dummy_hash, password)
    if not user or not valid:
        fail(401, "INVALID_CREDENTIALS", "邮箱或密码不正确")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    old_token = request.cookies.get(COOKIE_NAME)
    if old_token:
        old = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_hash(old_token)))
        if old and not old.revoked_at:
            old.revoked_at = now
    token = secrets.token_urlsafe(32)
    session = LoginSession(id=str(uuid.uuid4()), user_id=user.id, token_hash=token_hash(token),
                           created_at=now, expires_at=now + timedelta(seconds=settings.session_ttl_seconds))
    db.add(session)
    db.commit()
    response.set_cookie(COOKIE_NAME, token, max_age=settings.session_ttl_seconds,
                        httponly=True, secure=settings.cookie_secure, samesite="lax", path="/")
    return {"user": user_dto(user), "csrfToken": csrf_token(session)}

@app.get("/api/v1/auth/session")
def session_info(session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
    return {"user": user_dto(db.get(User, session.user_id)), "csrfToken": csrf_token(session)}

@app.post("/api/v1/auth/password", status_code=204, dependencies=[Depends(rate_limit)])
def change_password(payload: PasswordChangeInput, response: Response,
                    session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
    # Current reads under MySQL REPEATABLE READ; authentication earlier in the
    # request does not authorize reusing a session revoked while waiting here.
    user = db.scalar(select(User).where(User.id == session.user_id).with_for_update()
                     .execution_options(populate_existing=True))
    active = db.scalar(select(LoginSession).where(LoginSession.id == session.id).with_for_update()
                       .execution_options(populate_existing=True))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if not user or not active or active.revoked_at or active.expires_at <= now:
        fail(401, "UNAUTHENTICATED", "登录已失效，请重新登录")
    old_password = payload.current_password.get_secret_value()
    new_password = payload.new_password.get_secret_value()
    if not settings.password_min_length <= len(new_password) <= 128:
        fail(422, "INVALID_PASSWORD", f"密码长度应为 {settings.password_min_length}–128 个字符")
    if not verify_password(user.password_hash, old_password):
        fail(400, "INVALID_CURRENT_PASSWORD", "当前密码不正确")
    if new_password == old_password:
        fail(400, "PASSWORD_UNCHANGED", "新密码不能与当前密码相同")
    user.password_hash = password_hasher.hash(new_password)
    user.updated_at = now
    db.execute(update(LoginSession).where(LoginSession.user_id == user.id, LoginSession.revoked_at.is_(None))
               .values(revoked_at=now))
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True,
                           secure=settings.cookie_secure, samesite="lax")

@app.post("/api/v1/auth/logout", status_code=204)
def logout(response: Response, session: LoginSession = Depends(require_csrf), db: Session = Depends(get_db)):
    session.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True,
                           secure=settings.cookie_secure, samesite="lax")

@app.get("/api/v1/users/me")
def me(session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
    return user_dto(db.get(User, session.user_id))

@app.patch("/api/v1/users/me")
def update_me(payload: ProfileInput, session: LoginSession = Depends(require_csrf),
              db: Session = Depends(get_db)):
    user = db.get(User, session.user_id)
    user.display_name = payload.display_name
    user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return user_dto(user)

app.include_router(create_document_router(current_session, require_csrf))
app.include_router(create_annotation_router(current_session, require_csrf))

app.include_router(create_asset_router(current_session, require_csrf))
app.include_router(create_export_router(current_session, require_csrf))

from .translations import create_translation_router
app.include_router(create_translation_router(require_csrf))

from .notes import create_note_router
app.include_router(create_note_router(current_session, require_csrf))

from .user_models import create_user_model_router
app.include_router(create_user_model_router(current_session, require_csrf))

from .extraction import create_extraction_router
app.include_router(create_extraction_router(current_session, require_csrf))
