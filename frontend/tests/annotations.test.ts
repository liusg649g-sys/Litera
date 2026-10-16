import { afterEach, describe, expect, it, vi } from 'vitest'
import { createAnnotations } from '../src/reader/annotations'
import type { AnnotationDTO } from '../src/reader/annotations'
import { auth } from '../src/auth'

const original: AnnotationDTO = { id:'annotation', documentId:'doc', type:'comment', schemaVersion:1, pageNumber:1, position:null, geometry:{kind:'anchor',pageNumber:1,x:.2,y:.3}, content:'草稿', selectedText:null, color:'#F5D547', style:{opacity:1,fontSize:14,lineWidth:1}, zIndex:0, assetId:null, version:0, createdAt:'2026-10-15T00:00:00Z', updatedAt:'2026-10-15T00:00:00Z' }
function backend() {
  let revision=0, items:AnnotationDTO[]=[], lost=false, conflict=false, writes=0, active=0, maxActive=0
  const receipts = new Map<string, any>(), deleted = new Map<string, AnnotationDTO>()
  vi.stubGlobal('fetch', vi.fn(async (url:string,options:any={}) => {
    const path=String(url), body=options.body ? JSON.parse(options.body) : null
    const result=(data:any,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}})
    if (!body && path.endsWith('/annotations')) return result({items:JSON.parse(JSON.stringify(items)),annotationRevision:revision})
    if (!body) return receipts.has(path.split('/').pop()!) ? result(receipts.get(path.split('/').pop()!)) : result({error:{code:'COMMAND_NOT_FOUND'}},404)
    writes++; active++; maxActive=Math.max(maxActive,active); await Promise.resolve(); active--
    if (conflict || body.baseRevision!==revision) return result({error:{code:'ANNOTATION_CONFLICT'}},409)
    let annotation:AnnotationDTO|null=null
    const id=body.annotation?.id || path.split('/').pop(), existing=items.find(a=>a.id===id)
    if(options.method==='DELETE') { deleted.set(id,existing!); items=items.filter(a=>a.id!==id) }
    else {
      annotation=options.method==='PATCH' ? {...existing,...body.changes,version:existing!.version+1} : {...body.annotation,documentId:'doc',version:(deleted.get(id)?.version || 0)+(body.operation==='restore'?2:1),createdAt:original.createdAt,updatedAt:original.updatedAt}
      items=items.filter(a=>a.id!==id);items.push(annotation!)
    }
    const value={commandId:body.commandId,annotationRevision:++revision,annotation};receipts.set(body.commandId,value)
    if(lost){lost=false;throw new Error('response lost after commit')}
    return result(value)
  }))
  return {get items(){return items},get writes(){return writes},get revision(){return revision},get maxActive(){return maxActive},loseNext(){lost=true},conflict(){conflict=true}}
}
afterEach(()=>{vi.unstubAllGlobals();vi.useRealTimers();sessionStorage.clear()})
describe('annotation command queue',()=>{
  it('serializes create/edit/delete and persisted undo/redo compensation',async()=>{
    const db=backend(), manager=createAnnotations('doc');await manager.load()
    manager.create(original);manager.edit(original.id,{content:'第二版'});await manager.flush()
    expect(db.items[0]!.content).toBe('第二版');expect(db.maxActive).toBe(1)
    await manager.undo();expect(db.items[0]!.content).toBe('草稿')
    await manager.redo();expect(db.items[0]!.content).toBe('第二版')
    manager.remove(original.id);await manager.flush();expect(db.items).toEqual([])
    await manager.undo();expect(db.items[0]!.content).toBe('第二版')
    await manager.redo();expect(db.items).toEqual([]);expect(manager.state.dirty).toBe(false);manager.dispose()
  })
  it('undo while a creation is not sent confirms it then persists inverse',async()=>{
    const db=backend(), manager=createAnnotations('doc');await manager.load();manager.create(original)
    expect(manager.state.phase).toBe('draft');await manager.undo()
    expect(db.revision).toBe(2);expect(db.items).toEqual([]);expect(manager.state.redoCount).toBe(1)
    await manager.redo();expect(db.items).toHaveLength(1);manager.dispose()
  })
  it('reconciles a lost response through receipt without duplicate creation',async()=>{
    const db=backend(), manager=createAnnotations('doc');await manager.load();db.loseNext();manager.create(original);await manager.flush()
    expect(manager.state.phase).toBe('failed');expect(db.items).toHaveLength(1);expect(manager.state.dirty).toBe(true)
    await manager.retry();expect(manager.state.phase).toBe('confirmed');expect(db.writes).toBe(1);expect(manager.state.dirty).toBe(false);manager.dispose()
  })
  it('restores an unresolved command after refresh and confirms receipt',async()=>{
    const db=backend(), first=createAnnotations('doc');await first.load();db.loseNext();first.create(original);await first.flush();first.dispose()
    const next=createAnnotations('doc');await next.load();expect(next.state.error).toContain('草稿');await next.retry()
    expect(db.writes).toBe(1);expect(next.state.items).toHaveLength(1);expect(next.state.dirty).toBe(false);next.dispose()
  })
  it('stops dependent writes on 409, keeps draft and only resets on explicit server choice',async()=>{
    const db=backend(), manager=createAnnotations('doc');await manager.load();db.conflict();manager.create(original);manager.edit(original.id,{content:'不可丢失'});await manager.flush()
    expect(manager.state.phase).toBe('conflict');expect(db.writes).toBe(1);expect(manager.state.items[0]!.content).toBe('不可丢失')
    await manager.retry();expect(db.writes).toBe(1)
    await manager.reloadServer();expect(manager.state.items).toEqual([]);expect(Object.keys(sessionStorage).some(k=>k.includes(':backup:'))).toBe(true);manager.dispose()
  })
  it('keeps queues and draft keys separate from reading progress and another document',async()=>{
    backend();sessionStorage.setItem('litera:progress:undefined:doc','existing')
    const a=createAnnotations('doc'), b=createAnnotations('other');await a.load();await b.load();a.create(original)
    expect(a.state.dirty).toBe(true);expect(b.state.items).toEqual([]);expect(sessionStorage.getItem('litera:progress:undefined:doc')).toBe('existing');a.dispose();b.dispose()
  })
  it('does not execute a corrupted draft URL and preserves the original for recovery',async()=>{
    const db=backend(),key=`litera:annotations:${auth.user?.id}:doc`,raw=JSON.stringify({queue:[{id:'annotation',desired:original,prepared:{path:'/documents/doc',method:'DELETE',body:{commandId:'danger',baseRevision:0},at:Date.now()}}]})
    sessionStorage.setItem(key,raw);const manager=createAnnotations('doc');await manager.load();await manager.retry()
    expect(db.writes).toBe(0);expect(manager.state.dirty).toBe(true);expect(sessionStorage.getItem(key)).toBe(raw)
    await manager.reloadServer();expect(Object.keys(sessionStorage).some(k=>k.includes(':backup:'))).toBe(true);manager.dispose()
  })
  it('does not recreate private drafts after logout during an in-flight command',async()=>{
    backend();const manager=createAnnotations('doc');await manager.load();manager.create(original);const flight=manager.flush();manager.dispose(true);await flight
    expect(Object.keys(sessionStorage).some(k=>k.startsWith('litera:annotations:'))).toBe(false)
  })
})


describe('B2 asset recovery command safety',()=>{
  it('replaces only a definitively rejected asset using a fresh command and preserves undo',async()=>{
    const db=backend(),fetcher=globalThis.fetch;let rejectAsset=true
    vi.stubGlobal('fetch',vi.fn(async(url:any,options:any={})=>{
      if(options.method==='POST' && String(url).endsWith('/annotations') && rejectAsset)return new Response(JSON.stringify({error:{code:'ASSET_UNAVAILABLE',message:'图片已失效'}}),{status:422})
      return fetcher(url,options)
    }))
    const manager=createAnnotations('doc');await manager.load()
    const geometry={kind:'box' as const,pageNumber:1,rotation:0,rect:{x:.1,y:.2,width:.3,height:.2}}
    manager.create({...original,type:'image',assetId:'expired',geometry});await manager.flush()
    expect(manager.state.phase).toBe('failed');expect(manager.state.failureCode).toBe('ASSET_UNAVAILABLE')
    expect(manager.replaceFailedAsset('annotation','new-asset',geometry)).toBe(true)
    rejectAsset=false;await manager.retry();expect(db.items[0]!.assetId).toBe('new-asset');expect(manager.state.dirty).toBe(false)
    await manager.undo();expect(db.items).toHaveLength(0);await manager.redo();expect(db.items[0]!.assetId).toBe('new-asset');manager.dispose()
  })
  it('does not rewrite an unknown command outcome or conflict',async()=>{
    const db=backend(),manager=createAnnotations('doc');await manager.load();db.loseNext();manager.create(original);await manager.flush()
    expect(manager.replaceFailedAsset(original.id,'other',{kind:'box',pageNumber:1,rotation:0,rect:{x:.1,y:.2,width:.2,height:.2}})).toBe(false)
    await manager.retry();expect(db.items).toHaveLength(1);manager.dispose()
  })
})
