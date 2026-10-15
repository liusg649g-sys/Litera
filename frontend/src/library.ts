import { api } from './api'
import { auth } from './auth'
export interface FolderDTO { id: string; name: string }
export interface TagDTO extends FolderDTO { color: string | null }
export interface CleanupJobDTO { jobId: string; documentId?: string; status: 'pending' | 'running' | 'completed' | 'failed'; errorCode: string | null }
export interface DocumentDTO {
  id: string; title: string; authors: string[]; abstract: string | null; keywords: string[];
  year: number | null; journal: string | null; doi: string | null; folderId: string | null;
  tags: { id: string; name: string; color: string | null }[];
  attachment: { originalName: string; sizeBytes: number; mimeType: string };
  parseStatus: string; extractionVersion: string | null; pageCount: number | null;
  version: number; createdAt: string; updatedAt: string; lastReadAt: string | null; deletedAt: string | null;
  cleanupJob: CleanupJobDTO | null;
}
export interface DocumentPage { items: DocumentDTO[]; page: number; pageSize: number; total: number }
export interface DocumentDraft { title: string; authors: string[]; abstract: string | null; keywords: string[];
  year: number | null; journal: string | null; doi: string | null; version: number; folderId?: string | null; tagIds?: string[] }
export interface LibraryFilters { q: string; folderId: string; tagIds: string[]; yearFrom: string; yearTo: string }
export function listDocuments(page: number, pageSize: number, sort: string, order: string, signal?: AbortSignal, filters?: LibraryFilters, mode = 'documents') {
  const query = new URLSearchParams({ page: String(page), pageSize: String(pageSize), sort, order })
  if (mode === 'trash') {
    query.delete('sort'); query.delete('order')
    return api<DocumentPage>('/trash/documents?' + query, { signal })
  }
  if (filters) for (const [key, value] of Object.entries(filters)) {
    const text = Array.isArray(value) ? value.join(',') : value.trim()
    if (text) query.set(key, text)
  }
  if (mode === 'recent') return api<{ items: { document: DocumentDTO }[]; total: number; page: number; pageSize: number }>('/reading-history?' + query, { signal })
    .then(result => ({ ...result, items: result.items.map(item => item.document) }))
  return api<DocumentPage>('/documents?' + query, { signal })
}
export const getDocument = (id: string) => api<DocumentDTO>('/documents/' + encodeURIComponent(id))
export function uploadDocument(file: File, folderId?: string) {
  const form = new FormData(); form.append('file', file)
  if (folderId) form.append('folderId', folderId)
  return api<DocumentDTO>('/documents', { method: 'POST', body: form }, auth.csrfToken)
}
export type DocumentUpdate = Pick<DocumentDraft, 'version'> & Partial<Omit<DocumentDraft, 'version'>>
export const saveDocument = (id: string, draft: DocumentUpdate) =>
  api<DocumentDTO>('/documents/' + encodeURIComponent(id), { method: 'PATCH', body: JSON.stringify(draft) }, auth.csrfToken)
export const contentUrl = (id: string, download = false) => '/api/v1/documents/' + encodeURIComponent(id) + '/content' + (download ? '?download=true' : '')
export const listFolders = () => api<FolderDTO[]>('/folders')
export const listTags = () => api<TagDTO[]>('/tags')
export const writeCategory = (kind: 'folders' | 'tags', name: string, id?: string) =>
  api<FolderDTO>('/' + kind + (id ? '/' + encodeURIComponent(id) : ''), { method: id ? 'PATCH' : 'POST', body: JSON.stringify({ name }) }, auth.csrfToken)
export const removeCategory = (kind: 'folders' | 'tags', id: string) => api<void>('/' + kind + '/' + encodeURIComponent(id), { method: 'DELETE' }, auth.csrfToken)
export const trashDocument = (id: string) => api<void>('/documents/' + encodeURIComponent(id), { method: 'DELETE' }, auth.csrfToken)
export const restoreDocument = (id: string) => api<DocumentDTO>('/trash/documents/' + encodeURIComponent(id) + '/restore', { method: 'POST' }, auth.csrfToken)
export const purgeDocument = (id: string) => api<CleanupJobDTO | undefined>('/trash/documents/' + encodeURIComponent(id), { method: 'DELETE' }, auth.csrfToken)
export const retryCleanup = (id: string) => api<CleanupJobDTO | undefined>('/cleanup-jobs/' + encodeURIComponent(id) + '/retry', { method: 'POST' }, auth.csrfToken)
export const getCleanup = (id: string) => api<CleanupJobDTO>('/cleanup-jobs/' + encodeURIComponent(id))
export const recordOpen = (id: string, signal?: AbortSignal) => api('/documents/' + encodeURIComponent(id) + '/progress', { method: 'PUT', body: '{}', signal }, auth.csrfToken)
export const clampSidebar = (width: number) => Math.min(320, Math.max(180, width))
export function sizeLabel(bytes: number) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KiB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MiB'
}
