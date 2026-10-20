import asyncio
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import time
from urllib.parse import unquote
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from sqlalchemy import select

from app import pdf_exports as exports
from app.database import SessionLocal
from app.main import app
from app.models import Annotation, DocumentFile, Document, ReaderAsset
from app.pdf_export_renderer import render, mark_lines, checked_text, ExportError
from test_documents import logged,pdf,upload
from test_annotations import command,data
from test_reader_assets import asset,object_data
from export_samples import samples,KINDS


def post(client,path,revision=0):
    return client.post(path+'/annotated-pdf',json=dict(expectedAnnotationRevision=revision))


def test_real_process_download_snapshot_hash_and_cleanup(logged,pdf):
    id=upload(logged,pdf).json()['id'];path='/api/v1/documents/'+id
    created=logged.post(path+'/annotations',json=command(annotation=data('comment')))
    assert created.status_code==201
    original_mkdtemp=tempfile.mkdtemp;created=[]
    def track(*args,**kwargs):
        root=original_mkdtemp(*args,**kwargs);created.append(Path(root));return root
    with patch.object(exports.tempfile,'mkdtemp',track):response=post(logged,path,1)
    assert response.status_code==200,response.text
    assert response.headers['content-type']=='application/pdf'
    assert response.headers['x-annotation-revision']=='1'
    assert unquote(response.headers['content-disposition'].split("filename*=UTF-8''",1)[1])=='论文_带批注.pdf'
    assert int(response.headers['content-length'])==len(response.content)
    doc=PdfReader(BytesIO(response.content));assert len(doc.pages)==1
    note=next(a.get_object() for a in doc.pages[0].annotations if a.get_object()['/Subtype']=='/Text')
    assert note['/Contents']=='中文正文\n第二行'
    assert note['/AP']['/N'].get_object().get_data()
    assert note['/Popup'].get_object()['/Parent']==note
    assert hashlib.sha256(logged.get(path+'/content').content).digest()==hashlib.sha256(pdf).digest()
    assert created and all(not root.exists() for root in created)
    assert not exports.gate.locked()


@pytest.mark.parametrize('kind',KINDS)
def test_all_13_real_saved_types(logged,pdf,kind):
    path='/api/v1/documents/'+upload(logged,pdf).json()['id']
    aid=asset(logged,path)['assetId'] if kind in ('signature','image') else None
    value=data(kind) if kind in KINDS[:6] else object_data(kind,aid)
    assert logged.post(path+'/annotations',json=command(annotation=value)).status_code==201
    response=post(logged,path,1);assert response.status_code==200,response.text
    reader=PdfReader(BytesIO(response.content))
    assert len(reader.pages)==1
    if kind!='comment':assert reader.pages[0].get_contents().get_data()
    if value['content']:
        assert any(a.get_object().get('/Contents')==value['content'] for a in reader.pages[0].annotations)


def test_revision_permission_csrf_soft_delete(logged,pdf):
    path='/api/v1/documents/'+upload(logged,pdf).json()['id']
    assert post(logged,path,1).status_code==409
    assert logged.post(path+'/annotated-pdf',json={}).status_code==422
    assert post(logged,path,-1).status_code==422
    csrf=logged.headers.pop('X-CSRF-Token');assert post(logged,path).status_code==403
    logged.headers['X-CSRF-Token']=csrf
    assert logged.post(path+'/annotated-pdf',headers={'Origin':'https://evil.example'},json={'expectedAnnotationRevision':0}).status_code==403
    with TestClient(app,headers={'Origin':'http://localhost:8080'}) as anonymous:assert post(anonymous,path).status_code==401
    with SessionLocal() as db:
        doc=db.get(Document,path.rsplit('/',1)[1]);assert doc.last_read_at is None
    assert logged.delete(path).status_code==204
    assert post(logged,path).status_code==404


def test_capture_survives_edits_and_asset_removal(logged,pdf,tmp_path):
    id=upload(logged,pdf).json()['id'];path='/api/v1/documents/'+id
    aid=asset(logged,path)['assetId']
    a=logged.post(path+'/annotations',json=command(annotation=object_data('image',aid))).json()['annotation']
    with SessionLocal() as db:
        exports.capture(db,db.get(Document,id).owner_id,id,1,tmp_path)
    snapshot=json.loads((tmp_path/'snapshot.json').read_text(encoding='utf-8'))
    assert logged.request('DELETE',path+'/annotations/'+a['id'],json=command(1,version=1)).status_code==200
    # B2 deliberately protects the 24h undo lease. Expire it before sweeping.
    from datetime import timedelta
    from app.reader_assets import now,sweep_assets
    with SessionLocal() as db:db.get(ReaderAsset,aid).expires_at=now()-timedelta(seconds=1);db.commit()
    sweep_assets()
    with SessionLocal() as db:assert db.get(ReaderAsset,aid).status=='deleted'
    render(tmp_path/'source.pdf',snapshot['items'],{k:tmp_path/v for k,v in snapshot['assets'].items()},tmp_path/'result.pdf',1)
    assert PdfReader(tmp_path/'result.pdf').metadata['/LiteraAnnotationRevision']=='1'
    assert len(snapshot['items'])==1
    assert post(logged,path,1).status_code==409
    assert post(logged,path,2).status_code==200


def test_cross_user_document_and_missing_asset(logged,pdf):
    id=upload(logged,pdf).json()['id'];path='/api/v1/documents/'+id
    other='/api/v1/documents/'+upload(logged,pdf+b'\n%other').json()['id']
    aid=asset(logged,path)['assetId']
    logged.post(path+'/annotations',json=command(annotation=object_data('image',aid)))
    assert post(logged,other).status_code==200
    from test_auth import register,login
    with TestClient(app,headers={'Origin':'http://localhost:8080'}) as second:
        register(second,'second-export@example.com');second.headers['X-CSRF-Token']=login(second,'second-export@example.com').json()['csrfToken']
        assert post(second,path,1).status_code==404
    with SessionLocal() as db:
        row=db.get(ReaderAsset,aid)
        from app.reader_assets import asset_storage_path
        asset_storage_path(row.storage_key).unlink()
    assert post(logged,path,1).status_code==422
    assert not exports.gate.locked()
    assert logged.get(path+'/annotations').json()['annotationRevision']==1


def test_inflight_delete_and_logout_reauthorize(logged,pdf):
    id=upload(logged,pdf).json()['id'];path='/api/v1/documents/'+id
    actual=exports.run_worker
    async def deleted(root,request):
        await actual(root,request)
        from datetime import datetime
        with SessionLocal() as db:db.get(Document,id).deleted_at=datetime.now();db.commit()
    with patch.object(exports,'run_worker',deleted):assert post(logged,path).status_code==404
    with SessionLocal() as db:db.get(Document,id).deleted_at=None;db.commit()
    async def logged_out(root,request):
        await actual(root,request)
        from app.models import LoginSession
        from datetime import datetime
        with SessionLocal() as db:
            for row in db.scalars(select(LoginSession)):row.revoked_at=datetime.now()
            db.commit()
    with patch.object(exports,'run_worker',logged_out):assert post(logged,path).status_code==401
    assert not exports.gate.locked()


def test_actual_worker_termination_and_purge_race(logged,pdf):
    import threading
    id=upload(logged,pdf).json()['id'];path='/api/v1/documents/'+id
    original=exports.subprocess.Popen;processes=[]
    def killed(*args,**kwargs):
        process=original(*args,**kwargs);processes.append(process)
        threading.Timer(.1,lambda:process.kill() if process.poll() is None else None).start()
        return process
    with patch.object(exports.subprocess,'Popen',killed):assert post(logged,path).status_code==422
    assert processes and processes[0].poll() is not None
    assert not exports.gate.locked()
    actual=exports.run_worker
    async def purging(root,request):
        await actual(root,request)
        with SessionLocal() as db:db.get(Document,id).purge_job_id='inflight-test-job';db.commit()
    with patch.object(exports,'run_worker',purging):assert post(logged,path).status_code==404
    with SessionLocal() as db:db.get(Document,id).purge_job_id=None;db.commit()
    assert post(logged,path).status_code==200


def test_concurrent_capacity_and_failure_retry(logged,pdf):
    path='/api/v1/documents/'+upload(logged,pdf).json()['id']
    exports.gate.acquire()
    try:assert post(logged,path).status_code==429
    finally:exports.gate.release()
    with patch.object(exports.subprocess,'Popen',side_effect=OSError('injected')):assert post(logged,path).status_code==503
    assert not exports.gate.locked()
    assert post(logged,path).status_code==200


@pytest.mark.parametrize('failure',['timeout','disconnect','memory','output'])
def test_kill_worker_on_resource_or_disconnect(logged,pdf,failure):
    path='/api/v1/documents/'+upload(logged,pdf).json()['id']
    if failure=='timeout':
        with patch.object(exports,'TIMEOUT',0):response=post(logged,path)
        assert response.status_code==504
    elif failure=='disconnect':
        async def disconnected(_):return True
        with patch('starlette.requests.Request.is_disconnected',disconnected):response=post(logged,path)
        assert response.status_code==499
    elif failure=='memory':
        with patch.object(exports,'MAX_MEMORY',1):response=post(logged,path)
        assert response.status_code==413
    else:
        with patch.object(exports,'MAX_OUTPUT',1):response=post(logged,path)
        assert response.status_code==413
    assert not exports.gate.locked()
    assert post(logged,path).status_code==200


def test_orphan_cleanup_and_unsupported_glyph(logged,pdf):
    root=Path(tempfile.mkdtemp(prefix=exports.PREFIX))
    (root/'owner.json').write_text(json.dumps(dict(pid=999999999,created=0)))
    (root/'partial.pdf').write_bytes(b'half')
    exports.sweep_exports();assert not root.exists()
    path='/api/v1/documents/'+upload(logged,pdf).json()['id'];value=data('comment');value['content']='missing \U0010ffff'
    assert logged.post(path+'/annotations',json=command(annotation=value)).status_code==201
    result=post(logged,path,1)
    assert result.status_code==422 and result.json()['error']['code']=='EXPORT_UNSUPPORTED_GLYPH'
    assert logged.get(path+'/annotations').json()['items'][0]['content']==value['content']


def test_renderer_rotation_cropbox_userunit_text_alpha_and_all_types(tmp_path):
    fitz=pytest.importorskip('fitz')  # Development-only independent renderer, not production dependency.
    source,items,assets=samples(tmp_path)
    before=hashlib.sha256(source.read_bytes()).digest();render(source,items,assets,tmp_path/'export.pdf',52)
    assert hashlib.sha256(source.read_bytes()).digest()==before
    original=PdfReader(source);output=PdfReader(tmp_path/'export.pdf')
    assert len(output.pages)==4
    for i in range(4):
        assert list(output.pages[i].cropbox)==list(original.pages[i].cropbox)
        assert output.pages[i].rotation==original.pages[i].rotation
        assert output.pages[i].get('/UserUnit',1)==original.pages[i].get('/UserUnit',1)
    bodies=[a.get_object() for page in output.pages for a in page.annotations or [] if a.get_object().get('/Contents')]
    text='\n'.join(a['/Contents'] for a in bodies)
    for a in items:
        if a['content']:assert a['content'] in [body['/Contents'] for body in bodies]
    assert 'αβ ±∞ →' in text and '完整内容不应丢失' in text
    pdf=fitz.open(tmp_path/'export.pdf');base=fitz.open(source)
    for i in range(4):
        new=pdf[i].get_pixmap();old=base[i].get_pixmap()
        assert (new.width,new.height)==(old.width,old.height)
        assert sum(a!=b for a,b in zip(new.samples,old.samples))>1000
        # Independent raster check of every object's local region, every rotation.
        # Unrotate only the in-memory test view to use normalized CropBox pixels.
        from PIL import Image,ImageChops
        page=pdf[i];page.set_rotation(0);original_page=base[i];original_page.set_rotation(0)
        new=page.get_pixmap();old=original_page.get_pixmap()
        delta=ImageChops.difference(Image.frombytes('RGB',(new.width,new.height),new.samples),Image.frombytes('RGB',(old.width,old.height),old.samples))
        for a in (a for a in items if a['pageNumber']==i+1):
            g=a['geometry']
            if g['kind']=='box':r=g['rect']
            elif g['kind']=='text':r=g['positions'][0]['rects'][0]
            elif g['kind']=='anchor':r=dict(x=max(0,g['x']-.03),y=max(0,g['y']-.08),width=.13,height=.14)
            else:
                xs=[p['x'] for p in g['points']];ys=[p['y'] for p in g['points']]
                r=dict(x=min(xs),y=min(ys),width=max(xs)-min(xs),height=max(ys)-min(ys))
            box=(int(r['x']*new.width)-2,int(r['y']*new.height)-2,int((r['x']+r['width'])*new.width)+2,int((r['y']+r['height'])*new.height)+2)
            assert delta.crop(box).getbbox() is not None,(i,a['type'])
    assert '/SMask' in str(output.pages[0]['/Resources']['/XObject']) or any('/SMask' in v.get_object() for v in output.pages[0]['/Resources']['/XObject'].values())


@pytest.mark.parametrize('kind',['comment','freeText','watermark'])
def test_native_unicode_body_popup_appearance_and_original_annotations_preserved(tmp_path,kind):
    from pypdf.annotations import Text
    source,items,assets=samples(tmp_path)
    original=PdfWriter(clone_from=source)
    original.add_annotation(0,Text(rect=(300,300,320,320),text='原文件已有注释'))
    original.write(source)
    objects=[a for a in items if a['type']==kind]
    if kind=='comment':
        # Also cover text-anchored, multi-page comments, including source rotation.
        a=objects[0];a['geometry']={'kind':'text','positions':[
            {'pageNumber':n,'rects':[dict(x=.8,y=.01,width=.1,height=.03)],'textQuote':'anchor'} for n in (1,2)]}
    render(source,objects,assets,tmp_path/'native.pdf',7)
    output=PdfReader(tmp_path/'native.pdf');assert len(output.pages)==4
    assert any(a.get_object().get('/Contents')=='原文件已有注释' for a in output.pages[0].annotations)
    for i,page in enumerate(output.pages):
        notes=[a.get_object() for a in page.annotations if a.get_object().get('/NM','').startswith('litera-')]
        assert len(notes)==(2 if kind=='comment' and i==1 else 1)
        for note in notes:
            assert note['/F']==4 and note['/T']=='Litera'
            popup=note['/Popup'].get_object();assert popup['/Subtype']=='/Popup'
            assert popup['/Parent']==note and popup['/Open'].value is False
            assert note['/Contents'] in [a['content'] for a in objects]
            ap=note['/AP']['/N'].get_object();assert len(ap['/BBox'])==4
            assert '/A' not in note and '/AA' not in note and '/RC' not in note
            if kind=='comment':
                assert note['/Subtype']=='/Text' and ap.get_data()
            else:
                # Text semantics must not introduce a /Stamp: Edge paints an
                # extra comment indicator for stamps despite their empty AP.
                assert note['/Subtype']=='/FreeText' and ap.get_data()==b''


def test_superscript_body_baseline_and_separate_columns():
    rows=mark_lines([dict(x=.1,y=.2,width=.2,height=.02),dict(x=.30,y=.19,width=.01,height=.012),dict(x=.31,y=.2,width=.1,height=.02),dict(x=.8,y=.2,width=.1,height=.02)],600,800)
    assert len(rows)==2
    assert rows[0]['rect']['y']==.19 and rows[0]['body']['y']==.2


def test_snapshot_budget_before_copy_and_corrupt_source_process_retry(logged,pdf):
    id=upload(logged,pdf).json()['id'];path='/api/v1/documents/'+id
    assert logged.post(path+'/annotations',json=command(annotation=data('comment'))).status_code==201
    with patch.object(exports,'MAX_SNAPSHOT',1):assert post(logged,path,1).status_code==413
    assert not exports.gate.locked()
    with SessionLocal() as db:
        from app.documents import storage_path
        source=storage_path(db.scalar(select(DocumentFile).where(DocumentFile.document_id==id)).storage_key)
    source.write_bytes(b'broken test PDF')
    assert post(logged,path,1).status_code==422
    source.write_bytes(pdf)
    assert post(logged,path,1).status_code==200


@pytest.mark.parametrize('failure',['disconnect','timeout'])
def test_stream_cleanup_even_when_send_fails_before_first_chunk(failure):
    root=Path(tempfile.mkdtemp(prefix=exports.PREFIX));(root/'result.pdf').write_bytes(b'%PDF')
    exports.gate.acquire()
    async def run():
        async def receive():return {'type':'http.disconnect'}
        async def send(message):
            if failure=='disconnect':raise OSError('injected client disconnect')
            await asyncio.sleep(.1)
        response=exports.ExportResponse(iter([b'%PDF']),root=root,media_type='application/pdf')
        with patch.object(exports,'DOWNLOAD_TIMEOUT',.01):
            from starlette.requests import ClientDisconnect
            with pytest.raises((OSError,TimeoutError,ClientDisconnect)):
                await response({'type':'http','asgi':{'spec_version':'2.4'}},receive,send)
    asyncio.run(run());assert not root.exists();assert not exports.gate.locked()


@pytest.mark.parametrize('kind',['image','signature'])
@pytest.mark.parametrize('angle',[-90,-45,45,90])
def test_raster_insert_rotation_direction_and_original_preserved(tmp_path,kind,angle):
    import math
    from PIL import Image
    from pypdf.generic import RectangleObject, NameObject, NumberObject
    fitz=pytest.importorskip('fitz')
    writer=PdfWriter();page=writer.add_blank_page(640,880)
    page.cropbox=RectangleObject([20,40,620,840]);page.rotate(90)
    page[NameObject('/UserUnit')]=NumberObject(2)
    source=tmp_path/'source.pdf';writer.write(source)
    before=source.read_bytes()
    asset_path=tmp_path/'blue.png';Image.new('RGB',(120,60),(81,124,168)).save(asset_path)
    item=object_data(kind,'blue');item['geometry'].update(rotation=angle,rect=dict(x=.4,y=.4625,width=.2,height=.075))
    item['style']['opacity']=1;item['createdAt']='2026-10-20T00:00:00Z'
    output=tmp_path/'rotated.pdf';render(source,[item],{'blue':asset_path},output,1)
    assert source.read_bytes()==before
    assert PdfReader(output).pages[0].rotation==90
    with fitz.open(output) as document:
        page=document[0];page.set_rotation(0);pix=page.get_pixmap(matrix=fitz.Matrix(.5,.5),alpha=False)
        image=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
        # The long-axis tip must move clockwise around the physical box center,
        # including CropBox offset and UserUnit; a missing or opposite rotation fails.
        theta=math.radians(angle);x=300+50*math.cos(theta);y=400+50*math.sin(theta)
        pixel=image.getpixel((round(x*pix.width/600),round(y*pix.height/800)))
        assert max(abs(a-b) for a,b in zip(pixel,(81,124,168)))<5,pixel
        pixel=image.getpixel((round((300+50)*pix.width/600),round(400*pix.height/800)))
        assert min(pixel)>245,pixel
