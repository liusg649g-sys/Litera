import { api, ApiError } from '../api'
import type { DocumentDTO } from '../library'
import { isReaderContextCurrent, type Citation, type ReaderContext, type SelectionPosition } from './context'

export type ReaderLocation = { documentId: string; pageNumber: number; position?: SelectionPosition; annotationId?: string }
export type NavigationResult = { status: 'ok' } | { status: 'unavailable' | 'error'; code: string; message: string }
type Host = (target: ReaderLocation, signal: AbortSignal) => Promise<NavigationResult>
type CitationResolver = (citation: Citation, signal: AbortSignal) => Promise<ReaderLocation | null>
let host: Host | undefined, source: CitationResolver | undefined
export function registerReaderNavigation(value: Host) { host = value; return () => { if (host === value) host = undefined } }
// 05 owns extractionVersion/chunk validation. Until connected, citations are unavailable.
export function registerCitationResolver(value: CitationResolver) { source = value; return () => { if (source === value) source = undefined } }
export async function navigateReader(target: ReaderLocation | Citation, options: { signal?: AbortSignal; context?: Pick<ReaderContext, 'documentId' | 'contextRevision'> } = {}): Promise<NavigationResult> {
  const signal = options.signal || new AbortController().signal
  const invalid = (code: string, message: string): NavigationResult => ({ status: 'error', code, message })
  const stale = () => signal.aborted || (options.context && !isReaderContextCurrent(options.context))
  if (stale()) return invalid('STALE_CONTEXT', '阅读上下文已失效或操作已取消')
  if (!target.documentId || !Number.isInteger(target.pageNumber) || target.pageNumber < 1) return invalid('INVALID_LOCATION', '物理页码必须为正整数')
  try {
    // A context is never permission. Use the existing protected API for every navigation.
    await api<DocumentDTO>(`/documents/${encodeURIComponent(target.documentId)}`, { signal })
    if (stale()) return invalid('STALE_CONTEXT', '阅读上下文已失效或操作已取消')
    let location: ReaderLocation = target
    if ('extractionVersion' in target) {
      if (!source) return { status: 'unavailable', code: 'SOURCE_UNAVAILABLE', message: '引用来源尚未接入，无法验证版本和分块' }
      const resolved = await source(target, signal)
      if (!resolved || resolved.documentId !== target.documentId || resolved.pageNumber !== target.pageNumber) return invalid('SOURCE_VERSION_MISMATCH', '引用来源或版本已失效')
      location = resolved
    }
    if (stale()) return invalid('STALE_CONTEXT', '阅读上下文已失效或操作已取消')
    if (!host) return { status: 'unavailable', code: 'READER_UNAVAILABLE', message: '请先打开阅读工作区' }
    const position = location.position
    if (position && (position.pageNumber !== location.pageNumber || !position.rects.length || position.rects.some(r => ![r.x,r.y,r.width,r.height].every(Number.isFinite) || r.x < 0 || r.y < 0 || r.width <= 0 || r.height <= 0 || r.x+r.width > 1.000001 || r.y+r.height > 1.000001))) return invalid('INVALID_LOCATION', '文本位置超出页面')
    return await host(location, signal)
  } catch (error) {
    if (stale()) return invalid('STALE_CONTEXT', '阅读上下文已失效或操作已取消')
    return invalid(error instanceof ApiError ? error.code : 'NAVIGATION_FAILED', error instanceof Error ? error.message : '导航失败')
  }
}
