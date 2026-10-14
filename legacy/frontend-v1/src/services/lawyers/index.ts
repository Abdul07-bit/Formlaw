import type { CompletedCase, IdType, Lawyer, Outcome, PracticeArea } from '../../types'
import { request } from '../api/client'
import { store, upsert } from '../store'

export async function loadDirectory() {
  const [lawyers, cases] = await Promise.all([request<Lawyer[]>('/lawyers', { auth: false }), request<CompletedCase[]>('/lawyer-cases', { auth: false })])
  store.update((d) => {
    // Keep private profiles (own / admin queue) that the public directory does not list.
    const extra = d.lawyers.filter((l) => !lawyers.some((x) => x.id === l.id) && (l.kycSubmission || l.id === d.session?.lawyerId))
    const mine = d.completedCases.filter((c) => !c.verified)
    return { ...d, lawyers: [...lawyers, ...extra], completedCases: [...cases, ...mine.filter((m) => !cases.some((c) => c.id === m.id))] }
  })
}

export async function loadMyProfile() {
  const [me, mine] = await Promise.all([request<Lawyer>('/lawyers/me'), request<CompletedCase[]>('/lawyers/me/cases')])
  store.update((d) => ({
    ...d, lawyers: upsert(d.lawyers, me),
    completedCases: [...mine, ...d.completedCases.filter((c) => !mine.some((m) => m.id === c.id))],
  }))
  return me
}

export interface ProfilePatch {
  name?: string; title?: Lawyer['title']; city?: string; state?: string; courts?: string[]; barCouncil?: string; enrolmentNo?: string
  experienceYears?: number; practiceAreas?: PracticeArea[]; languages?: string[]; consultationFee?: number; hearingFee?: number
  responseHours?: number; bio?: string
}

export async function updateMyProfile(patch: ProfilePatch) {
  const me = await request<Lawyer>('/lawyers/me', { method: 'PATCH', body: patch })
  store.update((d) => ({ ...d, lawyers: upsert(d.lawyers, me) }))
  return me
}

/** Documents go to the server; the KYC provider runs there. The browser never decides "verified". */
export async function submitKyc(input: { idType: IdType; degree: File; idCard: File; selfie: Blob }) {
  const form = new FormData()
  form.append('idType', input.idType)
  form.append('degreeCertificate', input.degree)
  form.append('idCard', input.idCard)
  form.append('selfie', input.selfie, input.selfie instanceof File ? input.selfie.name : 'selfie.jpg')
  const me = await request<Lawyer>('/kyc/submissions', { form })
  store.update((d) => ({ ...d, lawyers: upsert(d.lawyers, me) }))
  return me
}

export interface LawyerCaseInput {
  title: string; area: PracticeArea; court: string; year: number; outcome: Outcome; sections: string[]; summary: string
  keywords: string[]; durationMonths: number
}

export async function submitLawyerCase(input: LawyerCaseInput) {
  const rec = await request<CompletedCase>('/lawyers/me/cases', { body: input })
  store.update((d) => ({ ...d, completedCases: [rec, ...d.completedCases] }))
  return rec
}
