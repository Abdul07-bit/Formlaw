import { z } from 'zod'

export const UserSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string(),
  role: z.enum(['lawyer', 'client', 'admin', 'compliance']),
  city: z.string().nullable().optional(),
  lawyerId: z.string().nullable().optional(),
  organizationId: z.string(),
  organizationName: z.string().default(''),
  verificationStatus: z.string().nullable().optional(),
  isDemo: z.boolean().default(false),
})
export type User = z.infer<typeof UserSchema>

const Citation = z.object({
  chunkId: z.string(),
  documentId: z.string(),
  documentName: z.string(),
  page: z.number(),
  paragraph: z.number(),
  section: z.string().nullable().optional(),
  quote: z.string(),
})
export type Citation = z.infer<typeof Citation>

export const ClaimStatus = z.enum(['SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNSUPPORTED', 'CONTRADICTED', 'UNVERIFIED'])
export type ClaimStatus = z.infer<typeof ClaimStatus>

const Claim = z.object({
  id: z.string(),
  text: z.string(),
  kind: z.string(),
  agent: z.string(),
  status: ClaimStatus,
  confidence: z.enum(['high', 'medium', 'low']),
  reason: z.string(),
  citations: z.array(Citation),
  meta: z.record(z.unknown()).default({}),
})
export type RunClaim = z.infer<typeof Claim>

const Side = z.object({ value: z.string(), statement: z.string(), citation: Citation.nullable() })
const Contradiction = z.object({
  id: z.string(),
  topic: z.string(),
  nature: z.string(),
  confidence: z.string(),
  explanation: z.string(),
  a: Side,
  b: Side,
  provenance: z
    .object({
      sides: z.record(z.object({ document: z.string(), docType: z.string(), page: z.number(), role: z.string() })).optional(),
      corroboration: z.record(z.array(z.object({ chunkId: z.string(), document: z.string(), page: z.number() }))).optional(),
      assessment: z.string().optional(),
    })
    .passthrough()
    .default({}),
})
export type RunContradiction = z.infer<typeof Contradiction>

const Missing = z.object({
  id: z.string(),
  title: z.string(),
  why: z.string(),
  basis: z.string(),
  importance: z.string(),
  citation: Citation.nullable(),
})
export type RunMissing = z.infer<typeof Missing>

const Timeline = z.object({
  id: z.string(),
  dateText: z.string(),
  date: z.string().nullable(),
  description: z.string(),
  eventType: z.string(),
  status: z.string(),
  citation: Citation.nullable(),
})
export type RunTimeline = z.infer<typeof Timeline>

const Authority = z.object({
  id: z.string(),
  type: z.string(),
  title: z.string(),
  citation: z.string().nullable(),
  court: z.string().nullable(),
  date: z.string().nullable(),
  page: z.number().nullable(),
  quote: z.string(),
  source: z.string(),
  sourceUrl: z.string().nullable(),
  license: z.string().nullable(),
  status: z.string(),
})
export type RunAuthority = z.infer<typeof Authority>

const Evidence = z.object({
  chunkId: z.string(),
  documentId: z.string(),
  documentName: z.string(),
  docType: z.string(),
  page: z.number(),
  paragraph: z.number(),
  section: z.string().nullable().optional(),
  text: z.string(),
  relevance: z.number(),
  securityFlags: z.array(z.string()),
})
export type RunEvidence = z.infer<typeof Evidence>

export const PlanStep = z.object({
  id: z.string(),
  agent: z.string(),
  action: z.string(),
  label: z.string(),
  status: z.string(),
  origin: z.string(),
  reason: z.string().default(''),
  summary: z.string().default(''),
})
export type PlanStep = z.infer<typeof PlanStep>

const Assessment = z.object({
  level: z.enum(['strong', 'partial', 'conflicting', 'insufficient', 'not_assessed']),
  label: z.string(),
  reason: z.string(),
})
export type RunAssessment = z.infer<typeof Assessment>

const Report = z.object({
  overview: z.object({
    title: z.string(),
    matterType: z.string(),
    fields: z.array(z.object({ key: z.string(), label: z.string(), value: z.string().nullable(), citation: Citation.nullable() })),
    provisions: z.array(z.object({ value: z.string(), citation: Citation.nullable() })),
    parties: z.array(z.object({ name: z.string(), role: z.string(), citation: Citation.nullable() })),
  }),
  nextSteps: z.array(z.string()),
  documents: z.object({ reviewed: z.array(z.string()), templates: z.array(z.string()), unreadable: z.array(z.string()), total: z.number() }),
  notFound: z.string(),
})
export type RunReport = z.infer<typeof Report>

export const RunResultSchema = z.object({
  runId: z.string(),
  intent: z.string(),
  topic: z.string().default(''),
  status: z.string(),
  stopReason: z.string().nullable().optional(),
  rationale: z.string().default(''),
  plan: z.array(PlanStep),
  answer: z.object({
    summary: z.string(),
    claimIds: z.array(z.string()),
    limitations: z.array(z.string()),
    confidence: z.object({ level: z.enum(['high', 'medium', 'low']), reason: z.string() }).optional(),
    assessment: Assessment.optional(),  // absent on answers saved before assessments existed
    requiresLawyerReview: z.boolean(),
    reviewReasons: z.array(z.string()),
  }),
  report: Report.nullable().optional(),
  claims: z.array(Claim),
  unverified: z.array(Claim),
  contradictions: z.array(Contradiction),
  missing: z.array(Missing),
  contractGaps: z.array(z.object({ title: z.string(), why: z.string() })).default([]),
  timeline: z.array(Timeline),
  authorities: z.array(Authority),
  draft: z
    .object({
      id: z.string().optional(),
      kind: z.string(),
      title: z.string(),
      body: z.string(),
      recommendations: z.array(z.string()),
    })
    .passthrough()
    .nullable(),
  evidence: z.array(Evidence),
  security: z.array(z.object({ kind: z.string(), source: z.string(), snippet: z.string(), chunkId: z.string().nullable(), action: z.string() })),
  actions: z.array(z.object({ kind: z.string(), label: z.string(), prompt: z.string().optional() })),
  stats: z.object({
    steps: z.number(),
    toolCalls: z.number(),
    replans: z.number(),
    tokens: z.number(),
    latencyMs: z.number(),
    engines: z.array(z.string()),
  }).passthrough(),
})
export type RunResult = z.infer<typeof RunResultSchema>

/** Validate a run result; on mismatch the UI shows an error instead of rendering unchecked data. */
export function parseRunResult(raw: unknown): RunResult | null {
  const r = RunResultSchema.safeParse(raw)
  if (!r.success) {
    console.error('Run result failed validation', r.error.issues.slice(0, 5))
    return null
  }
  return r.data
}

export interface Case {
  id: string
  reference: string
  title: string
  description: string
  matterType: string
  status: string
  jurisdiction: string
  court: string
  clientName: string
  isDemo: boolean
  documentCount: number
  flaggedDocuments: number
  myRole: string | null
  createdAt: string
  updatedAt: string
}

export interface CaseDocument {
  id: string
  filename: string
  mimeType: string
  size: number
  status: string
  statusNote: string | null
  pages: number | null
  uploadedAt: string
  source: string
  docType?: string
  contentHash?: string
  metadata?: { dates?: string[]; references?: string[] }
  securityFlags?: string[]
}

export interface Thread { id: string; title: string; createdAt: string; updatedAt: string | null }
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  runId: string | null
  result: unknown
  createdAt: string
  runStatus: string | null
}

export interface RunEvent {
  seq: number
  tMs: number
  type: string
  agent: string | null
  stepId: string | null
  summary: string
  data: Record<string, unknown>
}

export interface Lawyer {
  id: string
  name: string
  headline: string
  city: string
  state: string
  jurisdictions: string[]
  languages: string[]
  education: string[]
  qualifications: string[]
  bio: string
  experienceYears: number
  acceptingClients: boolean
  consultationFee: number | null
  feeRange?: { min: number | null; max: number | null } | null
  feesSelfDeclared?: boolean
  verificationStatus: string
  verifiedAreas: string[]
  practiceAreas: string[]
  judicialStatusVerified: boolean
  isDemo: boolean
  barCouncil?: string
  enrolmentNumber?: string
  profileStatus?: string
  verificationExpiresAt?: string | null
}

/** What clients and visitors receive: only identity/verification fields are guaranteed; the rest depend on the ConnectionPolicy. */
export type PublicLawyer = Pick<Lawyer, 'id' | 'name' | 'verificationStatus' | 'isDemo'> & Partial<Omit<Lawyer, 'id' | 'name' | 'verificationStatus' | 'isDemo'>>

export interface ConnectionPolicyPublic {
  source: 'default' | 'approved' | 'demo'
  version: number
  label: string
  features: { publicDiscovery: boolean; matching: boolean; clientRequests: boolean }
  showFees: boolean
  visibleProfileFields: string[]
  disclosures: string[]
  disclosureHash: string
}

export interface VerificationEvent { from: string; to: string; by: string; reason: string; at: string | null }

export const MATTER_TYPES = ['criminal', 'civil', 'contract', 'property', 'family', 'employment', 'corporate', 'consumer', 'cyber', 'constitutional', 'other'] as const
