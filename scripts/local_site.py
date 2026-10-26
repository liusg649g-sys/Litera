"""Persistent, Docker-free manual development site; no project .env is read."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '.cache' / 'local-site'
ORIGIN = 'http://127.0.0.1:5177'
API = 'http://127.0.0.1:8002'

def api():
    # Same SQLite/Alembic/Uvicorn approach as e2e_server.py, with retained data.
    DATA.mkdir(parents=True, exist_ok=True)
    secret = DATA / 'session-secret'
    if not secret.exists():
        with secret.open('x', encoding='utf-8') as f:
            f.write(secrets.token_hex(32))
    os.environ.update(DATABASE_URL='sqlite:///' + (DATA / 'local.db').as_posix(),
        PDF_STORAGE_ROOT=str(DATA / 'pdfs'), SESSION_SECRET=secret.read_text().strip(),
        PUBLIC_ORIGIN=ORIGIN, APP_ENV='development', COOKIE_SECURE='false',
        MAX_UPLOAD_BYTES='52428800', AUTH_RATE_LIMIT='200')
    os.chdir(DATA)  # Settings must not discover backend/.env or repository .env.
    sys.path.insert(0, str(ROOT / 'backend'))
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(ROOT / 'backend' / 'alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'backend' / 'migrations'))
    from app.config import get_settings
    settings = get_settings()
    assert settings.database_url == 'sqlite:///' + (DATA / 'local.db').as_posix()
    assert settings.pdf_storage_root.resolve() == (DATA / 'pdfs').resolve()
    command.upgrade(cfg, 'head')
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=8002, log_level='info')

def supervise():
    import socket
    DATA.mkdir(parents=True, exist_ok=True)
    for port in (8002, 5177):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))
    stop = DATA / 'stop.request'
    stop.unlink(missing_ok=True)
    children = []
    try:
        with (DATA / 'api.log').open('w', encoding='utf-8') as backend_log, (DATA / 'vite.log').open('w', encoding='utf-8') as vite_log:
            children.append(subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'api'], stdout=backend_log, stderr=subprocess.STDOUT))
            env = dict(os.environ, LITERA_API_PROXY=API)
            children.append(subprocess.Popen([shutil.which('node'), str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5177', '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=vite_log, stderr=subprocess.STDOUT))
            (DATA / 'processes.json').write_text(json.dumps({'supervisor': os.getpid(), 'children': [p.pid for p in children], 'origin': ORIGIN}), encoding='utf-8')
            while not stop.exists():
                free = {drive: shutil.disk_usage(drive).free for drive in ('C:/', str(ROOT.anchor))}
                (DATA / 'disk-status.json').write_text(json.dumps({'time': time.time(), 'freeBytes': free}), encoding='utf-8')
                if min(free.values()) < 10_000_000_000:
                    print('Stopped: disk space below 10 GB', flush=True)
                    break
                if any(p.poll() is not None for p in children):
                    print('Stopped: a site process exited; inspect api.log and vite.log', flush=True)
                    break
                time.sleep(5)
    finally:
        for p in reversed(children):
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    p.kill()
        (DATA / 'processes.json').unlink(missing_ok=True)
        stop.unlink(missing_ok=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['api', 'supervise', 'stop'])
    action = parser.parse_args().action
    if action == 'api': api()
    elif action == 'supervise': supervise()
    else:
        if (DATA / 'processes.json').exists():
            (DATA / 'stop.request').touch()
            print('Stop requested; data retained.')
        else:
            print('No managed local site is running.')
