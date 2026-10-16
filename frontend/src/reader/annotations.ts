import { reactive } from 'vue'
import { api } from '../api'
import { auth } from '../auth'
import type { NormalizedRect, SelectionPosition } from './context'

export const annotationLabels = { highlight: '高亮', underline: '下划线', squiggly: '波浪线', strikeout: '删除线', comment: '注释', freeText: '自由文本' } as const
export const annotationColors = ['#F5D547', '#9B0000', '#47A58E', '#6395CF'] as const
export type AnnotationType = keyof typeof annotationLabels
export type Geometry = { kind: 'text'; positions: SelectionPosition[] } | { kind: 'anchor'; pageNumber: number; x: number; y: number } | { kind: 'box'; pageNumber: number; rect: NormalizedRect; rotation: 0 }
export interface AnnotationData { id: string; type: AnnotationType; schemaVersion: 1; pageNumber: number; position: SelectionPosition[] | null; geometry: Geometry; style: { stroke?: string | null; fill?: string | null; opacity?: number; lineWidth?: number; fontSize?: number }; selectedText: string | null; content: string | null; color: string; assetId: null; zIndex: number }
export interface AnnotationDTO extends AnnotationData { documentId: string; version: number; createdAt: string; updatedAt: string }
interface Result { commandId: string; annotationRevision: number; annotation: AnnotationDTO | null }
interface Snapshot { items: AnnotationDTO[]; annotationRevision: number }
interface Intent { id: string; desired: AnnotationDTO | null; prepared?: { path: string; method: string; body: Record<string, unknown>; at: number } }
interface History { id: string; before: AnnotationDTO | null; after: AnnotationDTO | null }
const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value))
export function annotationData(value: AnnotationData): AnnotationData {
  const { id, type, schemaVersion, pageNumber, position, geometry, style, selectedText, content, color, assetId, zIndex } = value
  return clone({ id, type, schemaVersion, pageNumber, position, geometry, style, selectedText, content, color, assetId, zIndex })
}

export function createAnnotations(documentId: string) {
  const state = reactive({ items: [] as AnnotationDTO[], revision: 0, phase: 'loading' as 'loading'|'draft'|'sending'|'confirmed'|'failed'|'conflict', error: '', dirty: false, undoCount: 0, redoCount: 0, hasBackup: false })
  const path = `/documents/${encodeURIComponent(documentId)}`
  const key = `litera:annotations:${auth.user?.id}:${documentId}`
  let server: AnnotationDTO[] = [], queue: Intent[] = [], tombstones: Record<string, AnnotationDTO> = {}
  let undoStack: History[] = [], redoStack: History[] = [], timer: ReturnType<typeof setTimeout> | undefined, inFlight: Promise<void> | undefined, disposed = false, cleared = false
  let corruptDraft: string | undefined
  function project() {
    const items = new Map(server.map(a => [a.id, a]))
    for (const job of queue) { if (job.desired) items.set(job.id, job.desired); else items.delete(job.id) }
    state.items = clone([...items.values()]); state.dirty = queue.length > 0 || !!corruptDraft
    state.undoCount = undoStack.length; state.redoCount = redoStack.length
    if (cleared || corruptDraft) return
    try { if (queue.length) sessionStorage.setItem(key, JSON.stringify({ queue, tombstones })); else sessionStorage.removeItem(key) } catch { /* The in-memory queue and leave guard remain active. */ }
  }
  async function request<T>(url: string, options: RequestInit = {}) {
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 8000)
    try { return await api<T>(url, { ...options, signal: controller.signal }, auth.csrfToken) } finally { clearTimeout(timeout) }
  }
  async function load() {
    const saved = await request<Snapshot>(path + '/annotations'); server = saved.items; state.revision = saved.annotationRevision
    try {
      state.hasBackup = Object.keys(sessionStorage).some(k => k.startsWith(key + ':backup:'))
      const raw = sessionStorage.getItem(key), draft = JSON.parse(raw || 'null')
      if (draft && (!Array.isArray(draft.queue) || !draft.queue.every(validIntent))) throw new Error('Invalid local draft')
      if (draft?.queue?.length) { queue = draft.queue; tombstones = draft.tombstones || {}; state.error = '发现未完成的批注草稿，请重试以核对命令结果。'; state.phase = 'failed' }
      else state.phase = 'confirmed'
    } catch { corruptDraft = sessionStorage.getItem(key) || 'invalid'; state.error = '本地草稿无法读取，请先导出草稿再载入服务端。'; state.phase = 'failed' }
    project()
  }
  function validIntent(job: Intent) {
    if (!job || typeof job.id !== 'string' || !job.id.length || job.id.length > 36 || !(job.desired === null || (job.desired?.id === job.id && job.desired.documentId === documentId))) return false
    if (!job.prepared) return true
    const p = job.prepared, b = p.body
    return !!b && typeof b.commandId === 'string' && b.commandId.length > 0 && b.commandId.length <= 36 && Number.isInteger(b.baseRevision) && Number(b.baseRevision) >= 0 && Number.isFinite(p.at) &&
      ((p.path === path + '/annotations' && p.method === 'POST') || (p.path === path + '/annotation-commands' && p.method === 'POST' && b.operation === 'restore') || (p.path === path + '/annotations/' + encodeURIComponent(job.id) && ['PATCH','DELETE'].includes(p.method)))
  }
  function enqueue(id: string, desired: AnnotationDTO | null) {
    if (disposed || state.phase === 'loading') return
    queue.push({ id, desired: clone(desired) }); if (!state.error) state.phase = 'draft'; project()
    clearTimeout(timer); timer = setTimeout(() => { void flush() }, 1000)
  }
  function change(id: string, desired: AnnotationDTO | null) {
    const before = state.items.find(a => a.id === id) || null
    undoStack.push({ id, before: clone(before), after: clone(desired) }); if (undoStack.length > 100) undoStack.shift()
    redoStack = []; enqueue(id, desired)
  }
  function create(data: AnnotationData) {
    const now = new Date().toISOString()
    change(data.id, { ...clone(data), documentId, version: 0, createdAt: now, updatedAt: now })
  }
  function edit(id: string, changes: Partial<AnnotationData>) { const item = state.items.find(a => a.id === id); if (item) change(id, { ...clone(item), ...clone(changes) }) }
  function remove(id: string) { if (state.items.some(a => a.id === id)) change(id, null) }
  async function execute(job: Intent) {
    const existing = server.find(a => a.id === job.id)
    if (!job.prepared) {
      const body: Record<string, unknown> = { commandId: crypto.randomUUID(), baseRevision: state.revision }
      let url = path + '/annotations', method = 'POST'
      if (!job.desired) {
        if (!existing) return
        url += '/' + encodeURIComponent(job.id); method = 'DELETE'; body.version = existing.version
      } else if (existing) {
        url += '/' + encodeURIComponent(job.id); method = 'PATCH'; body.version = existing.version
        const { color, content, style, geometry, zIndex } = job.desired
        body.changes = { color, content, style, zIndex, ...(geometry.kind === 'text' ? {} : { geometry }) }
      } else if (tombstones[job.id]) { url = path + '/annotation-commands'; body.operation = 'restore'; body.annotation = tombstones[job.id] }
      else body.annotation = annotationData(job.desired)
      job.prepared = { path: url, method, body, at: Date.now() }; project()
    }
    const sent = job.prepared!
    let result: Result | undefined
    // Always reconcile a prepared command first, including after refresh and timeout.
    try { result = await request<Result>(`${path}/annotation-commands/${sent.body.commandId}`) }
    catch (error: any) { if (error.status !== 404 || error.code !== 'COMMAND_NOT_FOUND') throw error }
    if (disposed) return
    if (!result) {
      if (Date.now() - sent.at >= 24 * 3600_000) throw { status: 409, message: '命令收据已过期，请导出草稿并核对服务端。' }
      result = await request<Result>(sent.path, { method: sent.method, body: JSON.stringify(sent.body) })
    }
    if (!result.annotation && existing) tombstones[job.id] = clone(existing)
    server = server.filter(a => a.id !== job.id)
    if (result.annotation) { server.push(result.annotation); delete tombstones[job.id] }
    state.revision = result.annotationRevision
  }
  async function flush(): Promise<void> {
    clearTimeout(timer)
    if (inFlight) return inFlight
    if (disposed || state.error || !queue.length) return
    inFlight = (async () => {
      while (queue.length && !state.error && !disposed) {
        state.phase = 'sending'
        try { await execute(queue[0]!); queue.shift(); project(); state.phase = queue.length ? 'draft' : 'confirmed' }
        catch (error: any) { state.phase = error.status === 409 ? 'conflict' : 'failed'; state.error = error.status === 409 ? '批注发生并发冲突；本地草稿已保留。请导出草稿或核对服务端后处理。' : `批注未保存：${error.message || '请求失败'}。草稿已保留，请重试。`; project(); break }
      }
    })()
    try { await inFlight } finally { inFlight = undefined }
  }
  async function retry() { if (state.phase === 'conflict' || corruptDraft) return; state.error = ''; await flush() }
  async function undo() {
    await flush(); if (state.error || disposed) return
    const entry = undoStack.pop(); if (!entry) return
    redoStack.push(entry); enqueue(entry.id, entry.before); await flush()
  }
  async function redo() {
    await flush(); if (state.error || disposed) return
    const entry = redoStack.pop(); if (!entry) return
    undoStack.push(entry); enqueue(entry.id, entry.after); await flush()
  }
  function exportDraft() {
    const backups: Record<string, string | null> = {}
    try { for (const k of Object.keys(sessionStorage)) if (k.startsWith(key + ':backup:')) backups[k] = sessionStorage.getItem(k) } catch { /* Current in-memory draft remains exportable. */ }
    const blob = new Blob([JSON.stringify({ documentId, server, queue, tombstones, corruptDraft, backups }, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = `litera-annotations-${documentId}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  async function reloadServer() {
    if (inFlight) await inFlight
    const saved = await request<Snapshot>(path + '/annotations')
    // Retain the conflict draft even after the explicit server choice.
    if (queue.length || corruptDraft) { sessionStorage.setItem(key + ':backup:' + Date.now(), corruptDraft || JSON.stringify({ queue, tombstones })); state.hasBackup = true }
    server = saved.items; state.revision = saved.annotationRevision; queue = []; tombstones = {}; undoStack = []; redoStack = []
    corruptDraft = undefined
    state.error = ''; state.phase = 'confirmed'; project()
  }
  async function preserveForLeave() {
    if (inFlight) await inFlight
    try {
      // Keep exact unresolved commands for receipt reconciliation on next open.
      if (corruptDraft) sessionStorage.setItem(key, corruptDraft)
      else if (queue.length) sessionStorage.setItem(key, JSON.stringify({ queue, tombstones }))
      return true
    } catch { state.error = '浏览器无法保留批注草稿，请先导出草稿或恢复网络保存。'; return false }
  }
  function dispose(clear = false) { disposed = true; cleared = clear; clearTimeout(timer); if (clear) sessionStorage.removeItem(key) }
  return { state, load, create, edit, remove, flush, retry, undo, redo, reloadServer, preserveForLeave, exportDraft, dispose }
}
