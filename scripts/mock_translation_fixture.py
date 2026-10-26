"""Explicit fixture for the isolated P3 preview/browser tests; never a model adapter."""
import os
from pathlib import Path

def enable_test_translation():
    from sqlalchemy.engine import make_url
    from app.config import get_settings
    settings = get_settings()
    url = make_url(settings.database_url)
    if settings.app_env != 'test' or url.get_backend_name() != 'sqlite' or not url.database or url.database == ':memory:':
        raise RuntimeError('Mock requires an explicitly isolated file-backed SQLite test environment')
    database = Path(url.database).resolve()
    preview = Path(__file__).resolve().parents[1] / '.cache' / 'notes-preview'
    permitted = database.parent == preview.resolve() or database.parent.name.startswith('litera-note-captures-')
    if not permitted or settings.pdf_storage_root.resolve() != database.parent / 'pdfs':
        raise RuntimeError('Mock must not open the real local-site or a shared document directory')
    if any(os.environ.get(name) for name in ('AI_API_KEY','AI_BASE_URL','AI_MODEL')):
        raise RuntimeError('Mock fixture requires empty external-model configuration')
    import app.translations as translations
    async def isolated_translate(text, source, target, *_args, **_kwargs):
        direction = '英译中' if (source, target) == ('en', 'zh') else '中译英'
        return f'【隔离 Mock，非真实模型译文；{direction}】\n{text}'
    translations.translate_text = isolated_translate
    os.environ['LITERA_ISOLATED_TRANSLATION_MOCK'] = '1'
    print('Explicit isolated Mock translation enabled; no real model service is used.', flush=True)
