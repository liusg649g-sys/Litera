import os
import tempfile
from pathlib import Path
import pytest

test_url = os.environ.get("TEST_DATABASE_URL")
if test_url:
    from sqlalchemy.engine import make_url
    if make_url(test_url).database != "litera_test":
        raise RuntimeError("TEST_DATABASE_URL must target litera_test; refusing to reset user data")
else:
    temp_dir = tempfile.TemporaryDirectory(prefix="litera-auth-tests-")
    test_url = "sqlite:///" + str(Path(temp_dir.name) / "test.db")
os.environ["DATABASE_URL"] = test_url
os.environ["SESSION_SECRET"] = "isolated-test-session-secret-at-least-32-characters"
os.environ["APP_ENV"] = "test"
os.environ["PUBLIC_ORIGIN"] = "http://localhost:8080"

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete
from app.database import engine, SessionLocal
from app.main import app, auth_attempts
from app.models import LoginSession, User

@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    yield
    engine.dispose()
    if not os.environ.get('TEST_DATABASE_URL'):
        temp_dir.cleanup()

@pytest.fixture(autouse=True)
def clean_database(migrated_database):
    with SessionLocal() as db:
        db.execute(delete(LoginSession))
        db.execute(delete(User))
        db.commit()
    auth_attempts.clear()

@pytest.fixture
def client():
    with TestClient(app, headers={"Origin": "http://localhost:8080"}) as client:
        yield client
