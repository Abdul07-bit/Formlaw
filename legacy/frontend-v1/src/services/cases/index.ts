import type { Analysis, CaseDocument, ChatAnswer, ClientCase } from '../../types'
import { request } from '../api/client'
import { store, upsert } from '../store'

interface CaseSummary { id: string }

const put = (c: ClientCase) => store.update((d) => ({ ...d, cases: upsert(d.cases, c, true) }))

export async function loadMyCases() {
  const list = await request<CaseSummary[]>('/cases')
  const full = await Promise.all(list.map((c) => request<ClientCase>(`/cases/${c.id}`)))
  store.update((d) => ({ ...d, cases: full }))
}

export async function loadCase(id: string) {
  const c = await request<ClientCase>(`/cases/${encodeURIComponent(id)}`)
  put(c)
  return c
}

export async function createCase(input: { title: string; description: string; city: string; budget: number }) {
  const c = await request<ClientCase>('/cases', { body: input })
  put(c)
  return c
}

export async function createDemoCase(malicious = false) {
  const c = await request<ClientCase>('/cases/demo', { body: { malicious } })
  put(c)
  return c
}

export async function uploadDocuments(caseId: string, files: File[]) {
  const form = new FormData()
  files.forEach((f) => form.append('files', f, f.name))
  const docs = await request<CaseDocument[]>(`/cases/${encodeURIComponent(caseId)}/documents`, { form })
  store.update((d) => ({ ...d, cases: d.cases.map((c) => (c.id === caseId ? { ...c, documents: [...c.documents, ...docs] } : c)) }))
  return docs
}

const withAnalysis = (caseId: string, a: Analysis) =>
  store.update((d) => ({ ...d, cases: d.cases.map((c) => (c.id === caseId ? { ...c, analysis: a, status: 'reviewed' } : c)) }))

/** Runs the multi-agent review on the server (review, verification, research, matching, statutory draft). */
export async function runReview(caseId: string) {
  const a = await request<Analysis>(`/cases/${encodeURIComponent(caseId)}/review`, { method: 'POST' })
  withAnalysis(caseId, a)
  await loadCase(caseId) // documents may have been quarantined
  return a
}

export async function createDraft(caseId: string, docType: string) {
  const a = await request<Analysis>(`/cases/${encodeURIComponent(caseId)}/draft`, { body: { docType } })
  withAnalysis(caseId, a)
  return a
}

export const askCase = (caseId: string, question: string, history: string[]) =>
  request<ChatAnswer>(`/cases/${encodeURIComponent(caseId)}/chat`, { body: { question, history: history.slice(-6) } })

export const DRAFT_TYPES = ['bail', 'anticipatory_bail', 'fir', 'petition_302', 'appeal', 'legal_notice', 'affidavit', 'vakalatnama', 'plaint', 'written_statement'] as const
export const draftLabel = (t: string) => t.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase()).replace('302', '(s.302)')
