import { ApiError } from '../api'

export async function exportAnnotatedPdf(documentId: string, revision: number, csrf: string, signal: AbortSignal) {
  let response: Response
  try {
    response = await fetch(`/api/v1/documents/${encodeURIComponent(documentId)}/annotated-pdf`, {
      method: 'POST', credentials: 'same-origin', signal,
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: JSON.stringify({ expectedAnnotationRevision: revision }),
    })
  } catch (error) {
    if (signal.aborted) throw error
    throw new ApiError(0, 'NETWORK_ERROR', '无法连接服务，请检查网络后重试')
  }
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('litera:unauthenticated'))
    const data = await response.json().catch(() => null)
    throw new ApiError(response.status, data?.error?.code || 'EXPORT_FAILED', data?.error?.message || 'PDF导出失败，请重试')
  }
  if (!response.headers.get('Content-Type')?.startsWith('application/pdf')) throw new Error('导出响应不是PDF，请重试')
  const blob = await response.blob()
  if (signal.aborted) throw new DOMException('Canceled', 'AbortError')
  const disposition = response.headers.get('Content-Disposition') || ''
  const match = /filename\*=UTF-8''([^;]+)/i.exec(disposition)
  let filename = 'Litera-带批注.pdf'
  try { if (match?.[1]) filename = decodeURIComponent(match[1]).replace(/[\\/\x00-\x1f]/g, '_') } catch { /* Keep safe default. */ }
  const url = URL.createObjectURL(blob), anchor = document.createElement('a')
  anchor.href = url; anchor.download = filename; anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
