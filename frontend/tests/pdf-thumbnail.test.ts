import { afterEach, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PdfThumbnail from '../src/components/PdfThumbnail.vue'

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

it('renders CSS size at capped DPR, reuses unchanged output and cancels/releases obsolete work', async () => {
  let intersect!: (entries: any[]) => void, resize!: () => void, change!: () => void
  vi.stubGlobal('IntersectionObserver', class { constructor(fn: typeof intersect) { intersect = fn } observe() {} disconnect() {} })
  vi.stubGlobal('ResizeObserver', class { constructor(fn: typeof resize) { resize = fn } observe() {} disconnect() {} })
  vi.stubGlobal('matchMedia', () => ({ addEventListener: (_: string, fn: () => void) => { change = fn }, removeEventListener: vi.fn() }))
  vi.stubGlobal('devicePixelRatio', 1)
  let width = 128
  vi.spyOn(HTMLCanvasElement.prototype, 'getBoundingClientRect').mockImplementation(() => ({ width } as DOMRect))
  const drawImage = vi.fn()
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage } as any)
  let finish!: () => void
  const cancel = vi.fn(() => finish())
  const render = vi.fn((_options: any) => ({ promise: new Promise<void>(resolve => { finish = resolve }), cancel }))
  const page = { getViewport: ({ scale }: { scale: number }) => ({ width: 600 * scale, height: 800 * scale }), render }
  const wrapper = mount(PdfThumbnail, { props: { pdf: { getPage: vi.fn().mockResolvedValue(page) } as any, pageNumber: 1, current: 1 } })
  intersect([{ isIntersecting: true }]); await flushPromises()
  expect(render).toHaveBeenCalledTimes(1)
  expect(render.mock.calls[0]![0]).toMatchObject({ transform: [1, 0, 0, 1, 0, 0] })
  resize(); intersect([{ isIntersecting: true }]); expect(render).toHaveBeenCalledTimes(1)
  finish(); await flushPromises(); resize(); expect(drawImage).toHaveBeenCalledTimes(1)
  vi.stubGlobal('devicePixelRatio', 2); change(); await flushPromises()
  expect(render).toHaveBeenCalledTimes(2)
  expect(render.mock.calls[1]![0]).toMatchObject({ canvas: { width: 256, height: 342 }, transform: [2, 0, 0, 2, 0, 0] })
  vi.stubGlobal('devicePixelRatio', 3); change(); expect(render).toHaveBeenCalledTimes(2)
  width = 100; resize(); await flushPromises()
  expect(cancel).toHaveBeenCalledTimes(1)
  expect(render).toHaveBeenCalledTimes(3)
  expect(drawImage).toHaveBeenCalledTimes(1) // cancelled DPR2 frame never commits
  intersect([{ isIntersecting: false }]); await flushPromises()
  expect((wrapper.get('canvas').element as HTMLCanvasElement).width).toBe(0)
  intersect([{ isIntersecting: true }]); await flushPromises(); wrapper.unmount(); await flushPromises()
  expect(cancel).toHaveBeenCalledTimes(3)
  expect(drawImage).toHaveBeenCalledTimes(1)
})
