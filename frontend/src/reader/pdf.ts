import { getDocument, PDFWorker, TextLayer, version } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { ApiError } from '../api'

export const pdfVersion = version
export const pdfAssets = `/pdfjs/${version}/`
export function createPdfTask(url: string, full = false) {
  // A real module Worker is mandatory; an explicit port avoids PDF.js fake-worker fallback.
  const port = new Worker(workerUrl, { type: 'module' })
  const worker = PDFWorker.create({ port })
  const task = getDocument({ url, worker, withCredentials: true,
    cMapUrl: pdfAssets + 'cmaps/', cMapPacked: true,
    standardFontDataUrl: pdfAssets + 'standard_fonts/', wasmUrl: pdfAssets + 'wasm/',
    iccUrl: pdfAssets + 'iccs/',
    disableRange: full, disableStream: full,
  })
  const failedWorker = new Promise<never>((_, reject) => {
    port.addEventListener('error', () => reject(new ApiError(0, 'PDF_WORKER_START_FAILED',
      'PDF 阅读组件启动失败，请检查 Worker 文件是否加载成功及服务器 JavaScript 类型配置')), { once: true })
  })
  const promise = Promise.race([task.promise, failedWorker])
  let disposed = false
  return { task, promise, async destroy() {
    if (disposed) return
    disposed = true
    try { await task.destroy() } finally { worker.destroy(); port.terminate(); TextLayer.cleanup() }
  } }
}
export function pdfStatus(error: unknown): number {
  if (error instanceof ApiError) return error.status
  return typeof error === 'object' && error && 'status' in error ? Number(error.status) : 0
}
export function pdfError(error: unknown): string {
  const status = pdfStatus(error)
  if (status === 401) return '登录已失效，请重新登录'
  if (status === 404) return '文献不存在、已删除或无权访问'
  if (status === 416) return 'PDF 字节范围读取失败，请重试'
  const name = error instanceof Error ? error.name : ''
  if (name === 'PasswordException') return '暂不支持加密 PDF，请先解密后上传'
  if (name === 'InvalidPDFException') return 'PDF 结构损坏或格式不受支持'
  return error instanceof ApiError ? error.message : '无法加载 PDF，请检查网络或文件后重试'
}
