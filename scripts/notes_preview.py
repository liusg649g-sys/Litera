"""Persistent P3-A preview using only its own SQLite, files, secret and temporary directory.
Never starts Docker or changes the 5177 launcher/data. No backend .env is read.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '.cache' / 'notes-preview'
FRONT_HOST, FRONT_PORT, API_PORT = '127.0.0.2', 5180, 8003
ORIGIN, API = f'http://{FRONT_HOST}:{FRONT_PORT}', f'http://127.0.0.1:{API_PORT}'
HEAD = '0007_literature_notes'
PID_FILE = DATA / 'processes.json'


def ensure_space():
    free = {drive: shutil.disk_usage(drive).free for drive in {'C:/', str(ROOT.anchor)}}
    if min(free.values()) < 10_000_000_000:
        raise RuntimeError('Preview stopped: available disk space below 10 GB')
    return free


def check():
    ensure_space()
    if PID_FILE.exists():
        raise RuntimeError('Preview process manifest exists; use status/stop, do not overwrite it')
    for host, port in [(FRONT_HOST, FRONT_PORT), ('127.0.0.1', API_PORT)]:
        with socket.socket() as sock:
            sock.bind((host, port))
    if DATA.is_symlink() or DATA.is_junction():
        raise RuntimeError('Preview data directory must not redirect to another environment')
    if DATA.exists():
        for path in DATA.rglob('*'):
            if path.is_symlink() or path.is_junction():
                raise RuntimeError('Preview paths must not redirect to other data')
    database = DATA / 'preview.db'
    if database.exists():
        import sqlite3
        with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Preview integrity check failed; data retained, not reset')
            if db.execute('select version_num from alembic_version').fetchall() != [(HEAD,)]:
                raise RuntimeError('Existing preview migration version differs; no automatic upgrade')
    print('Independent preview preflight passed; 5177 data will not be opened')


def api():
    check()
    DATA.mkdir(parents=True, exist_ok=True)
    secret = DATA / 'session-secret'
    if not secret.exists():
        with secret.open('x', encoding='utf-8') as stream:
            stream.write(secrets.token_hex(32))
    temporary = DATA / 'tmp'
    temporary.mkdir(exist_ok=True)
    os.environ.update(DATABASE_URL='sqlite:///' + (DATA / 'preview.db').as_posix(),
        PDF_STORAGE_ROOT=str(DATA / 'pdfs'), SESSION_SECRET=secret.read_text(encoding='utf-8').strip(),
        PUBLIC_ORIGIN=ORIGIN, APP_ENV='test', COOKIE_SECURE='false', AUTH_RATE_LIMIT='200',
        MAX_UPLOAD_BYTES='52428800', TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary),
        AI_PROVIDER='openai_compatible', AI_BASE_URL='', AI_MODEL='', AI_API_KEY='', AI_MODEL_VERIFIED='false')
    import tempfile
    assert Path(tempfile.gettempdir()).resolve() == temporary.resolve(), 'Preview temporary directory is not isolated'
    os.chdir(DATA)
    sys.path.insert(0, str(ROOT / 'backend'))
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from app.config import get_settings
    settings = get_settings()
    assert settings.database_url == 'sqlite:///' + (DATA / 'preview.db').as_posix()
    assert settings.pdf_storage_root.resolve() == (DATA / 'pdfs').resolve()
    cfg = Config(str(ROOT / 'backend' / 'alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'backend' / 'migrations'))
    if ScriptDirectory.from_config(cfg).get_current_head() != HEAD:
        raise RuntimeError('Migration head changed; preview requires renewed review')
    command.upgrade(cfg, HEAD)  # Only a fresh disposable preview DB, or a no-op at HEAD.
    sys.path.insert(0, str(ROOT / 'scripts'))
    from mock_translation_fixture import enable_test_translation
    enable_test_translation()  # Explicit isolated P3-B preview only; never loads developer model keys.
    from mock_answer_fixture import enable_mock_answers
    enable_mock_answers()
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=API_PORT, log_level='info')


def supervise():
    import psutil
    check()
    DATA.mkdir(parents=True, exist_ok=True)
    stop = DATA / 'stop.request'
    if stop.exists():
        raise RuntimeError('Existing stop marker found; inspect previous preview rather than silently reset')
    children, written = [], False
    stamp = time.strftime('%Y%m%d-%H%M%S')
    try:
        with (DATA / f'api-{stamp}.log').open('x', encoding='utf-8') as backend_log, (DATA / f'vite-{stamp}.log').open('x', encoding='utf-8') as vite_log:
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            children.append(subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'api'], stdout=backend_log, stderr=subprocess.STDOUT, creationflags=flags))
            # Start the frontend only after the isolated backend is healthy.
            for _ in range(50):
                if children[0].poll() is not None:
                    raise RuntimeError('Preview API exited; inspect its timestamped log, do not repeatedly restart')
                try:
                    with urllib.request.urlopen(API + '/api/v1/health', timeout=1) as response:
                        if response.status == 200: break
                except Exception: pass
                time.sleep(.3)
            else: raise RuntimeError('Preview API health timed out')
            env = dict(os.environ, LITERA_API_PROXY=API, VITE_LITERA_PREVIEW_MOCK='true')
            children.append(subprocess.Popen([shutil.which('node'), str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), '--host', FRONT_HOST, '--port', str(FRONT_PORT), '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=vite_log, stderr=subprocess.STDOUT, creationflags=flags))
            manifest = {'supervisor':os.getpid(), 'created':psutil.Process().create_time(), 'children':[p.pid for p in children], 'origin':ORIGIN, 'api':API, 'database':str(DATA/'preview.db')}
            with PID_FILE.open('x', encoding='utf-8') as stream:
                json.dump(manifest, stream)
            written = True
            while not stop.exists():
                free = ensure_space()
                (DATA / 'disk-status.json').write_text(json.dumps({'time':time.time(),'freeBytes':free}), encoding='utf-8')
                if any(p.poll() is not None for p in children):
                    raise RuntimeError('A preview child exited; data retained, no automatic restart')
                time.sleep(5)
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=10)
                except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=5)
        # Remove only this supervisor's own runtime markers, never business data.
        if written:
            PID_FILE.unlink(missing_ok=True)
            stop.unlink(missing_ok=True)


def stop():
    import psutil
    if not PID_FILE.exists():
        print('No managed notes preview found; no process stopped')
        return
    manifest = json.loads(PID_FILE.read_text(encoding='utf-8'))
    try:
        process = psutil.Process(manifest['supervisor'])
        valid = abs(process.create_time()-manifest['created']) < 1 and any(Path(arg).resolve() == Path(__file__).resolve() for arg in process.cmdline()[1:] if arg.endswith('.py'))
    except (psutil.Error, KeyError, ValueError): valid = False
    if not valid:
        raise RuntimeError('Preview PID is stale or mismatched; no stop request written')
    (DATA / 'stop.request').touch()
    print('Stop requested for notes preview only; all preview data retained')


def status():
    for url in [API+'/api/v1/health', ORIGIN+'/api/v1/health', ORIGIN]:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                print(url, response.status)
        except Exception: print(url, 'unavailable')
    print('Preview manifest present:', PID_FILE.exists())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['check','api','supervise','status','stop'])
    globals()[parser.parse_args().action]()
