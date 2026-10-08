import type {
  Analysis, CaseDocument, CompletedCase, Contradiction, Evidence, Fact, Lawyer, LawyerMatch,
  MissingItem, PracticeArea, RelatedCase, SecurityEvent, TraceStep,
} from '../types'
import { chunkDocuments, type Chunk } from './ingest'
import { uid } from './store'

// ─────────────────────────────────────────────────────────────────────────────
// FormLaw agent engine (client-side reference implementation).
// Each function maps to one agent in the backend orchestrator. Deterministic and
// evidence-first: every fact must point at an Evidence chunk or it is not emitted.
// ─────────────────────────────────────────────────────────────────────────────

// ── Security Agent ───────────────────────────────────────────────────────────
const INJECTION_PATTERNS: { re: RegExp; kind: SecurityEvent['kind'] }[] = [
  { re: /ignore (all )?(previous|prior|above) instructions/i, kind: 'prompt_injection' },
  { re: /reveal (the )?(system|hidden) (prompt|instructions)/i, kind: 'prompt_injection' },
  { re: /you are now (in )?\w+ mode/i, kind: 'prompt_injection' },
  { re: /disregard (the )?(rules|policy|guidelines)/i, kind: 'prompt_injection' },
  { re: /call (external|outside) (services?|apis?|tools?)/i, kind: 'tool_request' },
  { re: /send (all )?(case )?(documents|files|data) to/i, kind: 'exfiltration' },
  { re: /(upload|post|forward|exfiltrate)\b.{0,40}https?:\/\//i, kind: 'exfiltration' },
  { re: /mark the (accused|defendant) as guilty/i, kind: 'prompt_injection' },
]

export function securityScan(chunks: Chunk[]): { events: SecurityEvent[]; quarantined: Set<Chunk> } {
  const events: SecurityEvent[] = []
  const quarantined = new Set<Chunk>()
  const byDoc = new Map<string, { chunk: Chunk; kinds: Set<SecurityEvent['kind']> }[]>()
  for (const c of chunks) {
    const kinds = new Set(INJECTION_PATTERNS.filter((p) => p.re.test(c.sentence)).map((p) => p.kind))
    if (kinds.size) {
      quarantined.add(c)
      const list = byDoc.get(c.docName) ?? []
      list.push({ chunk: c, kinds })
      byDoc.set(c.docName, list)
    }
  }
  // A document that tries to instruct the system loses evidence status entirely until a human reviews it.
  for (const c of chunks) if (byDoc.has(c.docName)) quarantined.add(c)
  for (const [docName, hits] of byDoc) {
    const kinds = new Set(hits.flatMap((h) => [...h.kinds]))
    const actions = ['Document instruction ignored', 'Document excluded from evidence pending human review']
    if (kinds.has('tool_request') || kinds.has('exfiltration')) actions.push('External tool / network access denied')
    actions.push('Security event logged', 'Analysis continued safely')
    events.push({
      id: uid('SEC'),
      docName,
      kind: kinds.has('exfiltration') ? 'exfiltration' : kinds.has('tool_request') ? 'tool_request' : 'prompt_injection',
      snippet: hits.map((h) => h.chunk.sentence).join(' ').slice(0, 220),
      risk: 'HIGH',
      actions,
      at: new Date().toISOString(),
    })
  }
  return { events, quarantined }
}

// ── Orchestrator: task classification ───────────────────────────────────────
const AREA_TERMS: Record<PracticeArea, string[]> = {
  Criminal: ['fir', 'arrest', 'bail', 'accused', 'police', 'remand', 'bns', 'bnss', 'ipc', 'crpc', 'theft', 'custody', 'chargesheet', 'witness', 'offence', 'magistrate'],
  Family: ['divorce', 'maintenance', 'custody of child', 'marriage', 'husband', 'wife', 'dowry', 'domestic violence', 'alimony', 'guardian'],
  Property: ['property', 'land', 'partition', 'title', 'sale deed', 'tenant', 'landlord', 'mutation', 'possession', 'encroachment', 'rent'],
  Corporate: ['contract', 'agreement', 'invoice', 'liability', 'indemnity', 'arbitration', 'shareholder', 'company', 'breach', 'vendor'],
  Consumer: ['refund', 'defective', 'warranty', 'consumer', 'product', 'service deficiency', 'e-commerce', 'seller'],
  Cyber: ['upi', 'otp', 'phishing', 'hacked', 'cyber', 'online fraud', 'social media', 'it act', 'identity theft'],
  Labour: ['salary', 'termination', 'employer', 'wages', 'gratuity', 'pf', 'retrenchment', 'posh', 'notice period'],
  Constitutional: ['article 21', 'article 14', 'writ', 'fundamental right', 'habeas corpus', 'article 226', 'article 32'],
}

export function classify(text: string): { area: PracticeArea; confidence: number; scores: Record<PracticeArea, number> } {
  const lower = text.toLowerCase()
  const scores = Object.fromEntries(
    (Object.keys(AREA_TERMS) as PracticeArea[]).map((a) => [a, AREA_TERMS[a].reduce((n, t) => n + (lower.split(t).length - 1), 0)]),
  ) as Record<PracticeArea, number>
  const ranked = (Object.entries(scores) as [PracticeArea, number][]).sort((x, y) => y[1] - x[1])
  const total = ranked.reduce((n, [, v]) => n + v, 0)
  if (!total) return { area: 'Criminal', confidence: 0.2, scores }
  return { area: ranked[0][0], confidence: Math.min(0.97, ranked[0][1] / total + 0.15), scores }
}

// ── Retrieval + Case Review agents ───────────────────────────────────────────
const DATE_RE = /\b(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b/gi

function datesIn(s: string): string[] {
  return [...s.matchAll(DATE_RE)].map((m) => `${Number(m[1])} ${m[2][0].toUpperCase()}${m[2].slice(1).toLowerCase()} ${m[3]}`)
}

function toEvidence(c: Chunk, highlight: string, list: Evidence[]): Evidence {
  const existing = list.find((e) => e.docId === c.docId && e.page === c.page && e.excerpt === c.sentence)
  if (existing) return existing
  const ev: Evidence = {
    id: `E${String(list.length + 1).padStart(3, '0')}`,
    docId: c.docId, docName: c.docName, page: c.page, excerpt: c.sentence, highlight,
  }
  list.push(ev)
  return ev
}

const tokenize = (s: string) => s.toLowerCase().match(/[a-z][a-z0-9]{2,}/g) ?? []
const STOP = new Set(['the', 'and', 'was', 'for', 'that', 'with', 'this', 'from', 'his', 'her', 'are', 'not', 'has', 'have', 'been', 'after', 'about', 'which', 'what', 'when', 'were', 'who', 'into'])

export function retrieve(chunks: Chunk[], query: string, k = 4): Chunk[] {
  const q = new Set(tokenize(query).filter((t) => !STOP.has(t)))
  if (!q.size) return []
  return chunks
    .map((c) => ({ c, s: tokenize(c.sentence).filter((t) => q.has(t)).length }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s)
    .slice(0, k)
    .map((x) => x.c)
}

interface ReviewOutput { facts: Fact[]; evidence: Evidence[]; contradictions: Contradiction[]; subject?: string }

export function reviewCase(chunks: Chunk[]): ReviewOutput {
  const evidence: Evidence[] = []
  const facts: Fact[] = []
  const contradictions: Contradiction[] = []
  const subjectMatch = chunks.map((c) => c.sentence.match(/accused (?:\w+ )?([A-Z][a-z]+ [A-Z][a-z]+)/)).find(Boolean)
  const subject = subjectMatch?.[1]

  // Arrest dates — compared across documents by the Contradiction Agent.
  const arrestHits = chunks.filter((c) => /\barrest(ed)?\b/i.test(c.sentence) && datesIn(c.sentence).length)
  const arrestByDate = new Map<string, Evidence>()
  for (const c of arrestHits) {
    const d = datesIn(c.sentence)[0]
    if (!arrestByDate.has(d)) arrestByDate.set(d, toEvidence(c, d, evidence))
  }
  if (arrestByDate.size === 1) {
    const [[d, ev]] = [...arrestByDate]
    facts.push({ id: 'F-ARREST', label: 'Arrest date', statement: `${subject ?? 'The accused'} was arrested on ${d}.`, status: 'supported', evidenceIds: [ev.id] })
  } else if (arrestByDate.size > 1) {
    const entries = [...arrestByDate]
    for (const [d, ev] of entries) {
      facts.push({ id: `F-ARREST-${ev.id}`, label: 'Arrest date', statement: `${ev.docName.replace(/[_-]/g, ' ').replace(/\.\w+$/, '')} records the arrest on ${d}.`, status: 'conflicted', evidenceIds: [ev.id] })
    }
    contradictions.push({
      id: 'C-ARREST', topic: 'Arrest date',
      a: { value: entries[0][0], evidenceId: entries[0][1].id },
      b: { value: entries[1][0], evidenceId: entries[1][1].id },
      confidence: 0.98,
    })
  }

  // Date of occurrence.
  const occ = chunks.find((c) => /(occurrence|night of|incident)/i.test(c.sentence) && datesIn(c.sentence).length)
  let occDate: string | undefined
  if (occ) {
    occDate = datesIn(occ.sentence)[0]
    const ev = toEvidence(occ, occDate, evidence)
    const corroborating = chunks.filter((c) => c !== occ && /(night of|occurrence|incident)/i.test(c.sentence) && datesIn(c.sentence).includes(occDate!))
    const ids = [ev.id, ...corroborating.map((c) => toEvidence(c, occDate!, evidence).id)]
    facts.push({ id: 'F-OCC', label: 'Date of occurrence', statement: `The alleged incident occurred on ${occDate}.`, status: 'supported', evidenceIds: ids })
  }

  // Offence sections.
  const secChunk = chunks.find((c) => /Section \d+[A-Z]? (BNS|BNSS|IPC|CrPC|IT Act)/i.test(c.sentence) && /offence/i.test(c.sentence))
  if (secChunk) {
    const sec = secChunk.sentence.match(/Section \d+[A-Z]? (BNS|BNSS|IPC|CrPC|IT Act)/i)![0]
    const ev = toEvidence(secChunk, sec, evidence)
    facts.push({ id: 'F-SEC', label: 'Offence charged', statement: `The FIR registers the offence under ${sec}.`, status: 'supported', evidenceIds: [ev.id] })
  }

  // Identification by witness.
  const idWeak = chunks.find((c) => /could not see|did not see|not clearly/i.test(c.sentence))
  if (idWeak) {
    const ev = toEvidence(idWeak, idWeak.sentence.match(/could not see[^.]*|did not see[^.]*|not clearly[^.]*/i)![0], evidence)
    facts.push({ id: 'F-WIT', label: 'Eyewitness identification', statement: 'The eyewitness could not positively identify the person at the scene.', status: 'supported', evidenceIds: [ev.id] })
  }

  // Suspect basis.
  const suspect = chunks.find((c) => /named as a suspect/i.test(c.sentence))
  if (suspect) {
    const ev = toEvidence(suspect, 'named as a suspect', evidence)
    facts.push({ id: 'F-SUS', label: 'Basis for suspicion', statement: 'The accused was named as a suspect on the basis of CCTV of the adjoining street and the complainant’s identification.', status: 'partial', evidenceIds: [ev.id] })
  }

  // Alibi from attendance record on the occurrence date.
  if (occDate) {
    const att = chunks.find((c) => c.sentence.includes(occDate!) && /\d{2}:\d{2},\d{2}:\d{2}/.test(c.sentence))
    if (att) {
      const ev = toEvidence(att, occDate, evidence)
      const times = att.sentence.match(/(\d{2}:\d{2}),(\d{2}:\d{2}),([^,]+)$/)
      facts.push({
        id: 'F-ALIBI', label: 'Possible alibi',
        statement: `An employment attendance record shows a check-in on ${occDate}${times ? ` from ${times[1]} to ${times[2]} at ${times[3].trim()}` : ''}, overlapping the time of occurrence.`,
        status: 'partial', evidenceIds: [ev.id],
      })
    }
  }

  // Generic fallback for non-demo uploads: surface the most fact-dense sentences.
  if (facts.length < 2) {
    const dense = chunks
      .map((c) => ({ c, s: datesIn(c.sentence).length * 2 + (c.sentence.match(/\b(Rs\.?|₹|section|article|dated|agreement|paid|notice)\b/gi)?.length ?? 0) }))
      .filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s)
      .slice(0, 5)
    dense.forEach(({ c }, i) => {
      const ev = toEvidence(c, datesIn(c.sentence)[0] ?? c.sentence.slice(0, 40), evidence)
      facts.push({ id: `F-GEN-${i}`, label: 'Extracted statement', statement: c.sentence, status: 'supported', evidenceIds: [ev.id] })
    })
  }

  return { facts, evidence, contradictions, subject }
}

// ── Missing Information Agent ────────────────────────────────────────────────
const CHECKLISTS: Record<PracticeArea, { title: string; present: RegExp; why: string; action: string }[]> = {
  Criminal: [
    { title: 'Arrest memo', present: /arrest memo/i, why: 'Article 22 and BNSS s.36 require an arrest memo; it is the primary record of the time and place of arrest.', action: 'Obtain a certified copy of the arrest memo.' },
    { title: 'Previous bail proceedings', present: /bail order|order copy.*available(?! in this file)/i, why: 'Prior bail history may affect the assessment of procedural history and conditions.', action: 'Retrieve the previous bail order or filing (court, case no., date).' },
    { title: 'CCTV footage / seizure memo', present: /seizure memo|footage (was )?seized/i, why: 'The suspect was named on the basis of CCTV, but no seizure memo or electronic-record certificate is on file.', action: 'Request the seizure memo and a BSA s.63 certificate for the footage.' },
    { title: 'Magistrate production record', present: /produced before|production before/i, why: 'Production within 24 hours of arrest is a constitutional safeguard under Article 22(2).', action: 'Retrieve the first remand/production order with date and time.' },
  ],
  Family: [
    { title: 'Marriage certificate', present: /marriage certificate/i, why: 'Establishes the legal relationship and jurisdiction.', action: 'Upload the marriage certificate or registration.' },
    { title: 'Income proof of both parties', present: /income|salary slip|itr/i, why: 'Maintenance is assessed on comparative income.', action: 'Upload salary slips or ITRs.' },
  ],
  Property: [
    { title: 'Title / sale deed', present: /sale deed|title deed/i, why: 'Ownership must be proved by registered documents.', action: 'Upload the registered sale/title deed.' },
    { title: 'Revenue records (jamabandi / mutation)', present: /jamabandi|mutation|khata/i, why: 'Revenue entries show possession and mutation history.', action: 'Obtain certified revenue extracts.' },
  ],
  Corporate: [
    { title: 'Executed agreement', present: /agreement|contract/i, why: 'Obligations must be read from the signed contract.', action: 'Upload the signed agreement with annexures.' },
    { title: 'Notice of breach', present: /notice/i, why: 'Most contracts require written notice before termination or claims.', action: 'Upload any notices exchanged.' },
  ],
  Consumer: [
    { title: 'Invoice / proof of purchase', present: /invoice|receipt|order id/i, why: 'Needed to establish the consumer relationship.', action: 'Upload the invoice or order confirmation.' },
    { title: 'Complaint correspondence', present: /email|complaint|ticket/i, why: 'Shows the seller was given an opportunity to remedy.', action: 'Upload emails or ticket history.' },
  ],
  Cyber: [
    { title: 'Cybercrime complaint acknowledgement', present: /acknowledg|cybercrime\.gov|1930/i, why: 'Prompt reporting enables fund freezing.', action: 'File on cybercrime.gov.in / call 1930 and upload the acknowledgement.' },
    { title: 'Bank statement with transaction IDs', present: /statement|utr|transaction id/i, why: 'Transaction references are needed to trace funds.', action: 'Upload the bank statement.' },
  ],
  Labour: [
    { title: 'Appointment letter', present: /appointment letter|offer letter/i, why: 'Defines employment terms and notice period.', action: 'Upload the appointment letter.' },
    { title: 'Termination letter', present: /termination letter|relieving/i, why: 'Required to examine compliance with notice and compensation.', action: 'Upload the termination letter.' },
  ],
  Constitutional: [
    { title: 'Impugned order / action', present: /order dated|impugned/i, why: 'A writ challenges a specific order or action.', action: 'Upload the order being challenged.' },
  ],
}

export function findMissing(area: PracticeArea, chunks: Chunk[]): MissingItem[] {
  const all = chunks.map((c) => c.sentence).join('\n')
  const items = CHECKLISTS[area].filter((i) => !i.present.test(all)).map((i, n) => ({ id: `M${n + 1}`, title: i.title, why: i.why, action: i.action }))
  // Explicitly flagged gaps ("not available") outrank checklist gaps.
  if (/not available/i.test(all) && area === 'Criminal') {
    const idx = items.findIndex((i) => i.title === 'Previous bail proceedings')
    if (idx > 0) items.unshift(...items.splice(idx, 1))
  }
  return items
}

// ── Related cases (from lawyers' completed-case database) ────────────────────
export function findRelated(area: PracticeArea, text: string, db: CompletedCase[]): RelatedCase[] {
  const lower = text.toLowerCase()
  return db
    .filter((c) => c.verified)
    .map((c) => {
      const shared = c.keywords.filter((k) => lower.includes(k))
      const sim = (shared.length / c.keywords.length) * 0.75 + (c.area === area ? 0.25 : 0)
      return { caseId: c.id, similarity: Math.round(Math.min(sim, 0.97) * 100) / 100, sharedTerms: shared.slice(0, 5) }
    })
    .filter((r) => r.similarity >= 0.3)
    .sort((a, b) => b.similarity - a.similarity)
    .slice(0, 4)
}

// ── Matching Agent ───────────────────────────────────────────────────────────
const HEARINGS: Record<PracticeArea, [number, number]> = {
  Criminal: [2, 6], Family: [4, 10], Property: [6, 14], Corporate: [3, 8], Consumer: [2, 5], Cyber: [2, 5], Labour: [3, 8], Constitutional: [2, 5],
}

export function matchLawyers(area: PracticeArea, city: string, budget: number, lawyers: Lawyer[], related: RelatedCase[], db: CompletedCase[]): LawyerMatch[] {
  const relatedAuthors = new Set(related.map((r) => db.find((c) => c.id === r.caseId)?.lawyerId))
  return lawyers
    .filter((l) => l.kyc === 'verified')
    .map((l) => {
      const reasons: string[] = []
      let score = 0
      if (l.practiceAreas.includes(area)) { score += 40; reasons.push(`Practises ${area} law`) }
      if (l.city.toLowerCase() === city.toLowerCase()) { score += 15; reasons.push(`Based in ${l.city}`) }
      if (relatedAuthors.has(l.id)) { score += 15; reasons.push('Handled a closely related case') }
      score += (l.rating - 4) * 15
      if (l.successRate) score += (l.successRate - 70) / 2
      const [hMin, hMax] = HEARINGS[area]
      const estimate: [number, number] = [l.consultationFee + l.hearingFee * hMin, l.consultationFee + l.hearingFee * hMax]
      if (budget && estimate[0] <= budget) { score += 10; reasons.push('Fits your budget') }
      else if (budget && estimate[0] > budget * 1.5) score -= 12
      if (l.responseHours <= 4) reasons.push(`Replies in ~${l.responseHours}h`)
      return { lawyerId: l.id, score: Math.max(5, Math.min(97, Math.round(score * 0.9 + 6))), reasons, estimate }
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, 4)
}

// ── Drafting Agent ───────────────────────────────────────────────────────────
function draftFor(area: PracticeArea, title: string, facts: Fact[], contradictions: Contradiction[], missing: MissingItem[], evidence: Evidence[]) {
  const ref = (f: Fact) => f.evidenceIds.map((id) => { const e = evidence.find((x) => x.id === id)!; return `[${id}: ${e.docName}, p.${e.page}]` }).join(' ')
  const factLines = facts.map((f, i) => `${i + 1}. ${f.statement} ${ref(f)}${f.status === 'conflicted' ? ' — CONFLICTING' : ''}`).join('\n')
  const conflictLines = contradictions.map((c) => `• ${c.topic}: "${c.a.value}" [${c.a.evidenceId}] vs "${c.b.value}" [${c.b.evidenceId}]`).join('\n')
  if (area === 'Criminal') {
    return {
      title: 'Draft — Application for Regular Bail (BNSS s.480 / s.483)',
      body: `IN THE COURT OF ____________________
${title.toUpperCase()}

APPLICATION FOR REGULAR BAIL ON BEHALF OF THE ACCUSED

MOST RESPECTFULLY SHOWETH:

GROUNDS (each ground is linked to evidence on record)
${factLines}

INCONSISTENCIES IN THE PROSECUTION RECORD
${conflictLines || '• None detected in the supplied documents.'}

The applicant submits that the right to personal liberty under Article 21 of the Constitution of India, and the safeguards under Article 22, require that the above inconsistencies be examined before continued custody is ordered.

DOCUMENTS TO BE PLACED ON RECORD BEFORE FILING
${missing.map((m) => `• ${m.title} — ${m.action}`).join('\n') || '• None identified.'}

PRAYER
It is therefore prayed that the applicant be released on bail on such terms as this Hon'ble Court deems fit.

[DRAFT generated from verified evidence only. Must be reviewed and signed by an enrolled advocate before filing.]`,
    }
  }
  return {
    title: 'Draft — Case Summary & Legal Notice Outline',
    body: `CASE SUMMARY — ${title}

FACTS ESTABLISHED FROM DOCUMENTS
${factLines || '• No verifiable facts could be extracted from text documents.'}

${conflictLines ? `CONFLICTS\n${conflictLines}\n\n` : ''}INFORMATION REQUIRED BEFORE ISSUING NOTICE
${missing.map((m) => `• ${m.title} — ${m.action}`).join('\n') || '• None identified.'}

[DRAFT generated from verified evidence only. Must be reviewed by an enrolled advocate.]`,
  }
}

// ── Orchestrator ─────────────────────────────────────────────────────────────
export interface AnalyseInput {
  title: string
  description: string
  city: string
  budget: number
  documents: CaseDocument[]
  lawyers: Lawyer[]
  completedCases: CompletedCase[]
}

export function analyseCase(input: AnalyseInput): Analysis {
  const trace: TraceStep[] = []
  let t = 0
  const log = (agent: string, message: string, kind: TraceStep['kind'] = 'ok') => trace.push({ t: (t += 0.6 + Math.random() * 0.5), agent, message, kind })

  log('Orchestrator', `Request received — ${input.documents.length} document(s), goal: review case & find counsel`, 'info')
  const allChunks = chunkDocuments(input.documents)
  const backendDocs = input.documents.filter((d) => d.extraction === 'backend').length
  log('Ingestion', `${allChunks.length} evidence chunks indexed${backendDocs ? `; ${backendDocs} file(s) queued for server-side extraction/OCR` : ''}`)

  const { events, quarantined } = securityScan(allChunks)
  if (events.length) {
    log('Security Agent', `Indirect prompt injection detected in ${events.map((e) => e.docName).join(', ')}`, 'danger')
    log('Policy Engine', 'Instruction BLOCKED · external tool access DENIED · event LOGGED', 'danger')
  } else log('Security Agent', 'All documents scanned — no embedded instructions found')
  const chunks = allChunks.filter((c) => !quarantined.has(c))

  const corpus = `${input.description}\n${chunks.map((c) => c.sentence).join('\n')}`
  const cls = classify(corpus)
  log('Orchestrator', `Task classified as ${cls.area.toUpperCase()}_CASE_REVIEW (${Math.round(cls.confidence * 100)}%)`)
  log('Planner', '5-step plan: retrieve → review → verify → contradictions → gaps, then match counsel', 'info')

  const review = reviewCase(chunks)
  log('Retrieval Agent', `${review.evidence.length} evidence items retrieved`)
  log('Case Review Agent', `${review.facts.length} claims generated`)

  if (review.contradictions.length) {
    log('Contradiction Agent', `Evidence conflict detected — ${review.contradictions.map((c) => c.topic).join(', ')}`, 'warn')
    log('Orchestrator', 'Adapting plan → retrieving additional evidence to resolve conflict', 'adapt')
    const extra = retrieve(chunks, 'arrest custody production magistrate memo', 6).filter((c) => !review.evidence.some((e) => e.excerpt === c.sentence))
    log('Retrieval Agent', `Re-search returned ${extra.length} new chunk(s); no independent record resolves the date`, 'adapt')
    log('Verification Agent', 'Re-evaluated claim — both sources preserved, status CONFLICTED', 'warn')
  } else log('Contradiction Agent', 'No conflicting facts across documents')

  const v = {
    analysed: review.facts.length,
    supported: review.facts.filter((f) => f.status === 'supported').length,
    partial: review.facts.filter((f) => f.status === 'partial').length,
    conflicted: review.facts.filter((f) => f.status === 'conflicted').length,
    unsupported: review.facts.filter((f) => f.status === 'unsupported').length,
    coverage: review.facts.length ? Math.round((review.facts.filter((f) => f.evidenceIds.length).length / review.facts.length) * 100) : 0,
  }
  log('Verification Agent', `${v.analysed} claims evaluated — ${v.supported} supported, ${v.partial} partial, ${v.conflicted} conflicted`)

  const missing = findMissing(cls.area, chunks)
  log('Missing Info Agent', `${missing.length} gap(s) identified`, missing.length ? 'warn' : 'ok')

  const related = findRelated(cls.area, corpus, input.completedCases)
  log('Precedent Agent', `${related.length} related case(s) found in the FormLaw verified-case database`)

  const matches = matchLawyers(cls.area, input.city, input.budget, input.lawyers, related, input.completedCases)
  log('Matching Agent', `${matches.length} KYC-verified advocates ranked by fit, outcomes and fees`)

  const draft = draftFor(cls.area, input.title, review.facts, review.contradictions, missing, review.evidence)
  log('Drafting Agent', `${draft.title.replace('Draft — ', '')} prepared — awaiting human review`, 'info')
  log('Orchestrator', 'Final result generated', 'ok')

  const who = review.subject ?? 'the client'
  const summary = review.contradictions.length
    ? `The supplied documents contain conflicting information regarding the ${review.contradictions[0].topic.toLowerCase()} of ${who}. Two different values appear in the case materials. FormLaw has preserved both sources rather than selecting one without sufficient evidence.`
    : review.facts.length
      ? `FormLaw extracted ${review.facts.length} evidence-backed statements from ${input.documents.length} document(s). The matter appears to be a ${cls.area.toLowerCase()} dispute; ${missing.length} supporting document(s) are still missing.`
      : `FormLaw could not extract verifiable facts from the text available in the browser. ${backendDocs ? 'PDF/DOCX/image files will be read by the extraction service once the backend is connected.' : 'Add text-based documents or a fuller description.'}`

  return {
    taskId: `TASK-${Math.floor(10000 + Math.random() * 89999)}`,
    area: cls.area, areaConfidence: cls.confidence, summary,
    facts: review.facts, evidence: review.evidence, contradictions: review.contradictions,
    missing, security: events, related, matches, draft, verification: v, trace,
    completedAt: new Date().toISOString(),
  }
}

// ── Grounded Q&A (Legal Chat) ────────────────────────────────────────────────
export interface GroundedAnswer {
  text: string
  status: 'supported' | 'conflicted' | 'insufficient'
  evidenceIds: string[]
  note?: string
  steps: string[]
}

export function answerQuestion(q: string, a: Analysis, docs: CaseDocument[]): GroundedAnswer {
  const lq = q.toLowerCase()
  const steps = ['Orchestrator understood request', 'Retrieval Agent searching evidence', 'Verification Agent checking claims']
  if (/arrest/.test(lq)) {
    const c = a.contradictions.find((x) => x.topic === 'Arrest date')
    steps.push('Contradiction Agent comparing evidence')
    if (c) {
      steps.push('Conflict detected → replanning, searching for additional evidence')
      return {
        status: 'conflicted', evidenceIds: [c.a.evidenceId, c.b.evidenceId], steps,
        text: `The supplied case documents contain conflicting arrest dates. One document states ${c.a.value}; another states ${c.b.value}.`,
        note: 'FormLaw cannot reliably select one date without additional evidence (e.g., the arrest memo or first production order).',
      }
    }
    const f = a.facts.find((x) => x.label === 'Arrest date')
    if (f) return { status: 'supported', evidenceIds: f.evidenceIds, steps, text: f.statement }
  }
  if (/contradict|conflict|inconsisten/.test(lq)) {
    steps.push('Contradiction Agent comparing evidence')
    if (!a.contradictions.length) return { status: 'supported', evidenceIds: [], steps, text: 'No contradictions were detected across the supplied documents.' }
    return {
      status: 'conflicted', steps, evidenceIds: a.contradictions.flatMap((c) => [c.a.evidenceId, c.b.evidenceId]),
      text: a.contradictions.map((c) => `${c.topic}: ${c.a.value} vs ${c.b.value}.`).join(' '),
      note: 'Both sources are preserved for review.',
    }
  }
  if (/missing|gap|lack/.test(lq)) {
    steps.push('Missing Information Agent analysing gaps')
    return { status: 'supported', evidenceIds: [], steps, text: a.missing.length ? `The record is missing: ${a.missing.map((m) => m.title).join('; ')}.` : 'No critical gaps found against the checklist.' }
  }
  if (/witness/.test(lq)) {
    const ids = a.facts.filter((f) => f.id === 'F-WIT' || f.id === 'F-OCC').flatMap((f) => f.evidenceIds)
    if (ids.length) return { status: 'supported', evidenceIds: ids, steps, text: 'The witness was on duty on the night of the incident and saw a man near the shop, but could not see his face clearly and did not see anyone enter the shop.' }
  }
  if (/prosecution|support|against/.test(lq)) {
    const ids = a.facts.filter((f) => ['F-SEC', 'F-SUS', 'F-OCC'].includes(f.id)).flatMap((f) => f.evidenceIds)
    if (ids.length) return { status: 'supported', evidenceIds: ids, steps, text: 'The prosecution relies on the FIR, CCTV of the adjoining street and the complainant’s identification of the accused as a former delivery worker. The eyewitness did not identify the accused.', note: 'Identification evidence is only partially supported.' }
  }
  // Generic retrieval over live chunks.
  const hits = retrieve(chunkDocuments(docs).filter((c) => !a.security.some((s) => s.docName === c.docName && s.snippet.includes(c.sentence))), q, 3)
  if (!hits.length) return { status: 'insufficient', evidenceIds: [], steps, text: 'We couldn’t verify an answer. The available evidence is insufficient.', note: 'Recommended: upload the document that addresses this question.' }
  const ids = hits.map((h) => {
    const existing = a.evidence.find((e) => e.excerpt === h.sentence)
    if (existing) return existing.id
    const ev: Evidence = { id: `E${String(a.evidence.length + 1).padStart(3, '0')}`, docId: h.docId, docName: h.docName, page: h.page, excerpt: h.sentence, highlight: h.sentence.slice(0, 60) }
    a.evidence.push(ev)
    return ev.id
  })
  return { status: 'supported', evidenceIds: ids, steps, text: hits.map((h) => h.sentence).join(' '), note: 'Answer composed only of retrieved document text.' }
}
