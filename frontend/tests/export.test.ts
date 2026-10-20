import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { exportAnnotatedPdf } from '../src/reader/export'

const click=vi.fn(), revoke=vi.fn(),create=vi.fn(()=> 'blob:export')
beforeEach(()=>{
  vi.useFakeTimers();vi.stubGlobal('fetch',vi.fn())
  vi.spyOn(document,'createElement').mockReturnValue({click} as unknown as HTMLAnchorElement)
  vi.stubGlobal('URL',{createObjectURL:create,revokeObjectURL:revoke})
})
afterEach(()=>{vi.useRealTimers();vi.restoreAllMocks();vi.unstubAllGlobals();vi.clearAllMocks()})
describe('annotated PDF transfer',()=>{
  it('posts saved CAS revision with CSRF, downloads PDF and releases object URL',async()=>{
    vi.mocked(fetch).mockResolvedValue(new Response(new Blob(['%PDF']),{headers:{'Content-Type':'application/pdf','Content-Disposition':"attachment; filename*=UTF-8''%E8%AE%BA%E6%96%87.pdf"}}))
    await exportAnnotatedPdf('a/b',7,'csrf',new AbortController().signal)
    expect(fetch).toHaveBeenCalledWith('/api/v1/documents/a%2Fb/annotated-pdf',expect.objectContaining({method:'POST',body:'{"expectedAnnotationRevision":7}',headers:expect.objectContaining({'X-CSRF-Token':'csrf'})}))
    expect(click).toHaveBeenCalledOnce();await vi.advanceTimersByTimeAsync(1000);expect(revoke).toHaveBeenCalledWith('blob:export')
  })
  it('reports revision conflict without downloading',async()=>{
    vi.mocked(fetch).mockResolvedValue(Response.json({error:{code:'ANNOTATION_REVISION_CONFLICT',message:'版本变化'}},{status:409}))
    await expect(exportAnnotatedPdf('a',1,'x',new AbortController().signal)).rejects.toMatchObject({code:'ANNOTATION_REVISION_CONFLICT',message:'版本变化'})
    expect(click).not.toHaveBeenCalled()
  })
  it('invalidates authentication and never downloads error bytes',async()=>{
    const event=vi.fn();window.addEventListener('litera:unauthenticated',event)
    vi.mocked(fetch).mockResolvedValue(Response.json({}, {status:401}))
    await expect(exportAnnotatedPdf('a',1,'x',new AbortController().signal)).rejects.toMatchObject({status:401})
    expect(event).toHaveBeenCalledOnce();expect(click).not.toHaveBeenCalled();window.removeEventListener('litera:unauthenticated',event)
  })
  it('cancellation after receiving bytes prevents a stale document download',async()=>{
    const controller=new AbortController();controller.abort()
    vi.mocked(fetch).mockResolvedValue(new Response('%PDF',{headers:{'Content-Type':'application/pdf'}}))
    await expect(exportAnnotatedPdf('a',1,'x',controller.signal)).rejects.toMatchObject({name:'AbortError'})
    expect(click).not.toHaveBeenCalled()
  })
})
