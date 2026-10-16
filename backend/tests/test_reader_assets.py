"""B2 real decode, private assets, CAS lifecycle, and failure recovery."""
from io import BytesIO
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import pytest
from PIL import Image
from sqlalchemy import select, text
from app.database import SessionLocal
from app.models import ReaderAsset, Annotation
from app.reader_assets import sweep_assets, now
from app.documents import storage_path
from test_documents import logged, pdf, upload
from test_annotations import command, data


def image(fmt="PNG", size=(120, 60)):
    out=BytesIO();Image.new("RGB",size,"red").save(out,format=fmt);return out.getvalue()

def asset(client,path,fmt="PNG"):
    result=client.post(path+'/reader-assets',files={'file':('a.png',image(fmt),'image/png')})
    assert result.status_code==201,result.text
    return result.json()

def object_data(kind,aid=None):
    value=data('freeText');value.update(type=kind,content='当前页水印' if kind=='watermark' else None,assetId=aid)
    value['geometry']['rect']={'x':.1,'y':.2,'width':.3,'height':.1 if kind in ('signature','image') else .2}
    if kind=='circle':value['geometry']['rect']['height']=.2  # 200x300 page: 60pt circle
    if kind=='ink':value['geometry']={'kind':'points','pageNumber':1,'points':[{'x':.1,'y':.2},{'x':.4,'y':.5}]}
    return value

@pytest.mark.parametrize('kind',['ink','rectangle','circle','ellipse','signature','watermark','image'])
def test_all_new_types_real_crud_restore_cas(logged,pdf,kind):
    doc=upload(logged,pdf).json();path='/api/v1/documents/'+doc['id']
    a=asset(logged,path) if kind in ('signature','image') else None
    value=object_data(kind,a['assetId'] if a else None)
    if kind=='watermark':value['geometry']['rotation']=-35
    body=command(annotation=value)
    created=logged.post(path+'/annotations',json=body)
    assert created.status_code==201,created.text
    assert logged.post(path+'/annotations',json=body).json()==created.json()
    item=created.json()['annotation']
    assert logged.get(path+'/annotations').json()['items']==[item]
    patch_body=command(1,version=1,changes={'style':{'opacity':.7},'color':'#9B0000'})
    changed=logged.patch(path+'/annotations/'+item['id'],json=patch_body)
    assert changed.status_code==200,changed.text
    saved=changed.json()['annotation']
    assert logged.patch(path+'/annotations/'+item['id'],json=command(1,version=1,changes={'content':'other'})).status_code==409
    assert logged.request('DELETE',path+'/annotations/'+item['id'],json=command(2,version=2)).status_code==200
    if a:
        with SessionLocal() as db: assert db.get(ReaderAsset,a['assetId']).expires_at>now()+timedelta(hours=23)
    restored=logged.post(path+'/annotation-commands',json=command(3,operation='restore',annotation=saved))
    assert restored.status_code==200,restored.text
    assert restored.json()['annotation']['id']==item['id']
    assert logged.get(path+'/content').content==pdf

@pytest.mark.parametrize('fmt',['PNG','JPEG'])
def test_raster_decode_security_and_cancel(logged,pdf,fmt):
    path='/api/v1/documents/'+upload(logged,pdf).json()['id'];a=asset(logged,path,fmt)
    response=logged.get(path+'/reader-assets/'+a['assetId']+'/content')
    assert response.status_code==200
    import hashlib
    with SessionLocal() as db:assert db.get(ReaderAsset,a['assetId']).sha256==hashlib.sha256(response.content).hexdigest()
    assert response.headers['x-content-type-options']=='nosniff'
    with Image.open(BytesIO(response.content)) as decoded: decoded.load();assert decoded.size==(120,60)
    other='/api/v1/documents/'+upload(logged,pdf+b'\n%other').json()['id']
    assert logged.get(other+'/reader-assets/'+a['assetId']+'/content').status_code==404
    value=object_data('image',a['assetId'])
    assert logged.post(other+'/annotations',json=command(annotation=value)).status_code==404
    aid=a['assetId']
    assert logged.delete(path+'/reader-assets/'+aid).status_code==204
    assert logged.delete(path+'/reader-assets/'+aid).status_code==204
    assert logged.get(path+'/reader-assets/'+aid+'/content').status_code==422

@pytest.mark.parametrize('raw,status',[(b'not an image',415),(b'<svg></svg>',415),(b'x'*(5*1024*1024+1),413)],ids=['garbage','svg','oversize'])
def test_invalid_upload_leaves_no_asset(logged,pdf,raw,status):
    path='/api/v1/documents/'+upload(logged,pdf).json()['id']
    result=logged.post(path+'/reader-assets',files={'file':('image.png',raw,'image/png')})
    assert result.status_code==status,result.text
    assert logged.get(path+'/reader-assets').json()['items']==[]


def test_real_pixel_and_broken_decode_validation(logged,pdf):
    path='/api/v1/documents/'+upload(logged,pdf).json()['id']
    for raw,expected in [(image(size=(5000,4001)),422),(image('JPEG')[:-30],415),(image('PNG')[:-20],415)]:
        result=logged.post(path+'/reader-assets',files={'file':('a.png',raw,'image/png')})
        assert result.status_code==expected,result.text


def test_cleanup_failure_retry_and_lifecycle(logged,pdf):
    id=upload(logged,pdf).json()['id'];path='/api/v1/documents/'+id;a=asset(logged,path)
    with SessionLocal() as db:key=db.get(ReaderAsset,a['assetId']).storage_key
    actual=Path.unlink
    def fail(p,*args,**kw):
        if p.name==key:raise PermissionError('injected')
        return actual(p,*args,**kw)
    with patch.object(Path,'unlink',fail):
        result=logged.delete(path+'/reader-assets/'+a['assetId']);assert result.status_code==202
        assert result.json()['status']=='failed'
    assert logged.get(path+'/reader-assets').json()['items'][0]['attempts']==1
    assert logged.delete(path+'/reader-assets/'+a['assetId']).status_code==204
    b=asset(logged,path)
    item=logged.post(path+'/annotations',json=command(annotation=object_data('signature',b['assetId']))).json()['annotation']
    assert logged.delete(path+'/reader-assets/'+b['assetId']).status_code==409
    assert logged.delete(path).status_code==204
    assert logged.get(path+'/reader-assets/'+b['assetId']+'/content').status_code==404
    assert logged.post('/api/v1/trash/documents/'+id+'/restore').status_code==200
    assert logged.get(path+'/annotations').json()['items'][0]['id']==item['id']
    logged.delete(path)
    with patch.object(Path,'unlink',side_effect=PermissionError('injected')):
        result=logged.delete('/api/v1/trash/documents/'+id);assert result.status_code==202
    job=result.json()['jobId']
    assert logged.post('/api/v1/cleanup-jobs/'+job+'/retry').status_code==204
    with SessionLocal() as db:assert not db.scalar(select(ReaderAsset).where(ReaderAsset.document_id==id))


def test_startup_sweep_leases_and_expired_restore(logged,pdf):
    id=upload(logged,pdf).json()['id'];path='/api/v1/documents/'+id
    a=asset(logged,path);b=asset(logged,path)
    item=logged.post(path+'/annotations',json=command(annotation=object_data('image',b['assetId']))).json()['annotation']
    with SessionLocal() as db:
        db.get(ReaderAsset,a['assetId']).expires_at=now()-timedelta(seconds=1)
        db.get(ReaderAsset,b['assetId']).expires_at=now()-timedelta(seconds=1);db.commit()
    sweep_assets()
    with SessionLocal() as db:
        assert db.get(ReaderAsset,a['assetId']).status=='deleted'
        assert db.get(ReaderAsset,b['assetId']).expires_at is None
    logged.request('DELETE',path+'/annotations/'+item['id'],json=command(1,version=1))
    with SessionLocal() as db:db.get(ReaderAsset,b['assetId']).expires_at=now()-timedelta(seconds=1);db.commit()
    sweep_assets()
    assert logged.post(path+'/annotation-commands',json=command(2,operation='restore',annotation=item)).status_code==422
    assert logged.get(path+'/annotations').json()['annotationRevision']==2

@pytest.mark.parametrize('value',[{'type':'circle','width':.4},{'type':'rectangle','rotation':30},{'type':'ink','points':10001},{'type':'ink','points':1}])
def test_invalid_geometry_is_atomic(logged,pdf,value):
    path='/api/v1/documents/'+upload(logged,pdf).json()['id'];obj=object_data(value['type'])
    if 'width' in value:obj['geometry']['rect']['width']=value['width']
    if 'rotation' in value:obj['geometry']['rotation']=value['rotation']
    if 'points' in value:obj['geometry']['points']=[{'x':.2,'y':.3}]*value['points']
    result=logged.post(path+'/annotations',json=command(annotation=obj));assert result.status_code==422,result.text
    assert logged.get(path+'/annotations').json()==dict(items=[],annotationRevision=0)


def test_asset_mysql_ddl_additive_only(monkeypatch,capsys):
    from alembic import command as ac
    from alembic.config import Config
    from app.config import get_settings
    monkeypatch.setattr(get_settings(),'database_url','mysql+pymysql://test:unused@127.0.0.1/litera_test')
    ac.upgrade(Config('alembic.ini'),'0005_annotations:0006_reader_assets',sql=True)
    ddl=capsys.readouterr().out
    assert 'CREATE TABLE reader_assets' in ddl and 'DROP TABLE' not in ddl and 'ALTER TABLE documents' not in ddl


def test_assets_auth_csrf_owner_quota_and_replacement(logged,pdf):
    from fastapi.testclient import TestClient
    from app.main import app
    from test_auth import register,login
    path='/api/v1/documents/'+upload(logged,pdf).json()['id'];a=asset(logged,path)
    with TestClient(app,headers={'Origin':'http://localhost:8080'}) as other:
        assert other.get(path+'/reader-assets/'+a['assetId']+'/content').status_code==401
        register(other,'b2-other@example.com');login(other,'b2-other@example.com')
        assert other.get(path+'/reader-assets').status_code==404
        assert other.get(path+'/reader-assets/'+a['assetId']+'/content').status_code==404
        assert other.post(path+'/reader-assets',files={'file':('a.png',image(),'image/png')}).status_code==403
    with patch('app.reader_assets.MAX_DOCUMENT_BYTES',a['sizeBytes']):
        assert logged.post(path+'/reader-assets',files={'file':('a.png',image(),'image/png')}).status_code==413
    b=asset(logged,path)
    obj=object_data('image',a['assetId']);created=logged.post(path+'/annotations',json=command(annotation=obj)).json()['annotation']
    changed=logged.patch(path+'/annotations/'+created['id'],json=command(1,version=1,changes={'assetId':b['assetId']}))
    assert changed.status_code==200,changed.text
    with SessionLocal() as db:
        assert db.get(ReaderAsset,a['assetId']).expires_at>now()+timedelta(hours=23)
        assert db.get(ReaderAsset,b['assetId']).expires_at is None


def test_upload_disk_failure_is_registered_and_swept(logged,pdf):
    path='/api/v1/documents/'+upload(logged,pdf).json()['id']
    original=Path.open
    def fail(p,*args,**kwargs):
        if p.name.startswith('asset-') and args and args[0]=='xb': raise OSError('injected')
        return original(p,*args,**kwargs)
    with patch.object(Path,'open',fail):
        assert logged.post(path+'/reader-assets',files={'file':('a.png',image(),'image/png')}).status_code==500
    pending=logged.get(path+'/reader-assets').json()['items'];assert len(pending)==1 and pending[0]['status']=='uploading'
    with SessionLocal() as db:
        db.get(ReaderAsset,pending[0]['assetId']).expires_at=now()-timedelta(seconds=1);db.commit()
    sweep_assets()
    assert logged.get(path+'/reader-assets').json()['items']==[]


def test_asset_stream_envelope_reports_its_actual_limit(logged,pdf):
    path='/api/v1/documents/'+upload(logged,pdf).json()['id']
    response=logged.post(path+'/reader-assets',files={'file':('large.png',b'x'*(5*1024*1024+100000),'image/png')})
    assert response.status_code==413,response.text
    assert response.json()['error']['details']['maxUploadBytes']==5*1024*1024
    assert logged.get(path+'/reader-assets').json()['items']==[]


def test_cleanup_between_ledger_and_file_cannot_resurrect_upload(logged,pdf):
    from app import reader_assets
    path='/api/v1/documents/'+upload(logged,pdf).json()['id']
    original=reader_assets.lock_document;calls=0
    def cleanup_before_write(db,owner,id):
        nonlocal calls
        calls+=1
        if calls==2:
            with SessionLocal() as other:
                row=other.scalar(select(ReaderAsset).where(ReaderAsset.document_id==id));row.status='deleted';other.commit()
        return original(db,owner,id)
    with patch.object(reader_assets,'lock_document',cleanup_before_write):
        result=logged.post(path+'/reader-assets',files={'file':('a.png',image(),'image/png')})
    assert result.status_code==409,result.text
    assert result.json()['error']['code']=='ASSET_UPLOAD_CANCELED'
    with SessionLocal() as db:
        row=db.scalar(select(ReaderAsset));assert row.status=='deleted'
        assert not reader_assets.asset_storage_path(row.storage_key).exists()
