import type { Role, User } from '../../types'
import { handleSessionLost, refreshSession, request, setAccessToken, type SessionPayload } from '../api/client'
import { loadKycQueue, loadPendingLawyerCases, loadSecurityEvents } from '../admin'
import { loadCase, loadMyCases } from '../cases'
import { loadConnections } from '../connections'
import { loadDirectory, loadMyProfile } from '../lawyers'
import { store } from '../store'

handleSessionLost(() => store.clearPrivate())

async function startSession(s: SessionPayload): Promise<User> {
  setAccessToken(s.accessToken)
  store.update((d) => ({ ...d, session: s.user, authReady: true }))
  await loadForRole(s.user)
  return s.user
}

/** Fetch what this role's pages render. Every call is authorised server-side. */
export async function loadForRole(u: User) {
  const jobs: Promise<unknown>[] = [loadDirectory()]
  if (u.role === 'client') jobs.push(loadMyCases(), loadConnections())
  if (u.role === 'lawyer' || u.role === 'judge') {
    // Briefs for connections the client approved (the server hides raw document text from counsel).
    jobs.push(loadMyProfile(), loadConnections().then((list) => Promise.allSettled(list.filter((c) => c.status !== 'declined').map((c) => loadCase(c.caseId)))))
  }
  if (u.role === 'admin') jobs.push(loadKycQueue(), loadPendingLawyerCases(), loadSecurityEvents())
  await Promise.allSettled(jobs)
}

export async function register(input: { name: string; email: string; password: string; role: Exclude<Role, 'admin'>; city?: string }) {
  return startSession(await request<SessionPayload>('/auth/register', { body: input, auth: false }))
}

export async function login(email: string, password: string) {
  return startSession(await request<SessionPayload>('/auth/login', { body: { email, password }, auth: false }))
}

/** DEMO personas (synthetic accounts). Works only when the server runs with DEMO_MODE=true. */
export async function demoLogin(persona: 'client' | 'lawyer' | 'admin') {
  store.clearPrivate()
  return startSession(await request<SessionPayload>('/auth/demo', { body: { persona }, auth: false }))
}

export async function signOut() {
  await request('/auth/logout', { method: 'POST', auth: false, csrf: true }).catch(() => undefined)
  setAccessToken(null)
  store.clearPrivate()
}

/** On page load: the httpOnly refresh cookie (if any) restores the session; otherwise load public data only. */
export async function restoreSession() {
  const s = await refreshSession()
  if (s) {
    await startSession(s)
  } else {
    store.update((d) => ({ ...d, authReady: true }))
    await loadDirectory().catch(() => undefined)
  }
}
