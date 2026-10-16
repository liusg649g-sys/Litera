from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy import inspect, select
from app.config import Settings
from app.database import engine, SessionLocal
from app.main import COOKIE_NAME, settings
from app.models import LoginSession, User

PASSWORD = "test-password-123"
def register(client, email="reader@example.com", name="Reader"):
    return client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "displayName": name})

def login(client, email="reader@example.com"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})

def test_migration_creates_only_auth_and_p2a_tables(client):
    assert set(inspect(engine).get_table_names()) == {"users", "sessions", "documents", "document_files", "alembic_version", "folders", "tags", "document_tags", "reading_progress", "cleanup_jobs", "annotations", "document_reader_state", "annotation_command_receipts"}
    assert client.get("/api/v1/health").json() == {"status": "ok"}

def test_register_hashes_password_and_does_not_auto_login(client):
    response = register(client)
    assert response.status_code == 201
    assert set(response.json()) == {"id", "email", "displayName", "createdAt"}
    assert client.get("/api/v1/users/me").status_code == 401
    with SessionLocal() as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$argon2id$")
        assert user.password_hash != PASSWORD

def test_duplicate_email_normalized(client):
    assert register(client, "Reader@EXAMPLE.com").status_code == 201
    duplicate = register(client, "reader@example.com")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EMAIL_EXISTS"
    with SessionLocal() as db:
        assert len(db.scalars(select(User)).all()) == 1

@pytest.mark.parametrize("changes", [
    {"email": "invalid"}, {"password": "short"}, {"password": "a" * 129},
    {"displayName": "   "}, {"role": "admin"}, {"ownerId": "another-user"},
])
def test_invalid_registration_does_not_create_user_or_echo_password(client, changes):
    body = {"email": "reader@example.com", "password": PASSWORD, "displayName": "Reader", **changes}
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 422
    assert "requestId" in response.json()
    assert PASSWORD not in response.text
    with SessionLocal() as db:
        assert db.scalar(select(User)) is None

def test_login_session_cookie_and_real_logout(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    token = client.cookies.get(COOKIE_NAME)
    csrf = response.json()["csrfToken"]
    assert client.get("/api/v1/auth/session").json()["csrfToken"] == csrf
    assert client.get("/api/v1/users/me").json()["displayName"] == "Reader"
    with SessionLocal() as db:
        assert db.scalar(select(LoginSession)).token_hash != token
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    client.cookies.set(COOKIE_NAME, token)
    assert client.get("/api/v1/auth/session").status_code == 401

def test_invalid_credentials_are_indistinguishable(client):
    register(client)
    bad_password = client.post("/api/v1/auth/login", json={"email": "reader@example.com", "password": "wrong"})
    absent = login(client, "missing@example.com")
    assert bad_password.status_code == absent.status_code == 401
    assert bad_password.json()["error"] == absent.json()["error"]

def test_session_expiration(client):
    register(client); login(client)
    with SessionLocal() as db:
        session = db.scalar(select(LoginSession))
        session.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/users/me").status_code == 401

@pytest.mark.parametrize("path", ["/api/v1/auth/register", "/api/v1/auth/login"])
def test_login_register_origin_check(client, path):
    payload = {"email": "reader@example.com", "password": PASSWORD, "displayName": "Reader"}
    if path.endswith("login"):
        payload.pop("displayName")
    response = client.post(path, json=payload, headers={"Origin": "https://attacker.example"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INVALID_ORIGIN"

def test_missing_origin_rejected(client):
    client.headers.pop("origin")
    assert register(client).status_code == 403

def test_authenticated_writes_need_csrf_and_origin(client):
    register(client); result = login(client)
    for supplied in (None, "invalid"):
        headers = {"X-CSRF-Token": supplied} if supplied else {}
        assert client.patch("/api/v1/users/me", json={"displayName": "Changed"}, headers=headers).status_code == 403
    csrf = result.json()["csrfToken"]
    assert client.patch("/api/v1/users/me", json={"displayName": "Changed"},
        headers={"X-CSRF-Token": csrf, "Origin": "https://attacker.example"}).status_code == 403
    assert client.get("/api/v1/users/me").json()["displayName"] == "Reader"

def test_profile_update_and_user_isolation(client):
    first = register(client).json()
    second = register(client, "other@example.com", "Other").json()
    result = login(client)
    headers = {"X-CSRF-Token": result.json()["csrfToken"]}
    assert client.patch("/api/v1/users/me", json={"displayName": "Jensen"}, headers=headers).status_code == 200
    assert client.get("/api/v1/users/me").json()["displayName"] == "Jensen"
    assert client.patch("/api/v1/users/me", json={"displayName": "Hijack", "id": second["id"]},
                        headers=headers).status_code == 422
    with SessionLocal() as db:
        assert db.get(User, first["id"]).display_name == "Jensen"
        assert db.get(User, second["id"]).display_name == "Other"

def test_new_login_rotates_session(client):
    register(client); login(client)
    old_token = client.cookies.get(COOKIE_NAME)
    login(client)
    assert client.cookies.get(COOKIE_NAME) != old_token
    client.cookies.set(COOKIE_NAME, old_token)
    assert client.get("/api/v1/auth/session").status_code == 401

def test_auth_rate_limit(client):
    previous = settings.auth_rate_limit
    settings.auth_rate_limit = 2
    try:
        register(client)
        login(client, "missing@example.com")
        assert login(client, "missing@example.com").status_code == 429
    finally:
        settings.auth_rate_limit = previous

def test_configuration_fails_without_required_values(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)

def test_production_requires_https_and_secure_cookie():
    with pytest.raises(ValidationError):
        Settings(app_env="production", database_url="sqlite://", session_secret="x" * 32,
                 public_origin="http://localhost:8080", cookie_secure=False, _env_file=None)

def test_api_has_no_cache_or_secret_error_payloads(client):
    response = client.get("/api/v1/users/me")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"] == response.json()["requestId"]
