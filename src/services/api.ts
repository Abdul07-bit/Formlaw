import type { ClientCase, CompletedCase, Conversation, KycSubmission, Lawyer, PracticeArea, Role, User } from '../types'
import { store, uid } from './store'
import { analyseCase } from './agents'
import { DEMO_CASE_TITLE, demoDocuments, maliciousDocument } from '../data/demoCase'

// API facade. Each function documents the FastAPI endpoint that will replace it.
// Components never touch the store directly for writes.

const now = () => new Date().toISOString()
export const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

// POST /api/auth/session
export function signIn(input: { name: string; email: string; role: Role; city?: string }): User {
  const db = store.get()
  const existing = db.users.find((u) => u.email.toLowerCase() === input.email.toLowerCase() && u.role === input.role)
  if (existing) {
    store.update((d) => ({ ...d, sessionUserId: existing.id }))
    return existing
  }
  const user: User = { id: uid('USR'), name: input.name.trim(), email: input.email.trim(), role: input.role, city: input.city }
  if (input.role === 'lawyer' || input.role === 'judge') {
    const lawyer: Lawyer = {
      id: uid('LAW'), name: user.name, title: input.role === 'judge' ? 'Retd. Judge' : 'Advocate', role: input.role,
      photoHue: 200, initials: user.name.split(/\s+/).map((p) => p[0]).join('').slice(0, 2).toUpperCase(),
      city: input.city ?? '', state: '', courts: [], barCouncil: '', enrolmentNo: '', experienceYears: 0,
      practiceAreas: [], languages: ['English'], consultationFee: 1500, hearingFee: 10000,
      rating: 0, reviews: 0, casesHandled: 0, successRate: 0, responseHours: 12, bio: '', kyc: 'not_started',
    }
    user.lawyerId = lawyer.id
    store.update((d) => ({ ...d, users: [...d.users, user], lawyers: [...d.lawyers, lawyer], sessionUserId: user.id }))
  } else {
    store.update((d) => ({ ...d, users: [...d.users, user], sessionUserId: user.id }))
  }
  return user
}

// Quick demo personas for judges.
export function demoLogin(role: 'client' | 'lawyer' | 'admin'): User {
  if (role === 'client') return signIn({ name: 'Priya Sharma', email: 'priya@demo.in', role: 'client', city: 'New Delhi' })
  const db = store.get()
  const user = role === 'admin' ? db.users.find((u) => u.role === 'admin')! : db.users.find((u) => u.lawyerId === 'LAW-101')!
  store.update((d) => ({ ...d, sessionUserId: user.id }))
  return user
}

export function signOut() {
  store.update((d) => ({ ...d, sessionUserId: null }))
}

// POST /api/lawyers/{id}/kyc  (multipart: degree, id card, selfie → object storage; face match server-side)
export async function submitKyc(lawyerId: string, profile: Partial<Lawyer>, submission: Omit<KycSubmission, 'submittedAt'>) {
  await wait(900)
  store.update((d) => ({
    ...d,
    lawyers: d.lawyers.map((l) => (l.id === lawyerId ? { ...l, ...profile, kyc: 'pending', kycSubmission: { ...submission, submittedAt: now() } } : l)),
  }))
}

// POST /api/admin/kyc/{id}/decision   (role: admin)
export function reviewKyc(lawyerId: string, approve: boolean, note: string) {
  store.update((d) => ({
    ...d,
    lawyers: d.lawyers.map((l) =>
      l.id === lawyerId && l.kycSubmission
        ? { ...l, kyc: approve ? 'verified' : 'rejected', rating: approve && !l.rating ? 4.5 : l.rating, kycSubmission: { ...l.kycSubmission, reviewedAt: now(), reviewNote: note } }
        : l,
    ),
  }))
}

// POST /api/lawyers/{id}/completed-cases   (PII must be anonymised before storage)
export function addCompletedCase(input: Omit<CompletedCase, 'id' | 'verified'>) {
  const rec: CompletedCase = { ...input, id: uid('FLC'), verified: false }
  store.update((d) => ({ ...d, completedCases: [rec, ...d.completedCases] }))
  return rec
}

// POST /api/admin/completed-cases/{id}/verify
export function verifyCompletedCase(id: string, approve: boolean) {
  store.update((d) => ({
    ...d,
    completedCases: approve ? d.completedCases.map((c) => (c.id === id ? { ...c, verified: true } : c)) : d.completedCases.filter((c) => c.id !== id),
  }))
}

// POST /api/cases
export function createCase(input: Pick<ClientCase, 'title' | 'description' | 'city' | 'budget' | 'documents'> & { isDemo?: boolean }): ClientCase {
  const user = currentUser()
  const c: ClientCase = { ...input, id: uid('CASE'), ownerId: user?.id ?? 'anonymous', connectedLawyerIds: [], createdAt: now() }
  store.update((d) => ({ ...d, cases: [c, ...d.cases] }))
  return c
}

export function createDemoCase(withMalicious = false): ClientCase {
  return createCase({
    title: withMalicious ? `${DEMO_CASE_TITLE} (security demo)` : DEMO_CASE_TITLE,
    description: 'My brother Arjun was arrested for a theft at a shop in Dwarka. He says he was at work that night. We need bail and a good criminal lawyer in Delhi.',
    city: 'New Delhi', budget: 150000, isDemo: true,
    documents: withMalicious ? [...demoDocuments, maliciousDocument] : demoDocuments,
  })
}

export function addDocuments(caseId: string, docs: ClientCase['documents']) {
  store.update((d) => ({ ...d, cases: d.cases.map((c) => (c.id === caseId ? { ...c, documents: [...c.documents, ...docs], analysis: undefined } : c)) }))
}

// POST /api/cases/{id}/review  → streams agent trace events (SSE) in the backend version.
export function runAnalysis(caseId: string) {
  const db = store.get()
  const c = db.cases.find((x) => x.id === caseId)
  if (!c) throw new Error('Case not found')
  const analysis = analyseCase({ ...c, lawyers: db.lawyers, completedCases: db.completedCases })
  store.update((d) => ({
    ...d,
    cases: d.cases.map((x) => (x.id === caseId ? { ...x, analysis } : x)),
    securityLog: [...analysis.security.map((s) => ({ ...s, docName: `${s.docName} · ${c.title}` })), ...d.securityLog],
  }))
  return analysis
}

// POST /api/connections
export function requestLawyer(caseId: string, lawyerId: string, note: string): Conversation {
  const db = store.get()
  const c = db.cases.find((x) => x.id === caseId)!
  const user = currentUser()
  const existing = db.conversations.find((x) => x.caseId === caseId && x.lawyerId === lawyerId)
  if (existing) return existing
  const conv: Conversation = {
    id: uid('CONV'), caseId, caseTitle: c.title, clientId: user?.id ?? c.ownerId, clientName: user?.name ?? 'Client', lawyerId,
    status: 'requested', updatedAt: now(),
    messages: [
      { id: uid('MSG'), from: 'system', text: `Case brief shared securely: ${c.analysis?.area ?? ''} matter · ${c.documents.length} documents · evidence summary attached.`, at: now() },
      ...(note.trim() ? [{ id: uid('MSG'), from: 'client' as const, text: note.trim(), at: now() }] : []),
    ],
  }
  store.update((d) => ({
    ...d,
    conversations: [conv, ...d.conversations],
    cases: d.cases.map((x) => (x.id === caseId ? { ...x, connectedLawyerIds: [...new Set([...x.connectedLawyerIds, lawyerId])] } : x)),
  }))
  return conv
}

// POST /api/connections/{id}/decision
export function respondToRequest(convId: string, accept: boolean, quote?: number) {
  store.update((d) => ({
    ...d,
    conversations: d.conversations.map((c) =>
      c.id === convId
        ? {
            ...c, status: accept ? 'accepted' : 'declined', quote, updatedAt: now(),
            messages: [...c.messages, { id: uid('MSG'), from: 'system', text: accept ? `Advocate accepted the brief${quote ? ` · proposed fee ₹${quote.toLocaleString('en-IN')}` : ''}. Chat is now open.` : 'Advocate declined this brief. FormLaw will suggest alternatives.', at: now() }],
          }
        : c,
    ),
  }))
}

// POST /api/connections/{id}/messages
export function sendMessage(convId: string, from: 'client' | 'lawyer', text: string) {
  const clean = text.trim().slice(0, 4000)
  if (!clean) return
  store.update((d) => ({
    ...d,
    conversations: d.conversations.map((c) => (c.id === convId ? { ...c, updatedAt: now(), messages: [...c.messages, { id: uid('MSG'), from, text: clean, at: now() }] } : c)),
  }))
}

export function updateLawyerProfile(lawyerId: string, patch: Partial<Lawyer>) {
  store.update((d) => ({ ...d, lawyers: d.lawyers.map((l) => (l.id === lawyerId ? { ...l, ...patch } : l)) }))
}

export function currentUser(): User | undefined {
  const db = store.get()
  return db.users.find((u) => u.id === db.sessionUserId)
}

export const ALL_AREAS: PracticeArea[] = ['Criminal', 'Family', 'Property', 'Corporate', 'Consumer', 'Cyber', 'Labour', 'Constitutional']

export const inr = (n: number) => `₹${Math.round(n).toLocaleString('en-IN')}`
