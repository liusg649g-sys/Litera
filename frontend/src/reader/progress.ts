import { reactive } from 'vue'
import { api } from '../api'
import { auth } from '../auth'
import type { ViewMode, ZoomMode } from './state'

export interface ReadingState { pageNumber: number; zoom: number; zoomMode: ZoomMode; viewMode: ViewMode }
export interface ProgressDTO { documentId: string; pageNumber: number | null; zoom: number | null; zoomMode: ZoomMode; viewMode: ViewMode; version: number; lastReadAt: string | null }
export function createProgress(documentId: string) {
  const status = reactive({ error: '', saving: false, conflict: false, dirty: false })
  const path = `/documents/${encodeURIComponent(documentId)}/progress`
  const key = `litera:progress:${auth.user?.id}:${documentId}`
  let version = 0, pending: ReadingState | undefined, latest: ProgressDTO | undefined
  let sequence = 0, timer: ReturnType<typeof setTimeout> | undefined, maximum: ReturnType<typeof setTimeout> | undefined
  let inFlight: Promise<void> | undefined, opened = false, needsOpen = true, disposed = false
  const stopTimers = () => { clearTimeout(timer); clearTimeout(maximum); timer = maximum = undefined }
  function store() { try { if (pending) sessionStorage.setItem(key, JSON.stringify(pending)); else sessionStorage.removeItem(key) } catch { /* In-memory draft remains available. */ } }
  async function load(signal?: AbortSignal) {
    latest = await api<ProgressDTO>(path, { signal }); version = latest.version
    try {
      const value = JSON.parse(sessionStorage.getItem(key) || 'null')
      if (value && Number.isInteger(value.pageNumber) && value.pageNumber > 0 && Number.isFinite(value.zoom) && value.zoom >= .5 && value.zoom <= 5 && ['continuous','single','spread'].includes(value.viewMode) && ['custom','fit-width','fit-height'].includes(value.zoomMode)) {
        pending = value; status.dirty = true; status.conflict = true; status.error = '发现未同步的本地阅读进度，请选择载入服务端或保存本地。'
      }
    } catch { /* Invalid local data is never sent. */ }
    return pending || latest
  }
  function stage(state: ReadingState) {
    if (disposed || !opened) return
    if (pending && JSON.stringify(state) === JSON.stringify(pending)) return
    pending = { ...state }; sequence++; status.dirty = true; store()
    if (status.error) return
    clearTimeout(timer); timer = setTimeout(() => { void flush() }, 1000)
    maximum ??= setTimeout(() => { void flush() }, 5000)
  }
  async function flush(): Promise<void> {
    stopTimers()
    if (inFlight) { await inFlight; if (pending && !status.error) return flush(); return }
    if (!pending || status.error || disposed) return
    const sent = pending, revision = sequence
    status.saving = true
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 8000)
    inFlight = (async () => {
      try {
        latest = await api<ProgressDTO>(path, { method: 'PUT', body: JSON.stringify({ ...sent, version, recordOpen: needsOpen }), signal: controller.signal }, auth.csrfToken)
        version = latest.version
        needsOpen = false
        if (sequence === revision) { pending = undefined; status.dirty = false; store() }
      } catch (error: any) {
        status.conflict = error.status === 409
        status.error = status.conflict ? '阅读记录已被其他会话更新，本地进度已保留。请选择如何处理。' : '阅读记录未同步，本地进度已保留。请重试后再离开。'
        if (status.conflict) { try { latest = await api<ProgressDTO>(path) } catch { /* Retry must re-read before writing. */ } }
      } finally { clearTimeout(timeout); status.saving = false; inFlight = undefined }
    })()
    await inFlight
    if (pending && !status.error && sequence !== revision) await flush()
  }
  async function ready(state: ReadingState) {
    if (opened) return
    opened = true
    // The first successful target frame is the real open event.
    if (!status.conflict) { stage(state); await flush() }
  }
  async function retry() { if (status.conflict) return; status.error = ''; await flush() }
  async function resolve(local: boolean) {
    if (!opened || disposed) return
    // Explicit user choice is required before rebasing a retained local draft.
    latest = await api<ProgressDTO>(path); version = latest.version
    status.conflict = false; status.error = ''
    if (local) await flush()
    else { pending = undefined; status.dirty = false; store(); return latest }
  }
  function dispose(clear = false) { disposed = true; stopTimers(); if (clear) { pending = undefined; store() } }
  return { status, load, stage, flush, ready, retry, resolve, dispose }
}
