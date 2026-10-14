// Shared domain types. These mirror the backend's Pydantic response schemas (backend/app/schemas, /api/openapi.json).

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
  city?: string | null
  lawyerId?: string | null
  isDemo?: boolean
}

export type IdType = 'Bar Council ID' | 'Aadhaar' | 'PAN' | 'Passport'

export interface KycCheck {
  type: 'government_id' | 'qualification' | 'professional_registration' | 'face_match' | 'judicial_status'
  status: 'pending' | 'passed' | 'failed' | 'manual_review'
  provider: string
  reference: string | null
  demo: boolean
}

// Written only by the server (KYC provider + admin decision). The browser can never set these.
export interface KycSubmission {
  degreeCertificate: string | null
  idCard: string | null
  idType: IdType | null
  faceMatchScore: number | null
  livenessPassed: boolean | null
  provider: string
  checks: KycCheck[]
  submittedAt: string
  reviewedAt?: string | null
  reviewNote?: string | null
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
  responseHours: number
  bio: string
  kyc: KycStatus
  profileStatus: 'draft' | 'published' | 'suspended'
  isDemo: boolean
  kycSubmission?: KycSubmission | null
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
  verificationStatus: 'pending' | 'verified' | 'rejected'
  isDemo: boolean
}

export interface CaseDocument {
  id: string
  name: string
  type: string
  size: number
  text: string // extracted text; empty unless you own the case
  extraction: 'live' | 'backend'
  processingStatus: 'received' | 'extracted' | 'needs_ocr' | 'quarantined' | 'failed'
  contentHash: string
  pages?: number | null
}

export type ClaimStatus = 'supported' | 'partial' | 'conflicted' | 'unsupported'

export interface Evidence {
  id: string
  docId: string
  docName: string
  page: number
  excerpt: string
  highlight: string
  contentHash?: string
}

export interface Fact {
  id: string
  label: string
  statement: string
  status: ClaimStatus
  verificationStatus?: 'SUPPORTED' | 'PARTIALLY_SUPPORTED' | 'UNSUPPORTED' | 'CONTRADICTED' | 'UNVERIFIED'
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
  kind: 'prompt_injection' | 'tool_request' | 'exfiltration' | 'malicious_file' | 'auth_abuse'
  snippet: string
  risk: 'HIGH' | 'MEDIUM'
  actions: string[]
  at: string
  caseId?: string | null
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
  legalPipeline?: LegalPipeline | null
  feeDisclaimer: string
}

// Output of the original six-agent system (Research → Drafting → Verification), attached to an analysis.
export interface LegalPipeline {
  docType: string
  release_status: string
  review?: Record<string, unknown>
  research?: { relevant_laws?: { doc_id: string; title: string; section?: string; source_url?: string }[]; relevant_judgments?: { doc_id: string; title: string; citation?: string; holding?: string }[] }
  draft?: Record<string, unknown> & { document_title?: string; status?: string; error?: string }
  verification?: { approved: boolean; final_result: string; verified_claims: unknown[]; unsupported_claims: unknown[]; missing_information: unknown[] }
  audit_log?: { time: string; step: string; agent: string; status: string; detail: string }[]
  warnings?: string[]
  error?: string
}

export interface ClientCase {
  id: string
  ownerId: string
  title: string
  description: string
  city: string
  budget: number
  documents: CaseDocument[]
  status: 'open' | 'processing' | 'reviewed' | 'archived'
  analysis?: Analysis | null
  connectedLawyerIds: string[]
  createdAt: string
  isDemo?: boolean
  access: 'owner' | 'counsel'
}

export type ConnectionStatus = 'requested' | 'accepted' | 'declined' | 'closed'

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
  quote?: number | null
  messages: Message[]
  updatedAt: string
}

export interface ChatAnswer {
  status: 'supported' | 'conflicted' | 'insufficient'
  text: string
  evidenceIds: string[]
  evidence: Evidence[]
  sources: string[]
  note?: string | null
  steps: string[]
  engine: 'extractive' | 'llm'
}

export type ApprovalAction = 'connection.request' | 'draft.share' | 'case.delete' | 'document.delete'

export interface Approval {
  id: string
  action: ApprovalAction
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH'
  resourceType: string
  resourceId: string
  summary: string
  status: 'pending' | 'approved' | 'rejected' | 'executed' | 'expired'
  createdAt: string
  decidedAt?: string | null
  result?: Record<string, string> | null
}

export type AuthorityKind = 'constitution_article' | 'statute_section' | 'rule' | 'regulation' | 'judgment'

export interface Authority {
  id: string
  kind: AuthorityKind
  title: string
  reference: string | null
  court?: string | null
  date?: string | null
  text: string
  sourceName: string
  sourceUrl: string | null
  contentHash: string
  score: number
  citation?: string | null
  neutralCitation?: string | null
  caseNumber?: string | null
  page?: number | null
  documentUrl?: string | null
  sourceStatus?: 'APPROVED' | 'REVIEW_REQUIRED' | 'REJECTED' | null
  dataClass?: 'VERIFIED_SOURCE' | 'SYNTHETIC'
  license?: string | null
}

export interface ResearchResult { query: string; results: Authority[]; note?: string | null }

export interface LegalEvidence {
  evidenceId: string; documentId: string; documentName: string; kind?: string | null; court?: string | null; date?: string | null
  citation?: string | null; neutralCitation?: string | null; caseNumber?: string | null; page?: number | null; text: string
  source?: string | null; sourceKey?: string | null; sourceStatus?: string | null; sourceUrl?: string | null; documentUrl?: string | null
  license?: string | null; attribution?: string | null; contentHash?: string | null; documentHash?: string | null; dataClass: string
}

export interface LegalAnswer {
  status: 'SUPPORTED' | 'NOT_FOUND' | 'INSUFFICIENT_EVIDENCE'
  answer: string
  claims: { text: string; evidenceIds: string[]; status: string }[]
  evidence: LegalEvidence[]
  note?: string | null
  engine: 'extractive' | 'llm'
}

export interface CorpusStats {
  totals: { documents: number; judgments: number; statutes: number; constitution_provisions: number; courts: number
    sources_with_data: number; coverage: string | null; chunks: number; embedded_chunks: number; quarantined: number }
  sources: { source: string; name: string; status: string; documents: number; coverage: string; quarantined: number }[]
}

export interface AuditEntry {
  id: string; at: string; taskId: string | null; actorId: string | null; actorRole: string | null; action: string
  resourceType: string | null; resourceId: string | null; risk: 'LOW' | 'MEDIUM' | 'HIGH'; result: string; agent: string | null
  tool: string | null; latencyMs: number | null; verificationStatus: string | null; securityEventId: string | null; detail: string | null
}
