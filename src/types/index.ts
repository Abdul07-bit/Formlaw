// Shared domain types. These mirror the API contract the backend should implement.

export type Role = 'client' | 'lawyer' | 'judge' | 'admin'

export type PracticeArea =
  | 'Criminal'
  | 'Family'
  | 'Property'
  | 'Corporate'
  | 'Consumer'
  | 'Cyber'
  | 'Labour'
  | 'Constitutional'

export type KycStatus = 'not_started' | 'pending' | 'verified' | 'rejected'

export interface User {
  id: string
  name: string
  email: string
  role: Role
  city?: string
  lawyerId?: string
}

export interface KycSubmission {
  degreeCertificate: string // file name only — files go to object storage via backend
  idCard: string
  idType: 'Bar Council ID' | 'Aadhaar' | 'PAN' | 'Passport'
  faceMatchScore: number
  livenessPassed: boolean
  submittedAt: string
  reviewedAt?: string
  reviewNote?: string
}

export interface Lawyer {
  id: string
  name: string
  title: 'Advocate' | 'Senior Advocate' | 'Retd. Judge'
  role: 'lawyer' | 'judge'
  photoHue: number
  initials: string
  city: string
  state: string
  courts: string[]
  barCouncil: string
  enrolmentNo: string
  experienceYears: number
  practiceAreas: PracticeArea[]
  languages: string[]
  consultationFee: number
  hearingFee: number
  rating: number
  reviews: number
  casesHandled: number
  successRate: number
  responseHours: number
  bio: string
  kyc: KycStatus
  kycSubmission?: KycSubmission
}

export type Outcome = 'Allowed' | 'Dismissed' | 'Settled' | 'Acquitted' | 'Convicted' | 'Bail granted' | 'Decree passed'

export interface CompletedCase {
  id: string
  lawyerId: string
  title: string // anonymised
  area: PracticeArea
  court: string
  year: number
  outcome: Outcome
  sections: string[]
  summary: string
  keywords: string[]
  durationMonths: number
  verified: boolean
}

export interface CaseDocument {
  id: string
  name: string
  type: string
  size: number
  text: string // extracted text (empty when extraction is backend-only)
  extraction: 'live' | 'backend'
  pages?: number
}

export type ClaimStatus = 'supported' | 'partial' | 'conflicted' | 'unsupported'

export interface Evidence {
  id: string
  docId: string
  docName: string
  page: number
  excerpt: string
  highlight: string
}

export interface Fact {
  id: string
  label: string
  statement: string
  status: ClaimStatus
  evidenceIds: string[]
}

export interface Contradiction {
  id: string
  topic: string
  a: { value: string; evidenceId: string }
  b: { value: string; evidenceId: string }
  confidence: number
}

export interface MissingItem {
  id: string
  title: string
  why: string
  action: string
}

export interface SecurityEvent {
  id: string
  docName: string
  kind: 'prompt_injection' | 'tool_request' | 'exfiltration'
  snippet: string
  risk: 'HIGH' | 'MEDIUM'
  actions: string[]
  at: string
}

export interface TraceStep {
  t: number
  agent: string
  message: string
  kind: 'info' | 'ok' | 'warn' | 'danger' | 'adapt'
}

export interface LawyerMatch {
  lawyerId: string
  score: number
  reasons: string[]
  estimate: [number, number]
}

export interface RelatedCase {
  caseId: string
  similarity: number
  sharedTerms: string[]
}

export interface Analysis {
  taskId: string
  area: PracticeArea
  areaConfidence: number
  summary: string
  facts: Fact[]
  evidence: Evidence[]
  contradictions: Contradiction[]
  missing: MissingItem[]
  security: SecurityEvent[]
  related: RelatedCase[]
  matches: LawyerMatch[]
  draft: { title: string; body: string }
  verification: { analysed: number; supported: number; partial: number; conflicted: number; unsupported: number; coverage: number }
  trace: TraceStep[]
  completedAt: string
}

export interface ClientCase {
  id: string
  ownerId: string
  title: string
  description: string
  city: string
  budget: number
  documents: CaseDocument[]
  analysis?: Analysis
  connectedLawyerIds: string[]
  createdAt: string
  isDemo?: boolean
}

export type ConnectionStatus = 'requested' | 'accepted' | 'declined'

export interface Message {
  id: string
  from: 'client' | 'lawyer' | 'system'
  text: string
  at: string
}

export interface Conversation {
  id: string
  caseId: string
  caseTitle: string
  clientId: string
  clientName: string
  lawyerId: string
  status: ConnectionStatus
  quote?: number
  messages: Message[]
  updatedAt: string
}
