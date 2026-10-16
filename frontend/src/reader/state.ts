import { reactive } from 'vue'

export type ViewMode = 'continuous' | 'single' | 'spread'
export type ZoomMode = 'custom' | 'fit-width' | 'fit-height'
export interface ReaderTab { id: string; title: string; page: number; mode: ViewMode; scrollTop: number; zoom: number; zoomMode: ZoomMode }
// Only lightweight session state survives a visit to the library. Never store PDF bytes/DOM.
export const readerTabs = reactive<ReaderTab[]>([])
export const annotationListFilters = reactive<Record<string, { type: string; color: string; sort: string }>>({})
export function openReaderTab(id: string, title = '正在读取文献…') {
  let tab = readerTabs.find(item => item.id === id)
  if (!tab) { tab = { id, title, page: 1, mode: 'continuous', scrollTop: 0, zoom: 1, zoomMode: 'fit-width' }; readerTabs.push(tab) }
  return readerTabs.find(item => item.id === id)!
}
export function clearReaderTabs(clearDrafts = false) {
  readerTabs.splice(0)
  for (const id of Object.keys(annotationListFilters)) delete annotationListFilters[id]
  if (clearDrafts) try { for (const key of Object.keys(sessionStorage)) if (key.startsWith('litera:progress:') || key.startsWith('litera:annotations:')) sessionStorage.removeItem(key) } catch { /* Storage may be unavailable. */ }
}
// Reorder existing objects only: no activation, routing or PDF lifecycle side effects.
export function moveReaderTab(id: string, beforeId: string | null) {
  const index = readerTabs.findIndex(tab => tab.id === id)
  if (index < 0 || beforeId === id || (beforeId !== null && !readerTabs.some(tab => tab.id === beforeId))) return
  const order = readerTabs.filter(tab => tab.id !== id)
  const target = beforeId === null ? order.length : order.findIndex(tab => tab.id === beforeId)
  order.splice(target, 0, readerTabs[index]!)
  if (order.some((tab, i) => tab !== readerTabs[i])) readerTabs.splice(0, readerTabs.length, ...order)
}
export function pageGroup(page: number, count: number, mode: ViewMode): number[] {
  if (mode === 'continuous') return Array.from({ length: count }, (_, i) => i + 1)
  const start = mode === 'spread' ? page - (page - 1) % 2 : page
  return mode === 'spread' && start < count ? [start, start + 1] : [start]
}
export function adjacentPage(page: number, count: number, mode: ViewMode, direction: number) {
  const start = mode === 'spread' ? page - (page - 1) % 2 : page
  return Math.max(1, Math.min(count, start + direction * (mode === 'spread' ? 2 : 1)))
}

// The PDF viewport owns crop offsets, intrinsic rotation, UserUnit and CSS scale.
export interface CoordinateViewport {
  viewBox: number[]; width: number; height: number;
  convertToPdfPoint(x: number, y: number): number[];
  convertToViewportPoint(x: number, y: number): number[];
}
export function viewportToNormalized(viewport: CoordinateViewport, x: number, y: number) {
  const [px, py] = viewport.convertToPdfPoint(x, y)
  const [x0, y0, x1, y1] = viewport.viewBox as [number, number, number, number]
  return { x: (px! - x0) / (x1 - x0), y: (y1 - py!) / (y1 - y0) }
}
export function normalizedToViewport(viewport: CoordinateViewport, x: number, y: number) {
  const [x0, y0, x1, y1] = viewport.viewBox as [number, number, number, number]
  return viewport.convertToViewportPoint(x0 + x * (x1 - x0), y1 - y * (y1 - y0))
}
