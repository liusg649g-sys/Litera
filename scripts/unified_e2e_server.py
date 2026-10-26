"""ONE static/API process, disposable SQLite. Personal-provider HTTP is controlled Mock.
This fixture never reads backend/.env, calls a real service or opens acceptance data.
"""
import json,os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='litera-unified-') as folder:
 data=Path(folder);scratch=data/'tmp';scratch.mkdir()
 for key in list(os.environ):
  if key.startswith(('AI_','TRANSLATION_')):os.environ.pop(key)
 os.environ.update(DATABASE_URL='sqlite:///'+(data/'test.db').as_posix(),PDF_STORAGE_ROOT=str(data/'pdfs'),SESSION_SECRET='synthetic-unified-browser-secret-only-32-characters',PUBLIC_ORIGIN='http://127.0.0.1:5184',APP_ENV='development',USER_MODELS_ENABLED='true',TRANSLATION_MOCK_ENABLED='true',UNIFIED_ACCEPTANCE='true',LITERA_DISABLE_DEVELOPER_MODEL='1',AUTH_RATE_LIMIT='200',COOKIE_SECURE='false',TEMP=str(scratch),TMP=str(scratch),TMPDIR=str(scratch))
 import base64
 test_key=data/'synthetic-vault.key';test_key.write_bytes(base64.urlsafe_b64encode(os.urandom(32)));test_key.chmod(0o600)
 os.environ.update(USER_MODEL_SECRET_BACKEND='aesgcm_file',USER_MODEL_MASTER_KEY_FILE=str(test_key))
 tempfile.tempdir=str(scratch);os.chdir(data);sys.path.insert(0,str(ROOT/'backend'));sys.path.insert(0,str(ROOT/'scripts'))
 from alembic import command
 from alembic.config import Config
 cfg=Config(str(ROOT/'backend/alembic.ini'));cfg.set_main_option('script_location',str(ROOT/'backend/migrations'));command.upgrade(cfg,'head')
 import httpx
 from app import ai_service
 original=httpx.AsyncClient
 async def reply(request):
  content=json.loads(request.content)
  if request.headers.get('authorization')=='Bearer synthetic-wrong-key':return httpx.Response(401,json={'error':'controlled failure'})
  return httpx.Response(200,json={'choices':[{'message':{'content':'[CONTROLLED HTTP MOCK - NOT REAL AI] '+content['model']+' / Synthetic translated excerpt'},'finish_reason':'stop'}]})
 ai_service.httpx.AsyncClient=lambda **kw:original(**{**kw,'transport':httpx.MockTransport(reply)})
 from mock_answer_fixture import enable_mock_answers
 enable_mock_answers()
 from app.main import app
 from app.acceptance_site import mount_acceptance_site
 mount_acceptance_site(app,Path(os.environ.get('LITERA_TEST_FRONTEND_DIST',str(ROOT/'frontend/dist'))))
 print('Unified disposable browser fixture; no real model traffic',flush=True)
 import uvicorn
 uvicorn.run(app,host='127.0.0.1',port=5184,log_level='warning')
