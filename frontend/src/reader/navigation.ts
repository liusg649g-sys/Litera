import { api, ApiError } from '../api'
import type { DocumentDTO } from '../library'
import { isReaderContextCurrent, type Citation, type ReaderContext, type SelectionPosition } from './context'

export type ReaderLocation = { documentId: string; pageNumber: number; fileSha256?: string; position?: SelectionPosition; annotationId?: string }
export type NavigationResult = { status: 'ok'; precision?: 'page' | 'exact'; message?: string } | { status: 'unavailable' | 'error'; code: string; message: string }
type Host = (target: ReaderLocation, signal: AbortSignal) => Promise<NavigationResult>
type CitationResolver = (citation: Citation, signal: AbortSignal) => Promise<ReaderLocation | null>
type SourceReset = () => void
let host: Host | undefined, source: CitationResolver | undefined, sourceReset: SourceReset | undefined
export function registerReaderNavigation(value: Host) { host = value; return () => { if (host === value) host = undefined } }
export function registerReaderSourceReset(value: SourceReset) { sourceReset = value; return () => { if (sourceReset === value) sourceReset = undefined } }
// 05 owns extractionVersion/chunk validation. Until connected, citations are unavailable.
export function registerCitationResolver(value: CitationResolver) { source = value; return () => { if (source === value) source = undefined } }
export async function navigateReader(target: ReaderLocation | Citation, options: { signal?: AbortSignal; context?: Pick<ReaderContext, 'documentId' | 'contextRevision'> } = {}): Promise<NavigationResult> {
  const signal = options.signal || new AbortController().signal
  const sourceNavigation = 'fileSha256' in target
  const invalid = (code: string, message: string): NavigationResult => ({ status: 'error', code, message })
  const sourceError = (message: string) => message.startsWith('无法可靠定位来源') ? message : '无法可靠定位来源：' + message
  const stale = () => signal.aborted || (options.context && !isReaderContextCurrent(options.context))
  if (stale()) return invalid('STALE_CONTEXT', '阅读上下文已失效或操作已取消')
  if (sourceNavigation) sourceReset?.()
  if (!target.documentId || !Number.isInteger(target.pageNumber) || target.pageNumber < 1) return invalid('INVALID_LOCATION', sourceNavigation ? sourceError('来源文献标识或物理页码无效。') : '物理页码必须为正整数')
  if (sourceNavigation && !/^[a-f0-9]{64}$/i.test(target.fileSha256 || '')) return invalid('INVALID_SOURCE', sourceError('来源记录缺少有效的 PDF 版本信息。'))
  try {
    // A context is never permission. Use the existing protected API for every navigation.
    const document = await api<DocumentDTO>(`/documents/${encodeURIComponent(target.documentId)}`, { signal })
    if (stale()) return invalid('STALE_CONTEXT', '阅读上下文已失效或操作已取消')
    if (sourceNavigation && document.attachment.sha256.toLowerCase() !== target.fileSha256!.toLowerCase()) return invalid('SOURCE_VERSION_MISMATCH', sourceError('来源 PDF 与保存时版本不一致。'))
    if (document.pageCount !== null && target.pageNumber > document.pageCount) return invalid('INVALID_PAGE', sourceNavigation ? sourceError('来源页码超出当前 PDF 范围。') : '物理页码超出文献范围')
    let location: ReaderLocation = target
    if ('extractionVersion' in target) {
      if (!source) return { status: 'unavailable', code: 'SOURCE_UNAVAILABLE', message: '引用来源尚未接入，无法验证版本和分块' }
      const resolved = await source(target, signal)
      if (!resolved || resolved.documentId !== target.documentId || resolved.pageNumber !== target.pageNumber) return invalid('SOURCE_VERSION_MISMATCH', '引用来源或版本已失效')
      location = resolved
    }
    if (stale()) return invalid('STALE_CONTEXT', '阅读上下文已失效或操作已取消')
    if (!host) return { status: 'unavailable', code: 'READER_UNAVAILABLE', message: sourceNavigation ? sourceError('请先打开阅读工作区。') : '请先打开阅读工作区' }
    const position = location.position
    if (position && (position.pageNumber !== location.pageNumber || !position.rects.length || position.rects.some(r => ![r.x,r.y,r.width,r.height].every(Number.isFinite) || r.x < 0 || r.y < 0 || r.width <= 0 || r.height <= 0 || r.x+r.width > 1.000001 || r.y+r.height > 1.000001))) return invalid('INVALID_LOCATION', sourceNavigation ? sourceError('保存的文本位置超出页面。') : '文本位置超出页面')
    const result = await host(location, signal)
    if (sourceNavigation && result.status !== 'ok') return { ...result, message: sourceError(result.message) }
    return result
  } catch (error) {
    if (stale()) return invalid('STALE_CONTEXT', '阅读上下文已失效或操作已取消')
    const code = error instanceof ApiError ? error.code : 'NAVIGATION_FAILED'
    const message = error instanceof Error ? error.message : '导航失败'
    return invalid(code, sourceNavigation ? sourceError(message) : message)
  }
}
