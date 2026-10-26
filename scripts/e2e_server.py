"""Disposable real API for P2-A Playwright; never reads the development .env."""
import os
import json
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="litera-browser-") as temporary:
    scratch = Path(temporary) / "tmp"
    scratch.mkdir()
    os.environ.update(
        DATABASE_URL="sqlite:///" + str(Path(temporary) / "e2e.db"),
        PDF_STORAGE_ROOT=str(Path(temporary) / "pdfs"),
        SESSION_SECRET="litera-local-browser-isolated-session-secret-32",
        PUBLIC_ORIGIN="http://127.0.0.1:5175", APP_ENV="test", COOKIE_SECURE="false",
        MAX_UPLOAD_BYTES="52428800", AUTH_RATE_LIMIT="200",
        TEMP=str(scratch), TMP=str(scratch), TMPDIR=str(scratch),
        AI_PROVIDER="openai_compatible", AI_BASE_URL="", AI_MODEL="",
        AI_API_KEY="", AI_MODEL_VERIFIED="false",
    )
    manifest = root / "frontend" / "test-results" / "e2e-storage.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"database": str(Path(temporary) / "e2e.db"), "pdfRoot": str(Path(temporary) / "pdfs")}), encoding="utf-8")
    tempfile.tempdir = str(scratch)
    os.chdir(temporary)  # Never discover backend/.env; exports also stay disposable.
    import sys
    sys.path.insert(0, str(root / "backend"))
    from alembic import command
    from alembic.config import Config
    import uvicorn
    from app.database import engine
    config = Config(str(root / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(root / "backend" / "migrations"))
    command.upgrade(config, "head")
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=8001, log_level="warning")
    finally:
        engine.dispose()
        manifest.unlink(missing_ok=True)
