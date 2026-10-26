"""P3-B disposable browser fixture: temporary SQLite/PDFs and explicitly labelled Mock.
Never loads developer model credentials or opens either persistent Litera environment.
"""
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'http://127.0.0.1:5182'
with tempfile.TemporaryDirectory(prefix='litera-note-captures-') as temporary:
    data = Path(temporary).resolve()
    scratch = data / 'tmp'
    scratch.mkdir()
    os.environ.update(
        DATABASE_URL='sqlite:///' + (data / 'browser.db').as_posix(),
        PDF_STORAGE_ROOT=str(data / 'pdfs'),
        SESSION_SECRET='litera-note-captures-test-only-session-secret-32',
        PUBLIC_ORIGIN=ORIGIN, APP_ENV='test', COOKIE_SECURE='false',
        MAX_UPLOAD_BYTES='52428800', AUTH_RATE_LIMIT='200',
        AI_PROVIDER='openai_compatible', AI_BASE_URL='', AI_MODEL='',
        AI_API_KEY='', AI_MODEL_VERIFIED='false',
        TEMP=str(scratch), TMP=str(scratch), TMPDIR=str(scratch),
    )
    tempfile.tempdir = str(scratch)
    os.chdir(data)
    sys.path.insert(0, str(ROOT / 'backend'))
    sys.path.insert(0, str(ROOT / 'scripts'))
    from alembic import command
    from alembic.config import Config
    from app.config import get_settings
    from app.database import engine
    from mock_translation_fixture import enable_test_translation
    import uvicorn

    settings = get_settings()
    assert settings.app_env == 'test'
    assert settings.database_url == 'sqlite:///' + (data / 'browser.db').as_posix()
    assert settings.pdf_storage_root.resolve() == (data / 'pdfs').resolve()
    config = Config(str(ROOT / 'backend/alembic.ini'))
    config.set_main_option('script_location', str(ROOT / 'backend/migrations'))
    command.upgrade(config, 'head')
    enable_test_translation()
    from mock_answer_fixture import enable_mock_answers
    enable_mock_answers()
    manifest = ROOT / 'frontend/test-results/note-captures-storage.json'
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({'database': str(data / 'browser.db'), 'pdfRoot': str(data / 'pdfs'), 'origin': ORIGIN, 'model': 'isolated_mock'}), encoding='utf-8')
    print('P3-B test fixture: independent temporary SQLite, isolated_mock only; no real model service', flush=True)
    try:
        uvicorn.run('app.main:app', host='127.0.0.1', port=8005, log_level='warning')
    finally:
        engine.dispose()
        manifest.unlink(missing_ok=True)
