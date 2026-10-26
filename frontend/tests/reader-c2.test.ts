import { afterEach, expect, it, vi } from 'vitest'
import { publishContext, readerContext, isReaderContextCurrent, subscribeReaderContext } from '../src/reader/context'
import { navigateReader, registerReaderNavigation, registerReaderSourceReset, registerCitationResolver } from '../src/reader/navigation'
afterEach(() => { vi.unstubAllGlobals(); publishContext('context-cleared') })
const value = { documentId: 'a', pageNumber: 2, selectedText: '', selectionPosition: null, annotationId: 'ann' }
it('cancels subscriptions and rejects old A responses after A→B→A; keeps annotation and physical page', () => {
  const controller = new AbortController(), callback = vi.fn()
  subscribeReaderContext(callback, controller.signal)
  publishContext('document-change', value); const first = readerContext.value!
  publishContext('document-change', { ...value, documentId: 'b' }); publishContext('document-change', value)
  expect(isReaderContextCurrent(first)).toBe(false); expect(isReaderContextCurrent(readerContext.value!)).toBe(true)
  expect(readerContext.value).toMatchObject({ pageNumber: 2, annotationId: 'ann' })
  controller.abort(); publishContext('page-change', { ...value, pageNumber: 3 }); expect(callback).toHaveBeenCalledTimes(3)
  const aborted = new AbortController(); aborted.abort(); const never = vi.fn(); subscribeReaderContext(never, aborted.signal); publishContext('context-cleared'); expect(never).not.toHaveBeenCalled()
})
it('requires real permission, source validation, and a connected reader; rejects malformed coordinates', async () => {
  const fetcher = vi.fn(async () => new Response(JSON.stringify({ id: 'a' })))
  vi.stubGlobal('fetch', fetcher)
  expect(await navigateReader({ documentId:'a', pageNumber:1 })).toMatchObject({ status:'unavailable', code:'READER_UNAVAILABLE' })
  const handler = vi.fn(async () => ({ status:'ok' as const })), stop = registerReaderNavigation(handler)
  const citation = { documentId:'a', pageNumber:1, extractionVersion:'v1', chunkId:'c1', quote:'real text' }
  try {
    expect(await navigateReader(citation)).toMatchObject({ status:'unavailable', code:'SOURCE_UNAVAILABLE' })
    const unbind = registerCitationResolver(async () => null)
    expect(await navigateReader(citation)).toMatchObject({ code:'SOURCE_VERSION_MISMATCH' }); unbind()
    expect(await navigateReader({ documentId:'a', pageNumber:1, position:{pageNumber:1,textQuote:'x',rects:[{x:.9,y:0,width:.2,height:.1}]} })).toMatchObject({ code:'INVALID_LOCATION' })
    expect(await navigateReader({ documentId:'a', pageNumber:1 })).toEqual({ status:'ok' }); expect(handler).toHaveBeenCalledTimes(1)
    fetcher.mockImplementation(async () => new Response(JSON.stringify({ error:{ code:'DOCUMENT_NOT_FOUND', message:'不可访问' } }), {status:404}))
    expect(await navigateReader(citation)).toMatchObject({ status:'error', code:'DOCUMENT_NOT_FOUND' }); expect(handler).toHaveBeenCalledTimes(1)
  } finally { stop() }
})
it('rechecks context after asynchronous permission lookup and never forwards a stale result', async () => {
  let release!: () => void
  vi.stubGlobal('fetch', vi.fn(async () => { await new Promise<void>(resolve => { release = resolve }); return new Response('{}') }))
  publishContext('document-change', value); const snapshot = readerContext.value!
  const handler = vi.fn(async () => ({ status:'ok' as const })), stop = registerReaderNavigation(handler)
  const operation = navigateReader({documentId:'a',pageNumber:2}, {context:snapshot})
  publishContext('document-change', {...value,documentId:'b'}); publishContext('document-change', value); release()
  expect(await operation).toMatchObject({code:'STALE_CONTEXT'}); expect(handler).not.toHaveBeenCalled(); stop()
})

it('validates the saved PDF digest and known page count before invoking the reader host',async()=>{
 const digest='a'.repeat(64),fetcher=vi.fn(async()=>new Response(JSON.stringify({id:'a',pageCount:3,attachment:{sha256:digest}})))
 vi.stubGlobal('fetch',fetcher)
 const handler=vi.fn(async()=>({status:'ok' as const})),stop=registerReaderNavigation(handler)
 try{
  expect(await navigateReader({documentId:'a',pageNumber:2,fileSha256:digest})).toEqual({status:'ok'})
  expect(handler).toHaveBeenLastCalledWith({documentId:'a',pageNumber:2,fileSha256:digest},expect.any(AbortSignal))
  expect(await navigateReader({documentId:'a',pageNumber:2,fileSha256:'b'.repeat(64)})).toMatchObject({code:'SOURCE_VERSION_MISMATCH',message:expect.stringContaining('无法可靠定位来源')})
  expect(await navigateReader({documentId:'a',pageNumber:4,fileSha256:digest})).toMatchObject({code:'INVALID_PAGE',message:expect.stringContaining('无法可靠定位来源')})
  expect(await navigateReader({documentId:'a',pageNumber:1,fileSha256:''})).toMatchObject({code:'INVALID_SOURCE'})
  expect(handler).toHaveBeenCalledTimes(1)
 }finally{stop()}
})
it('clears a previous temporary source highlight before validating a new source request',async()=>{
 const digest='a'.repeat(64),reset=vi.fn(),stopReset=registerReaderSourceReset(reset)
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({id:'a',pageCount:3,attachment:{sha256:digest}}))))
 const stop=registerReaderNavigation(async()=>({status:'ok',precision:'page'}))
 try{
  await navigateReader({documentId:'a',pageNumber:2,fileSha256:digest})
  expect(reset).toHaveBeenCalledTimes(1)
  await navigateReader({documentId:'a',pageNumber:0,fileSha256:digest})
  expect(reset).toHaveBeenCalledTimes(2)
 }finally{stop();stopReset()}
})
