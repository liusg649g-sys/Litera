"""Mount a prebuilt SPA onto the same API process; never expose data directories."""
from pathlib import Path
from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

class AcceptanceFiles(StaticFiles):
    async def get_response(self,path,scope):
        path=path.replace(chr(92),'/').lstrip('/')
        if path in ('','.'):path='index.html'
        if path=='api' or path.startswith('api/') or any(part in ('.','..') for part in path.split('/')):
            raise HTTPException(404)
        try:
            response=await super().get_response(path,scope)
        except HTTPException as error:
            if error.status_code!=404 or '.' in path.rsplit('/',1)[-1]:raise
            response=await super().get_response('index.html',scope)
        if path in ('','index.html') or response.headers.get('content-type','').startswith('text/html'):
            response.headers['Cache-Control']='no-store'
        return response

def mount_acceptance_site(app,directory:Path):
    if not (directory/'index.html').is_file():raise RuntimeError('Build the unified frontend before starting')
    app.mount('/',AcceptanceFiles(directory=str(directory),html=True,follow_symlink=False),name='unified-frontend')
