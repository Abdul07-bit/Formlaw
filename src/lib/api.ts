/**
 * HTTP client. The access token lives only in memory; the refresh token is an httpOnly SameSite=Strict cookie that
 * JavaScript cannot read. Cookie-authenticated endpoints require the X-Requested-With header (CSRF defence).
 */
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message)
  }
}

const BASE = (import.meta.env.VITE_API_URL ?? '') + '/api/v1'
let accessToken: string | null = null
let refreshing: Promise<SessionBody | null> | null = null

export interface SessionBody {
  accessToken: string
  expiresIn: number
  user: unknown
}
const listeners = new Set<(token: string | null) => void>()

export function setToken(t: string | null) {
  accessToken = t
  listeners.forEach((l) => l(t))
}
export const getToken = () => accessToken
export function onTokenChange(fn: (t: string | null) => void) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export async function refresh(): Promise<SessionBody | null> {
  refreshing ??= (async () => {
    try {
      const r = await fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'include', headers: { 'x-requested-with': 'formlaw' } })
      if (!r.ok) {
        setToken(null)
        return null
      }
      const body = (await r.json()) as SessionBody
      setToken(body.accessToken)
      return body
    } catch {
      return null
    } finally {
      setTimeout(() => (refreshing = null), 0)
    }
  })()
  return refreshing
}

async function parseError(r: Response): Promise<ApiError> {
  try {
    const body = await r.json()
    const e = body.error ?? {}
    const detail = Array.isArray(e.details) ? `: ${e.details.map((d: { loc?: string[]; msg?: string }) => `${(d.loc ?? []).slice(1).join('.')} ${d.msg}`).join('; ')}` : ''
    return new ApiError(r.status, e.code ?? 'error', (e.message ?? r.statusText) + detail, e.details)
  } catch {
    return new ApiError(r.status, 'error', r.statusText || 'Request failed')
  }
}

export async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers)
  if (accessToken) headers.set('authorization', `Bearer ${accessToken}`)
  if (init.body && !(init.body instanceof FormData) && !headers.has('content-type')) headers.set('content-type', 'application/json')
  const r = await fetch(`${BASE}${path}`, { ...init, headers, credentials: 'include' })
  if (r.status === 401 && retry && !path.startsWith('/auth/')) {
    if (await refresh()) return request<T>(path, init, false)
  }
  if (!r.ok) throw await parseError(r)
  if (r.status === 204) return undefined as T
  return r.json() as Promise<T>
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) => request<T>(p, { method: 'POST', body: body instanceof FormData ? body : JSON.stringify(body ?? {}) }),
  put: <T>(p: string, body?: unknown) => request<T>(p, { method: 'PUT', body: JSON.stringify(body ?? {}) }),
  patch: <T>(p: string, body?: unknown) => request<T>(p, { method: 'PATCH', body: JSON.stringify(body ?? {}) }),
  del: <T>(p: string) => request<T>(p, { method: 'DELETE' }),
  auth: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: 'POST', body: JSON.stringify(body ?? {}), headers: { 'x-requested-with': 'formlaw' } }, false),
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message
  if (e instanceof Error) return e.message
  return 'Something went wrong'
}

/** Server-sent events over fetch (EventSource cannot send the Authorization header). */
export async function streamEvents(path: string, onEvent: (type: string, data: unknown) => void, signal: AbortSignal): Promise<void> {
  const r = await fetch(`${BASE}${path}`, { headers: accessToken ? { authorization: `Bearer ${accessToken}` } : {}, credentials: 'include', signal })
  if (!r.ok || !r.body) throw await parseError(r)
  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    buf += decoder.decode(value, { stream: true })
    let i: number
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const frame = buf.slice(0, i)
      buf = buf.slice(i + 2)
      let type = 'message'
      let data = ''
      for (const line of frame.split('\n')) {
        if (line.startsWith('event: ')) type = line.slice(7)
        else if (line.startsWith('data: ')) data += line.slice(6)
      }
      if (data) {
        try {
          onEvent(type, JSON.parse(data))
        } catch {
          /* malformed frame: ignore */
        }
      }
    }
  }
}
