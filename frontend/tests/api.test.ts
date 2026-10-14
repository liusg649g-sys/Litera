import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../src/api'
beforeEach(() => vi.unstubAllGlobals())
describe('HTTP contract', () => {
  it('lets the browser set multipart boundaries and preserves conflict details', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: {
      code: 'DUPLICATE_DOCUMENT', message: '重复', details: { existingDocumentId: 'doc', inTrash: false } }, requestId: 'trace' }), { status: 409 }))
    vi.stubGlobal('fetch', fetchMock)
    const form = new FormData(); form.append('file', new File(['pdf'], 'test.pdf'))
    await expect(api('/documents', { method: 'POST', body: form }, 'csrf')).rejects.toMatchObject({
      details: { existingDocumentId: 'doc', inTrash: false }, requestId: 'trace' })
    expect(fetchMock.mock.calls[0][1].headers.has('Content-Type')).toBe(false)
    expect(fetchMock.mock.calls[0][1].headers.get('X-CSRF-Token')).toBe('csrf')
  })
  it('sends session cookies and csrf headers for a write', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)
    await api('/auth/logout', { method: 'POST' }, 'test-csrf')
    expect(fetchMock.mock.calls[0][1].credentials).toBe('same-origin')
    expect(fetchMock.mock.calls[0][1].headers.get('X-CSRF-Token')).toBe('test-csrf')
  })
  it('surfaces backend duplicate-account error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'EMAIL_EXISTS', message: '该邮箱已注册，请直接登录' }, requestId: 'test',
    }), { status: 409 })))
    await expect(api('/auth/register')).rejects.toMatchObject({ status: 409, code: 'EMAIL_EXISTS' })
  })
  it('reports network errors without pretending success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    await expect(api('/auth/session')).rejects.toMatchObject({ code: 'NETWORK_ERROR' })
  })
  it('does not recursively navigate when the route guard checks an expired session', async () => {
    const listener = vi.fn()
    window.addEventListener('litera:unauthenticated', listener)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'UNAUTHENTICATED', message: '请先登录' }, requestId: 'test',
    }), { status: 401 })))
    await expect(api('/auth/session')).rejects.toMatchObject({ status: 401 })
    expect(listener).not.toHaveBeenCalled()
    window.removeEventListener('litera:unauthenticated', listener)
  })
  it('notifies the app if an authenticated business request expires', async () => {
    const listener = vi.fn()
    window.addEventListener('litera:unauthenticated', listener)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'UNAUTHENTICATED', message: '登录已失效' }, requestId: 'test',
    }), { status: 401 })))
    await expect(api('/users/me')).rejects.toMatchObject({ status: 401 })
    expect(listener).toHaveBeenCalledTimes(1)
    window.removeEventListener('litera:unauthenticated', listener)
  })
})
