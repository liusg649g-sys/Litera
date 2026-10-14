export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string,
    public details?: Record<string, unknown>, public requestId?: string) { super(message) }
}
export async function api<T>(path: string, options: RequestInit = {}, csrfToken?: string): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (csrfToken) headers.set('X-CSRF-Token', csrfToken)
  let response: Response
  try {
    response = await fetch('/api/v1' + path, { ...options, headers, credentials: 'same-origin' })
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', '无法连接服务，请检查网络后重试')
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    if (response.status === 401 && !['/auth/login', '/auth/session'].includes(path)) {
      window.dispatchEvent(new Event('litera:unauthenticated'))
    }
    throw new ApiError(response.status, data?.error?.code || 'REQUEST_FAILED',
      data?.error?.message || '请求失败，请稍后重试', data?.error?.details, data?.requestId)
  }
  return response.status === 204 ? undefined as T : await response.json() as T
}
