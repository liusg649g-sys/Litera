"""Unified translation/notes acceptance site. Explicit Mock or personal model; no developer .env.
Prepare is additive, backed up and verified. API start never migrates existing data.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'.cache/user-model-preview/unified'
SOURCE=ROOT/'.cache/notes-preview'
FRONT_HOST,FRONT_PORT='127.0.0.3',5183
API_PORT=FRONT_PORT
ORIGIN=API=f'http://{FRONT_HOST}:{FRONT_PORT}'
HTTP=urllib.request.build_opener(urllib.request.ProxyHandler({}))
HEAD='0010_qa_answers_indexes_vectors'
PID_FILE=DATA/'processes.json'


def ensure_space():
    free={d:shutil.disk_usage(d).free for d in {'C:/',str(ROOT.anchor)}}
    if min(free.values())<10_000_000_000:raise RuntimeError('Preview stopped: available disk space below 10 GB')
    return free


def check_paths():
    ensure_space()
    for base in (ROOT/'.cache',DATA.parent,DATA):
        if base.is_symlink() or base.is_junction():raise RuntimeError('Preview paths may not redirect to another environment')
    if DATA.exists():
        for p in DATA.rglob('*'):
            if p.is_symlink() or p.is_junction():raise RuntimeError('Preview paths may not redirect')


def db_check(expected=HEAD):
    with sqlite3.connect((DATA/'preview.db').as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('pragma integrity_check').fetchone()[0]!='ok' or db.execute('pragma foreign_key_check').fetchall():raise RuntimeError('Preview database integrity failed; do not reset')
        if db.execute('select version_num from alembic_version').fetchall()!=[(expected,)]:raise RuntimeError('Preview version differs; explicit migration review required')


def check():
    check_paths()
    if PID_FILE.exists():raise RuntimeError('Manifest exists; inspect status/stop rather than overwrite')
    if (DATA/'stop.request').exists():raise RuntimeError('Existing stop marker; review rather than reset')
    for host,port in [(FRONT_HOST,FRONT_PORT)]:
        with socket.socket() as s:s.bind((host,port))
    if (DATA/'preview.db').exists():
        db_check()
        try: record=json.loads((DATA/'import-verification.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):raise RuntimeError('Import verification missing; do not start a partial copy') from None
        if record.get('backupAndRestoreVerified') is not True or record.get('migration')!=HEAD:raise RuntimeError('Import verification failed; retain data for review')
    print('User-model preview preflight passed; 5177 and 5180 will not be opened',flush=True)


def configure():
    check_paths()
    temporary=DATA/'tmp';temporary.mkdir(exist_ok=True)
    for key in list(os.environ):
        if key.startswith(('AI_','TRANSLATION_')):os.environ.pop(key)
    os.environ.update(DATABASE_URL='sqlite:///'+(DATA/'preview.db').as_posix(),PDF_STORAGE_ROOT=str(DATA/'pdfs'),
        SESSION_SECRET=(DATA/'session-secret').read_text(encoding='utf-8').strip(),PUBLIC_ORIGIN=ORIGIN,APP_ENV='development',
        USER_MODELS_ENABLED='true',TRANSLATION_MOCK_ENABLED='true',UNIFIED_ACCEPTANCE='true',LITERA_DISABLE_DEVELOPER_MODEL='1',COOKIE_SECURE='false',AUTH_RATE_LIMIT='100',
        TEMP=str(temporary),TMP=str(temporary),TMPDIR=str(temporary))
    # Clear preview-only fixtures as well. This site must never turn real results into Mock.
    for key in list(os.environ):
        if key.startswith(('LITERA_ISOLATED_', 'LITERA_MOCK_')):os.environ.pop(key)
    import tempfile
    tempfile.tempdir=str(temporary)
    os.chdir(DATA)
    sys.path.insert(0,str(ROOT/'backend'))


def migration_config():
    from alembic.config import Config
    cfg=Config(str(ROOT/'backend/alembic.ini'))
    cfg.set_main_option('script_location',str(ROOT/'backend/migrations'))
    return cfg


def file_manifest(base):
    return {str(p.relative_to(base)):{'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in base.rglob('*') if p.is_file()}


def data_snapshot(path):
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('pragma integrity_check').fetchone()[0]!='ok' or db.execute('pragma foreign_key_check').fetchall():raise RuntimeError('Database integrity failed; no reset')
        tables=[row[0] for row in db.execute("select name from sqlite_master where type='table' and name!='alembic_version'")]
        return {name:hashlib.sha256(repr(db.execute('select * from "'+name+'" order by rowid').fetchall()).encode()).hexdigest() for name in tables}


def frontend_digest():
    files=sorted(p for p in (ROOT/'frontend/src').rglob('*') if p.is_file())
    return hashlib.sha256(''.join(str(p.relative_to(ROOT))+'='+hashlib.sha256(p.read_bytes()).hexdigest() for p in files).encode()).hexdigest()


def built():
    try:
        stamp=json.loads((ROOT/'frontend/dist/unified-build.json').read_text(encoding='utf-8'))
        return stamp['sourceDigest']==frontend_digest() and stamp['unified'] is True and stamp['indexSha256']==hashlib.sha256((ROOT/'frontend/dist/index.html').read_bytes()).hexdigest()
    except (OSError,ValueError,KeyError):return False


def build():
    ensure_space()
    if built():print('Reusing verified unified frontend build');return
    env={k:v for k,v in os.environ.items() if not k.startswith(('AI_','TRANSLATION_'))}
    env.update(VITE_LITERA_UNIFIED_ACCEPTANCE='true',VITE_LITERA_PREVIEW_MOCK='false',VITE_LITERA_USER_MODEL_PREVIEW='false',NODE_OPTIONS='--max-old-space-size=1024')
    digest=frontend_digest()
    commands=[['node_modules/vue-tsc/bin/vue-tsc.js','--noEmit'],['node_modules/vite/bin/vite.js','build']]
    for args in commands:
        proc=subprocess.Popen([shutil.which('node'),*args],cwd=ROOT/'frontend',env=env)
        try:
            while proc.poll() is None:
                ensure_space();time.sleep(.5)
        except BaseException:
            proc.terminate();proc.wait(timeout=10);raise
        if proc.returncode:raise RuntimeError('Unified build failed; no service started')
    if digest!=frontend_digest():raise RuntimeError('Frontend changed during build; review before starting')
    (ROOT/'frontend/dist/unified-build.json').write_text(json.dumps({'unified':True,'sourceDigest':digest,'indexSha256':hashlib.sha256((ROOT/'frontend/dist/index.html').read_bytes()).hexdigest()}),encoding='utf-8')


def prepare():
    check_paths()
    if (DATA/'preview.db').exists():check();return
    if DATA.exists() and any(DATA.iterdir()):raise RuntimeError('Nonempty target without database; no overwrite')
    check()
    # The source is kept offline, read-only and at its original migration.
    for host,port in [('127.0.0.2',5180),('127.0.0.1',8003)]:
        with socket.socket() as sock:sock.bind((host,port))
    for base in [SOURCE,*SOURCE.rglob('*')]:
        if base.is_symlink() or base.is_junction():raise RuntimeError('Source redirection requires review')
    if not (SOURCE/'preview.db').is_file() or not (SOURCE/'session-secret').is_file():raise RuntimeError('Original preview data missing; no automatic initialization')
    if any((SOURCE/name).exists() and (SOURCE/name).stat().st_size for name in ['preview.db-wal','preview.db-journal']):raise RuntimeError('Source journal present; pause for a coordinated backup')
    original=data_snapshot(SOURCE/'preview.db')
    with sqlite3.connect((SOURCE/'preview.db').as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('select version_num from alembic_version').fetchall()!=[('0007_literature_notes',)]:raise RuntimeError('Unexpected source version')
    stamp=time.strftime('%Y%m%d-%H%M%S');backup=ROOT.parent/'Litera-backups'/('unified-source-'+stamp)
    before=file_manifest(SOURCE)
    shutil.copytree(SOURCE,backup)
    if file_manifest(backup)!=before or file_manifest(SOURCE)!=before or data_snapshot(backup/'preview.db')!=original:raise RuntimeError('Joint backup changed or differs; no migration')
    DATA.mkdir(parents=True,exist_ok=True)
    shutil.copy2(backup/'preview.db',DATA/'preview.db')
    shutil.copy2(backup/'session-secret',DATA/'session-secret')
    shutil.copytree(backup/'pdfs',DATA/'pdfs')
    # Restore verification is the actual independent target, not an overwrite.
    if data_snapshot(DATA/'preview.db')!=original or file_manifest(DATA/'pdfs')!=file_manifest(backup/'pdfs'):raise RuntimeError('Restore verification failed')
    configure()
    from alembic import command
    from alembic.script import ScriptDirectory
    cfg=migration_config()
    if ScriptDirectory.from_config(cfg).get_current_head()!=HEAD:raise RuntimeError('New migration requires review')
    command.upgrade(cfg,HEAD)
    after=data_snapshot(DATA/'preview.db')
    if any(after.get(name)!=value for name,value in original.items()):raise RuntimeError('Original rows changed after additive migration; retain backup, no startup')
    db_check()
    if data_snapshot(SOURCE/'preview.db')!=original or file_manifest(SOURCE)!=before:raise RuntimeError('Source changed during import; pause')
    record={'source':str(SOURCE),'backup':str(backup),'files':before,'fileCount':len(before),'bytes':sum(v['size'] for v in before.values()),'sourceTables':original,'backupAndRestoreVerified':True,'migration':HEAD}
    (DATA/'import-verification.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('Original preview jointly backed up and restored into independent unified copy; source unchanged',flush=True)


def api():
    check();db_check();configure()
    from app.model_secrets import get_secret_vault
    vault=get_secret_vault()
    if not vault.available or vault.decrypt('startup-canary',vault.encrypt('startup-canary','synthetic-canary'))!='synthetic-canary':raise RuntimeError('Secure vault unavailable')
    # Existing normal collector only sees this new DB and the dedicated tmp directory.
    with sqlite3.connect((DATA/'preview.db').as_uri()+'?mode=ro',uri=True) as db:
        if db.execute("select count(*) from reader_assets where status!='deleted' and expires_at<=datetime('now')").fetchone()[0]:raise RuntimeError('Pending asset cleanup requires review')
    if list((DATA/'tmp').glob('litera-pdf-export-*')):raise RuntimeError('Export cleanup candidates require review')
    if not built():raise RuntimeError('Unified static build missing/stale; no service started')
    sys.path.insert(0,str(ROOT/'scripts'))
    from mock_answer_fixture import enable_mock_answers
    enable_mock_answers()
    from app.main import app
    from app.acceptance_site import mount_acceptance_site
    mount_acceptance_site(app,ROOT/'frontend/dist')
    import asyncio,uvicorn
    asyncio.run(serve_api(uvicorn.Server(uvicorn.Config(app,host=FRONT_HOST,port=FRONT_PORT,log_level='info'))))


async def serve_api(server):
    import asyncio
    async def watch():
        while not server.should_exit:
            try: ensure_space()
            except (RuntimeError,OSError):
                server.should_exit=True
                return
            if (DATA/'stop.request').exists():
                server.should_exit=True
                return
            await asyncio.sleep(.25)
    watcher=asyncio.create_task(watch())
    try: await server.serve()
    finally:
        watcher.cancel()
        try:await watcher
        except asyncio.CancelledError:pass


def stop_children(children):
    import psutil
    # Snapshot only the processes we created and their descendants, before any
    # wrapper can exit and orphan its actual Python worker.
    owned={}
    for child in children:
        try:
            parent=psutil.Process(child.pid)
            for process in [parent,*parent.children(recursive=True)]:owned[process.pid]=process
        except psutil.Error:pass
    (DATA/'stop.request').touch()
    # The API observes the marker and performs normal uvicorn shutdown.
    for child in reversed(children[1:]):
        if child.poll() is None:child.terminate()
    deadline=time.monotonic()+15
    while time.monotonic()<deadline and any(p.is_running() for p in owned.values()):
        time.sleep(.2)
        # Hidden conhost may outlive an already stopped Python wrapper.
        if all(child.poll() is not None for child in children):break
    for process in reversed(list(owned.values())):
        try:
            # psutil Process identity includes creation time to protect PID reuse.
            if process.is_running():process.terminate()
        except psutil.Error:pass
    psutil.wait_procs(list(owned.values()),timeout=3)


def supervise():
    import psutil
    check();db_check();children=[];written=False
    stamp=time.strftime('%Y%m%d-%H%M%S');stop_file=DATA/'stop.request'
    try:
        with (DATA/f'api-{stamp}.log').open('x',encoding='utf-8') as alog:
            flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            children.append(subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'api'],stdout=alog,stderr=subprocess.STDOUT,creationflags=flags))
            for _ in range(50):
                ensure_space()
                if children[0].poll() is not None:raise RuntimeError('API exited; inspect log, no automatic retry')
                try:
                    with HTTP.open(API+'/api/v1/health',timeout=1) as r:
                        if r.status==200:break
                except OSError:pass
                time.sleep(.3)
            else:raise RuntimeError('API health timed out')
            with PID_FILE.open('x',encoding='utf-8') as f:json.dump({'supervisor':os.getpid(),'created':psutil.Process().create_time(),'children':[p.pid for p in children],'origin':ORIGIN,'api':API,'database':str(DATA/'preview.db')},f)
            written=True
            while not stop_file.exists():
                free=ensure_space();(DATA/'disk-status.json').write_text(json.dumps({'time':time.time(),'freeBytes':free}),encoding='utf-8')
                if any(p.poll() is not None for p in children):raise RuntimeError('Preview child exited; no automatic retry')
                time.sleep(5)
    finally:
        stop_children(children)
        if written:PID_FILE.unlink(missing_ok=True)
        stop_file.unlink(missing_ok=True)


def stop():
    import psutil
    if not PID_FILE.exists():print('No user-model preview manifest; no process stopped');return
    info=json.loads(PID_FILE.read_text(encoding='utf-8'))
    try:
        p=psutil.Process(info['supervisor'])
        if abs(p.create_time()-info['created'])>=1 or not any(Path(a).resolve()==Path(__file__).resolve() for a in p.cmdline()[1:] if a.endswith('.py')):raise RuntimeError('Manifest identity mismatch')
    except psutil.Error:raise RuntimeError('Stale manifest; no process stopped') from None
    (DATA/'stop.request').touch();print('Stop requested only for user-model preview; all data retained')


def status():
    for url in [ORIGIN,ORIGIN+'/api/v1/health',API+'/api/v1/health']:
        try:
            with HTTP.open(url,timeout=3) as r:print(url,r.status)
        except OSError:print(url,'unavailable')
    print('Manifest present:',PID_FILE.exists())

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['check','build','prepare','api','supervise','stop','status']);globals()[parser.parse_args().action]()
