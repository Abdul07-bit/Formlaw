import type { AuditEntry, CompletedCase, Lawyer, SecurityEvent } from '../../types'
import { request } from '../api/client'
import { store, upsert } from '../store'

export async function loadKycQueue() {
  const list = await request<Lawyer[]>('/admin/kyc')
  store.update((d) => ({ ...d, lawyers: list.reduce((acc, l) => upsert(acc, l), d.lawyers) }))
}

export async function decideKyc(lawyerId: string, approve: boolean, note: string) {
  const l = await request<Lawyer>(`/admin/kyc/${encodeURIComponent(lawyerId)}/decision`, { body: { approve, note } })
  store.update((d) => ({ ...d, lawyers: upsert(d.lawyers, l) }))
}

export async function loadPendingLawyerCases() {
  const pending = await request<CompletedCase[]>('/admin/lawyer-cases?status=pending')
  store.update((d) => ({ ...d, completedCases: [...pending, ...d.completedCases.filter((c) => c.verified)] }))
}

export async function verifyLawyerCase(id: string, approve: boolean) {
  const c = await request<CompletedCase>(`/admin/lawyer-cases/${encodeURIComponent(id)}/verify`, { body: { approve } })
  store.update((d) => ({ ...d, completedCases: c.verificationStatus === 'rejected' ? d.completedCases.filter((x) => x.id !== id) : upsert(d.completedCases, c) }))
}

export async function loadSecurityEvents() {
  const log = await request<SecurityEvent[]>('/admin/security-events')
  store.update((d) => ({ ...d, securityLog: log }))
}

export const loadAudit = (action?: string, limit = 300) =>
  request<AuditEntry[]>(`/admin/audit?limit=${limit}${action ? `&action=${encodeURIComponent(action)}` : ''}`)

export interface AdminUser { id: string; name: string; email: string; role: string; status: string; isDemo: boolean; createdAt: string }
export const loadUsers = () => request<AdminUser[]>('/admin/users')

export interface SystemHealth {
  database: string; env: string; demoMode: boolean; llmProvider: string; kycProvider: string; fileEncryption: boolean
  counts: Record<string, number>; limits: Record<string, number>
}
export const loadHealth = () => request<SystemHealth>('/admin/health')
