"""Disposable real API for P2-A Playwright; never reads the development .env."""
import os
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="litera-browser-") as temporary:
    os.environ.update(
        DATABASE_URL="sqlite:///" + str(Path(temporary) / "e2e.db"),
        PDF_STORAGE_ROOT=str(Path(temporary) / "pdfs"),
        SESSION_SECRET="litera-local-browser-isolated-session-secret-32",
        PUBLIC_ORIGIN="http://127.0.0.1:5175", APP_ENV="test", COOKIE_SECURE="false",
        MAX_UPLOAD_BYTES="52428800", AUTH_RATE_LIMIT="200",
    )
    os.chdir(root / "backend")
    import sys
    sys.path.insert(0, str(root / "backend"))
    from alembic import command
    from alembic.config import Config
    import uvicorn
    from app.database import engine
    command.upgrade(Config("alembic.ini"), "head")
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=8001, log_level="warning")
    finally:
        engine.dispose()
