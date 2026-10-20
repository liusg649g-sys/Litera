"""One protected synchronous request owns capture, rendering and download cleanup."""
import asyncio
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import quote

import psutil
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .annotations import dto
from .database import get_db, SessionLocal
from .documents import owned_document, reject, storage_path
from .models import Annotation, DocumentReaderState
from .reader_assets import lock_document, validate_asset, asset_storage_path
from .schemas import InputModel

MAX_OUTPUT=200*1024**2
MAX_MEMORY=512*1024**2
TIMEOUT=60
DOWNLOAD_TIMEOUT=120
MAX_SNAPSHOT=16*1024**2
PREFIX='litera-pdf-export-'
gate=threading.Lock()


class ExportResponse(StreamingResponse):
    """Also bound slow downloads, and release capacity even before iteration starts."""
    def __init__(self,*args,root,**kwargs):
        self.workspace=root
        super().__init__(*args,**kwargs)

    async def __call__(self,scope,receive,send):
        try:
            async with asyncio.timeout(DOWNLOAD_TIMEOUT):
                await super().__call__(scope,receive,send)
        finally:
            try:cleanup(self.workspace)
            finally:gate.release()


class ExportInput(InputModel):
    expectedAnnotationRevision: int = Field(ge=0,strict=True)


def cleanup(root):
    # Only our random, direct OS-temp child directories can be removed.
    root=Path(root)
    if root.parent.resolve()!=Path(tempfile.gettempdir()).resolve() or not root.name.startswith(PREFIX) or root.is_symlink():
        raise ValueError('Invalid export workspace')
    shutil.rmtree(root,ignore_errors=True)


def sweep_exports():
    try:roots=list(Path(tempfile.gettempdir()).glob(PREFIX+'*'))
    except OSError:
        logging.exception('Cannot scan PDF export workspaces');return
    for root in roots:
        try:
            if not root.is_dir() or root.is_symlink():continue
            expired=time.time()-root.stat().st_mtime>3600
            try:
                owner=json.loads((root/'owner.json').read_text())
                active=psutil.pid_exists(owner['pid']) and abs(psutil.Process(owner['pid']).create_time()-owner['created'])<1
            except (OSError,ValueError,KeyError,TypeError,psutil.Error):active=True
            if not active or expired:cleanup(root)
        except (OSError,ValueError):
            # An inaccessible directory must not stop B2's shared cleanup loop.
            logging.exception('PDF export workspace cleanup will retry')


def capture(db,owner,id,revision,root):
    lock_document(db,owner,id)
    doc,attachment=owned_document(db,owner,id,lock=True)
    if doc.purge_job_id:reject(404,'DOCUMENT_NOT_FOUND','文献不存在或不可访问')
    state=db.scalar(select(DocumentReaderState).where(DocumentReaderState.document_id==id,DocumentReaderState.owner_id==owner).with_for_update())
    actual=state.annotation_revision if state else 0
    if revision!=actual:reject(409,'ANNOTATION_REVISION_CONFLICT','已保存批注版本已变化，请核对并载入最新批注后重试',{'annotationRevision':actual})
    # Bound ORM/JSON allocation before materializing a potentially huge collection.
    items=[];json_bytes=0;last_id=''
    while True:
        batch=db.scalars(select(Annotation).where(Annotation.document_id==id,Annotation.owner_id==owner,
            Annotation.deleted_at.is_(None),Annotation.id>last_id).order_by(Annotation.id).limit(16).with_for_update()).all()
        if not batch:break
        for row in batch:
            item=dto(row);json_bytes+=len(json.dumps(item,ensure_ascii=False).encode())
            if json_bytes>MAX_SNAPSHOT or len(items)>=10000:reject(413,'EXPORT_LIMIT','批注快照不能超过16MiB或10000对象')
            items.append(item);last_id=row.id;db.expunge(row)
    assets={};total=0
    source=storage_path(attachment.storage_key)
    if not source.is_file():reject(404,'PDF_UNAVAILABLE','原始PDF资源不存在')
    if source.stat().st_size>50*1024**2:reject(413,'EXPORT_LIMIT','导出原始PDF不能超过50MiB')
    for a in items:
        if a['assetId'] and a['assetId'] not in assets:
            asset=validate_asset(db,owner,id,a['assetId'])
            path=asset_storage_path(asset.storage_key);total+=path.stat().st_size
            if total>50*1024**2:reject(413,'EXPORT_LIMIT','导出图片合计不能超过50MiB')
            name=f'asset-{len(assets)}'+path.suffix;assets[a['assetId']]=name
            shutil.copyfile(path,root/name)
    payload=json.dumps(dict(items=items,assets=assets,revision=actual),ensure_ascii=False)
    if len(payload.encode())>MAX_SNAPSHOT:reject(413,'EXPORT_LIMIT','批注快照不能超过16MiB')
    shutil.copyfile(source,root/'source.pdf')
    (root/'snapshot.json').write_text(payload,encoding='utf-8')
    db.commit()  # immutable physical copies own all resources from this point
    return attachment.original_name


async def run_worker(root,request):
    process=subprocess.Popen([sys.executable,'-m','app.pdf_export_worker',str(root)],cwd=Path(__file__).parents[1],
                             stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
    started=time.monotonic()
    try:
        while process.poll() is None:
            if await request.is_disconnected():reject(499,'EXPORT_CANCELED','导出已取消')
            if time.monotonic()-started>TIMEOUT:reject(504,'EXPORT_TIMEOUT','PDF导出超过60秒，请减少批注或拆分文献后重试')
            try:memory=psutil.Process(process.pid).memory_info().rss
            except psutil.NoSuchProcess:memory=0
            if memory>MAX_MEMORY:reject(413,'EXPORT_MEMORY_LIMIT','PDF导出超过512MiB内存限制')
            if (root/'result.pdf').exists() and (root/'result.pdf').stat().st_size>MAX_OUTPUT:
                reject(413,'EXPORT_OUTPUT_LIMIT','导出文件超过200MiB限制')
            await asyncio.sleep(.1)
        if process.returncode:
            error=json.loads((root/'error.json').read_text(encoding='utf-8')) if (root/'error.json').is_file() else dict(code='EXPORT_FAILED',message='PDF导出进程异常结束，请重试')
            reject(413 if error['code']=='EXPORT_LIMIT' else 422,error['code'],error['message'])
        if not (root/'result.pdf').is_file() or (root/'result.pdf').stat().st_size>MAX_OUTPUT:
            reject(413,'EXPORT_OUTPUT_LIMIT','导出文件不存在或超过200MiB限制')
    finally:
        if process.poll() is None:process.kill()
        await run_in_threadpool(process.wait)


def create_export_router(current_session,require_csrf):
    router=APIRouter(prefix='/api/v1/documents/{id}',tags=['pdf-export'])

    @router.post('/annotated-pdf',response_class=StreamingResponse,responses={200:{'content':{'application/pdf':{}},'description':'已保存快照的带批注PDF附件'}})
    async def export(id:str,payload:ExportInput,request:Request,session=Depends(require_csrf),db:Session=Depends(get_db)):
        # Authorize before reporting capacity, including other users' requests.
        owned_document(db,session.user_id,id)
        if not gate.acquire(blocking=False):reject(429,'EXPORT_BUSY','已有PDF正在导出或下载，请稍后重试')
        root=None;streaming=False
        try:
            root=Path(tempfile.mkdtemp(prefix=PREFIX))
            (root/'owner.json').write_text(json.dumps(dict(pid=os.getpid(),created=psutil.Process().create_time())))
            name=await run_in_threadpool(capture,db,session.user_id,id,payload.expectedAnnotationRevision,root)
            await run_worker(root,request)
            # Fresh transaction: reject logout, soft delete or purge during rendering.
            db.rollback()
            with SessionLocal() as verify:
                current_session(request,verify)
                doc,_=owned_document(verify,session.user_id,id)
                if doc.purge_job_id:reject(404,'DOCUMENT_NOT_FOUND','文献不存在或不可访问')
            length=(root/'result.pdf').stat().st_size
            async def chunks():
                with (root/'result.pdf').open('rb') as handle:
                    while chunk:=await run_in_threadpool(handle.read,65536):
                        yield chunk
            filename=Path(name).stem+'_带批注.pdf'
            response=ExportResponse(chunks(),root=root,media_type='application/pdf',headers={
                'Content-Disposition':"attachment; filename=\"litera-annotated.pdf\"; filename*=UTF-8''"+quote(filename,safe=''),
                'Content-Length':str(length),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
                'X-Annotation-Revision':str(payload.expectedAnnotationRevision)})
            streaming=True
            return response
        except OSError:
            reject(503,'EXPORT_RESOURCE_ERROR','导出临时资源不可用，请稍后重试')
        finally:
            if not streaming:
                db.rollback()
                try:
                    if root:cleanup(root)
                finally:gate.release()
    return router
