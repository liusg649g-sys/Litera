"""Reproducible isolated checks; never starts/migrates persistent Litera sites.
Run with the installed backend venv Python. Model calls are controlled fixtures.
"""
import argparse,json,locale,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
import psutil
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.cache/github-delivery'
FRONT=ROOT/'frontend'
BUILD=OUT/'frontend-dist'
MIN_FREE=10_000_000_000
SUITES={'notes':'playwright.notes.config.ts','translation':'playwright.translation.config.ts','captures':'playwright.note-captures.config.ts','user-models':'playwright.user-models.config.ts','unified':'playwright.unified.config.ts'}

def free():
    roots={ROOT.anchor}
    if os.name=='nt':roots.add('C:/')
    return {path:shutil.disk_usage(path).free for path in roots}

def environment():
    env={k:v for k,v in os.environ.items() if not k.startswith(('AI_','TRANSLATION_','USER_MODEL_','VITE_')) and not (k.startswith('LITERA_') and k.endswith('_PDF'))}
    env.update(LITERA_DISABLE_DEVELOPER_MODEL='1',NODE_OPTIONS='--max-old-space-size=1024',PYTHONIOENCODING='utf-8',CI='true')
    return env

def run(label,args,cwd,env):
    OUT.mkdir(parents=True,exist_ok=True)
    minimum=free()
    if min(minimum.values())<MIN_FREE:raise SystemExit('Below original 10GB safety threshold; nothing started')
    log=OUT/(label+'.log');stopped=False
    with log.open('w',encoding='utf-8') as stream:
        process=subprocess.Popen(args,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT)
        while process.poll() is None:
            available=free();minimum={k:min(minimum[k],available[k]) for k in minimum}
            if min(available.values())<MIN_FREE:
                stopped=True
                try:children=psutil.Process(process.pid).children(recursive=True)
                except psutil.Error:children=[]
                for child in reversed(children):
                    try:child.terminate()
                    except psutil.Error:pass
                process.terminate();process.wait();break
            time.sleep(1)
    result=dict(exit=process.returncode,guardStopped=stopped,minimumDisk=minimum,diskAfter=free(),log=str(log))
    (OUT/(label+'-run.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(log.read_text(encoding='utf-8',errors='replace')[-6000:]);print(json.dumps(result),flush=True)
    if stopped or process.returncode:raise SystemExit(85 if stopped else process.returncode)

def backend(files):
    paths=[ROOT/'backend/tests'/name for name in files] if files else sorted((ROOT/'backend/tests').glob('test_*.py'))
    if not paths or any(not p.is_file() or p.parent!=ROOT/'backend/tests' for p in paths):raise SystemExit('Invalid isolated test list')
    with tempfile.TemporaryDirectory(prefix='litera-delivery-tests-') as folder:
        data=Path(folder)
        (data/'alembic.ini').write_text('[alembic]\nscript_location = '+(ROOT/'backend/migrations').as_posix()+'\nprepend_sys_path = '+(ROOT/'backend').as_posix()+'\npath_separator = os\n',encoding=locale.getencoding())
        (data/'sitecustomize.py').write_text("import socket,ipaddress\n_original=socket.getaddrinfo\ndef safe(host):\n if host is None or host=='localhost':return True\n try:return ipaddress.ip_address(host.decode() if isinstance(host,bytes) else host).is_loopback\n except (ValueError,TypeError):return False\ndef resolve(host,*a,**kw):\n if not safe(host):raise OSError('Isolated tests: external network disabled')\n return _original(host,*a,**kw)\nsocket.getaddrinfo=resolve\n_connect=socket.socket.connect\ndef connect(self,address):\n if isinstance(address,tuple) and not safe(address[0]):raise OSError('Isolated tests: external network disabled')\n return _connect(self,address)\nsocket.socket.connect=connect\n",encoding='utf-8')
        env=environment();env.update(APP_ENV='test',USER_MODELS_ENABLED='false',TEST_DATABASE_URL='',DATABASE_URL='sqlite:///'+(data/'bootstrap.db').as_posix(),TEMP=folder,TMP=folder,TMPDIR=folder,PYTHONPATH=str(data)+os.pathsep+str(ROOT/'backend'))
        run('backend-targeted' if files else 'backend',[sys.executable,'-m','pytest',*[str(p) for p in paths],'-q','--tb=short','--junitxml='+str(OUT/'backend.xml'),'-o','cache_dir='+str(data/'cache')],data,env)

def node():
    value=shutil.which('node')
    if not value:raise SystemExit('Install project Node dependencies first')
    return value

def frontend():
    run('frontend',[node(),'node_modules/vitest/vitest.mjs','run','--maxWorkers=1'],FRONT,environment())

def types():
    run('types',[node(),'node_modules/vue-tsc/bin/vue-tsc.js','--noEmit'],FRONT,environment())

def build():
    if any(p.name!='.env.example' for p in FRONT.glob('.env*')):raise SystemExit('Private frontend dotenv exists; review before building')
    types()
    env=environment();env.update(VITE_LITERA_UNIFIED_ACCEPTANCE='true',VITE_LITERA_PREVIEW_MOCK='false',VITE_LITERA_USER_MODEL_PREVIEW='false')
    run('build',[node(),'node_modules/vite/bin/vite.js','build','--outDir',str(BUILD)],FRONT,env)

def browser(suites):
    if not (BUILD/'index.html').is_file():raise SystemExit('Run build first; do not overwrite live frontend/dist')
    for name in suites or SUITES:
        if name not in SUITES:raise SystemExit('Unknown browser suite')
        env=environment();env.update(LITERA_TEST_FRONTEND_DIST=str(BUILD),LITERA_TEST_PYTHON=sys.executable,PLAYWRIGHT_JUNIT_OUTPUT_FILE=str(OUT/('browser-'+name+'.xml')))
        run('browser-'+name,[node(),'node_modules/@playwright/test/cli.js','test','--config='+SUITES[name],'--reporter=list,junit'],FRONT,env)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('scope',choices=['backend','frontend','types','build','browser']);parser.add_argument('items',nargs='*');args=parser.parse_args()
    if args.scope in ('backend','browser'):globals()[args.scope](args.items)
    else:globals()[args.scope]()
