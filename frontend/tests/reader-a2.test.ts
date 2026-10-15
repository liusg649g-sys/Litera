import { describe, expect, it, vi, afterEach } from 'vitest'
import { findMatches } from '../src/reader/search'
import { clampZoom, fitZoom } from '../src/reader/zoom'
import { publishContext, readerContext, subscribeReaderContext } from '../src/reader/context'
import { createProgress } from '../src/reader/progress'
import { auth } from '../src/auth'
import { mount, flushPromises } from '@vue/test-utils'
import PdfSearch from '../src/components/PdfSearch.vue'
const item = (str: string, hasEOL = false) => ({ str, hasEOL })
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); sessionStorage.clear() })
describe('PDF search and shared context', () => {
  it('rejects a delayed old query after a new query finishes and clears highlights on empty input', async () => {
    vi.useFakeTimers()
    let release!: (page: any) => void
    const old = new Promise(resolve => { release = resolve })
    const page = (str: string) => ({ getTextContent: async () => ({ items: [item(str)] }) })
    const getPage = vi.fn().mockImplementationOnce(() => old).mockResolvedValue(page('new query'))
    const wrapper = mount(PdfSearch, { props: { pdf: { numPages: 1, getPage } as any, selected: '' } })
    await wrapper.get('input').setValue('old'); await vi.advanceTimersByTimeAsync(250)
    expect(wrapper.text()).toContain('搜索中')
    await wrapper.get('input').setValue('new'); await vi.advanceTimersByTimeAsync(300); await flushPromises()
    expect(wrapper.emitted('matches')!.at(-1)![0]).toMatchObject([{ snippet: 'new query' }])
    release(page('old query')); await vi.advanceTimersByTimeAsync(100); await flushPromises()
    expect(wrapper.emitted('matches')!.at(-1)![0]).toMatchObject([{ snippet: 'new query' }])
    await wrapper.get('input').setValue(''); expect(wrapper.emitted('matches')!.at(-1)![0]).toEqual([])
    wrapper.unmount()
  })
  it('matches across items with exact source offsets and Unicode normalization', () => {
    const result = findMatches([item('pre inter'), item('national post')], 'international', false, true, 2)
    expect(result).toHaveLength(1); expect(result[0]!.parts).toEqual([{ item: 0, start: 4, end: 9 }, { item: 1, start: 0, end: 8 }])
    expect(findMatches([item('ﬁeld ＡＢＣ')], 'field abc', false, false, 1)).toHaveLength(1)
    expect(findMatches([item('Word word words')], 'word', true, true, 1)).toHaveLength(1)
    expect(findMatches([item('Word word words')], 'word', false, false, 1)).toHaveLength(3)
    expect(findMatches([item('科研文献 阅读测试')], '科研', false, true, 1)).toHaveLength(1)
    expect(findMatches([item('first', true), item('second')], 'first\nsecond', false, false, 1)).toHaveLength(1)
  })
  it('clamps custom and spread fit to the same 50–500 range', () => {
    expect(clampZoom(.1)).toBe(.5); expect(clampZoom(8)).toBe(5)
    const sizes = [{ width: 600, height: 800 }, { width: 700, height: 900 }]
    expect(fitZoom(sizes, 1336, 924, 'fit-width')).toBe(1)
    expect(fitZoom(sizes, 1336, 924, 'fit-height')).toBe(1)
    expect(fitZoom(sizes, 300, 200, 'fit-width')).toBe(.5)
    expect(fitZoom(sizes, 300, 200, 'fit-height')).toBe(.5)
    expect(fitZoom(sizes, 9000, 9000, 'fit-height')).toBe(5)
  })
  it('publishes monotonic immutable A→B→A snapshots and supports unsubscribe/clear', () => {
    const events: string[] = [], stop = subscribeReaderContext((event) => events.push(event))
    const value = { pageNumber: 1, selectedText: '', selectionPosition: null }
    publishContext('document-change', { documentId: 'a', ...value }); const first = readerContext.value!
    publishContext('document-change', { documentId: 'b', ...value }); publishContext('document-change', { documentId: 'a', ...value })
    expect(readerContext.value!.contextRevision).toBeGreaterThan(first.contextRevision); expect(Object.isFrozen(first)).toBe(true)
    stop(); publishContext('context-cleared'); expect(readerContext.value).toBeNull(); expect(events).toHaveLength(3)
  })
})
const dto = (version: number) => ({ documentId: 'a', pageNumber: 1, zoom: 1, zoomMode: 'custom', viewMode: 'single', lastReadAt: null, version })
const state = { pageNumber: 1, zoom: 1, zoomMode: 'custom' as const, viewMode: 'single' as const }
describe('reader progress queue', () => {
  it('never replays a stored draft before a real target frame succeeds', async () => {
    auth.user = { id: 'u', email: '', displayName: '', createdAt: '' }
    sessionStorage.setItem('litera:progress:u:a', JSON.stringify(state))
    const writes: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (_url, options) => {
      if (options.method === 'PUT') writes.push(JSON.parse(options.body))
      return new Response(JSON.stringify(dto(writes.length)))
    }))
    const queue = createProgress('a'); await queue.load(); await queue.resolve(true); await queue.flush()
    expect(writes).toEqual([]); expect(queue.status.dirty).toBe(true)
    await queue.ready(state); expect(writes).toEqual([])
    await queue.resolve(true); expect(writes).toHaveLength(1); expect(writes[0].recordOpen).toBe(true); queue.dispose()
  })
  it('serializes writes, preserves later edits, and debounces continuous input', async () => {
    vi.useFakeTimers(); const bodies: any[] = []; let release!: () => void
    vi.stubGlobal('fetch', vi.fn(async (_url, options) => {
      if (options.method === 'PUT') { bodies.push(JSON.parse(options.body)); if (bodies.length === 1) await new Promise<void>(r => { release = r }); return new Response(JSON.stringify(dto(bodies.length))) }
      return new Response(JSON.stringify(dto(0)))
    }))
    const queue = createProgress('a'); await queue.load(); const opening = queue.ready(state)
    await vi.waitFor(() => expect(bodies).toHaveLength(1)); queue.stage({ ...state, zoom: 2 }); release(); await opening
    expect(bodies.map(b => b.version)).toEqual([0,1]); expect(bodies[1].zoom).toBe(2)
    for (let i = 0; i < 4; i++) { queue.stage({ ...state, zoom: 2 + i / 10 }); await vi.advanceTimersByTimeAsync(500) }
    expect(bodies).toHaveLength(2); await vi.advanceTimersByTimeAsync(1000); expect(bodies).toHaveLength(3); queue.dispose()
  })
  it('retains drafts on network failure and requires explicit rebase after a conflict', async () => {
    auth.user = { id: 'u', email: '', displayName: '', createdAt: '' }
    let fail = 500, version = 0; const writes: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (_url, options) => {
      if (options.method !== 'PUT') return new Response(JSON.stringify(dto(version)))
      writes.push(JSON.parse(options.body))
      if (fail) return new Response(JSON.stringify({ error: { code: 'FAIL', message: 'failure' } }), { status: fail })
      return new Response(JSON.stringify(dto(++version)))
    }))
    const queue = createProgress('a'); await queue.load(); await queue.ready(state)
    expect(queue.status.dirty).toBe(true); expect(sessionStorage.length).toBe(1)
    fail = 409; version = 4; await queue.retry(); expect(queue.status.conflict).toBe(true)
    const before = writes.length; queue.stage({ ...state, zoom: 2 }); await queue.flush(); expect(writes).toHaveLength(before)
    fail = 0; await queue.resolve(true); expect(writes.at(-1).version).toBe(4); expect(writes.at(-1).zoom).toBe(2)
    expect(queue.status.dirty).toBe(false); expect(sessionStorage.length).toBe(0); queue.dispose()
  })
})
