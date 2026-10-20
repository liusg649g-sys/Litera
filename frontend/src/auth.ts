import { reactive } from 'vue'
import { api, ApiError } from './api'
import { clearReaderTabs } from './reader/state'
export interface User { id: string; email: string; displayName: string; createdAt: string }
interface SessionResult { user: User; csrfToken: string }
export const auth = reactive({ user: null as User | null, csrfToken: '', restoreError: '' })
function applySession(result: SessionResult) {
  if (auth.user?.id !== result.user.id) clearReaderTabs(!!auth.user)
  auth.user = result.user; auth.csrfToken = result.csrfToken; auth.restoreError = ''
}
export function clearAuth() { clearReaderTabs(true); auth.user = null; auth.csrfToken = ''; auth.restoreError = '' }
export async function restoreSession() {
  try {
    const result = await api<SessionResult>('/auth/session')
    applySession(result)
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) clearAuth()
    else auth.restoreError = error instanceof Error ? error.message : '无法读取登录状态'
  }
}
export async function login(email: string, password: string) {
  const result = await api<SessionResult>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
  applySession(result)
}
export async function logout() {
  await api<void>('/auth/logout', { method: 'POST' }, auth.csrfToken)
  clearAuth()
}
export async function updateProfile(displayName: string) {
  auth.user = await api<User>('/users/me', { method: 'PATCH', body: JSON.stringify({ displayName }) }, auth.csrfToken)
}
export async function changePassword(currentPassword: string, newPassword: string) {
  await api<void>('/auth/password', { method: 'POST', body: JSON.stringify({ currentPassword, newPassword }) }, auth.csrfToken)
  clearAuth()
}
