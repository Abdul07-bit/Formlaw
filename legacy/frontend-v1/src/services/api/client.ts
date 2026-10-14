// Typed HTTP client for the FormLaw API (/api/v1). The access token lives only in memory; the refresh
// token is an httpOnly cookie the browser cannot read. No secrets or database access exist in the frontend.

const BASE = `${((import.meta.env.VITE_API_URL as string | undefined) ?? '').replace(/\/$/, '')}/api/v1`

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string, public details?: unknown) {
    super(message)
  }
}

let accessToken: string | null = null
let onSessionLost: (() => void) | null = null
export const setAccessToken = (t: string | null) => { accessToken = t }
export const handleSessionLost = (fn: () => void) => { onSessionLost = fn }

export interface SessionPayload { accessToken: string; expiresIn: number; user: import('../../types').User }

let refreshing: Promise<SessionPayload | null> | null = null

/** Exchange the refresh cookie for a new access token. Concurrent callers share one request. */
export function refreshSession(): Promise<SessionPayload | null> {
  refreshing ??= fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'include', headers: { 'x-requested-with': 'formlaw' } })
    .then(async (r) => (r.ok ? ((await r.json()) as SessionPayload) : null))
    .catch(() => null)
    .then((s) => { setAccessToken(s?.accessToken ?? null); return s })
    .finally(() => { refreshing = null })
  return refreshing
}

interface Options { method?: string; body?: unknown; form?: FormData; auth?: boolean; csrf?: boolean; signal?: AbortSignal }

export async function request<T>(path: string, opts: Options = {}, retried = false): Promise<T> {
  const headers: Record<string, string> = {}
  if (opts.body !== undefined) headers['content-type'] = 'application/json'
  if (opts.auth !== false && accessToken) headers.authorization = `Bearer ${accessToken}`
  if (opts.csrf) headers['x-requested-with'] = 'formlaw'
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      method: opts.method ?? (opts.body !== undefined || opts.form ? 'POST' : 'GET'),
      headers, credentials: 'include', signal: opts.signal,
      body: opts.form ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Cannot reach the FormLaw server. Is the backend running (npm run api)?')
  }
  if (res.status === 401 && opts.auth !== false && !retried) {
    const s = await refreshSession()
    if (s) return request<T>(path, opts, true)
    onSessionLost?.()
  }
  if (!res.ok) {
    let code = 'http_error', message = `Request failed (${res.status})`, requestId: string | undefined, details: unknown
    try {
      const j = await res.json()
      if (j?.error) ({ code, message, request_id: requestId, details } = j.error)
    } catch {
      // Non-JSON 5xx = the dev proxy could not reach the API (our API always returns JSON errors).
      if (res.status >= 500) throw new ApiError(res.status, 'backend_unreachable', 'Cannot reach the FormLaw server. Start the backend with: npm run api')
    }
    throw new ApiError(res.status, code, message, requestId, details)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

export const errorMessage = (e: unknown) => (e instanceof ApiError ? e.message : e instanceof Error ? e.message : 'Something went wrong')
