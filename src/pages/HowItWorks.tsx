import { AnimatePresence, motion } from 'framer-motion'
import {
  Bot, BrainCircuit, ClipboardCheck, Database, FileSearch, FileSignature, GitCompareArrows, Handshake, KeyRound,
  Lock, Network, ScrollText, Search, ShieldAlert, ShieldCheck, User, UserCheck, Workflow,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { ConstitutionArt } from '../components/art'
import { Badge, cx, DemoTag, PageHeader } from '../components/ui'

interface Agent { id: string; name: string; icon: ReactNode; purpose: string; inputs: string; outputs: string; perms: string; tools: string; risk: 'LOW' | 'MEDIUM' | 'HIGH'; verification: string; status: 'live' | 'simulated' | 'future' }

const AGENTS: Agent[] = [
  { id: 'orc', name: 'Orchestrator', icon: <Network className="size-5" />, purpose: 'Understands the goal, classifies the task, plans and delegates to specialists, re-plans when conflicts appear.', inputs: 'User goal, case metadata', outputs: 'Plan, delegations, final result', perms: 'INVOKE_AGENTS', tools: 'Planner, agent registry', risk: 'LOW', verification: 'Plan validated against policy', status: 'live' },
  { id: 'sec', name: 'Security Agent', icon: <ShieldAlert className="size-5" />, purpose: 'Scans every document for prompt injection, tool requests and exfiltration attempts before any reasoning.', inputs: 'Raw document chunks', outputs: 'Quarantine set, security events', perms: 'READ_CASE_DOCS', tools: 'Pattern + classifier scanners', risk: 'LOW', verification: 'Events logged to audit', status: 'live' },
  { id: 'ret', name: 'Retrieval Agent', icon: <FileSearch className="size-5" />, purpose: 'Finds page-level evidence for each question or claim.', inputs: 'Query, case index', outputs: 'Evidence chunks with doc + page', perms: 'READ_INDEX', tools: 'Lexical search (pgvector in backend)', risk: 'LOW', verification: 'Evidence hashed', status: 'live' },
  { id: 'rev', name: 'Case Review Agent', icon: <ScrollText className="size-5" />, purpose: 'Extracts facts: arrest, occurrence, offence, identification, alibi.', inputs: 'Evidence chunks', outputs: 'Claims linked to evidence IDs', perms: 'READ_CASE_DOCS', tools: 'Retrieval', risk: 'LOW', verification: 'Required — no evidence, no claim', status: 'live' },
  { id: 'ver', name: 'Verification Agent', icon: <ShieldCheck className="size-5" />, purpose: 'Grades each claim: supported, partial, conflicted, unsupported.', inputs: 'Claims, evidence', outputs: 'Trust status, coverage', perms: 'READ_EVIDENCE', tools: 'Evidence store', risk: 'LOW', verification: 'Self', status: 'live' },
  { id: 'con', name: 'Contradiction Agent', icon: <GitCompareArrows className="size-5" />, purpose: 'Compares facts across documents and preserves both sides of a conflict.', inputs: 'Claims across documents', outputs: 'Contradictions with confidence', perms: 'READ_EVIDENCE', tools: 'Retrieval', risk: 'LOW', verification: 'Both sources shown to user', status: 'live' },
  { id: 'mis', name: 'Missing Info Agent', icon: <Search className="size-5" />, purpose: 'Checks the record against a per-area checklist (arrest memo, bail order, title deed…).', inputs: 'Practice area, evidence', outputs: 'Gaps + why they matter', perms: 'READ_EVIDENCE', tools: 'Checklists', risk: 'LOW', verification: 'Rule-based', status: 'live' },
  { id: 'mat', name: 'Matching Agent', icon: <Handshake className="size-5" />, purpose: 'Ranks KYC-verified lawyers by area, related outcomes, city, rating and budget fit.', inputs: 'Case profile, lawyer directory, case DB', outputs: 'Ranked matches + fee estimates', perms: 'READ_LAWYER_DIR', tools: 'Directory, case DB', risk: 'LOW', verification: 'Only verified profiles', status: 'live' },
  { id: 'dra', name: 'Drafting Agent', icon: <FileSignature className="size-5" />, purpose: 'Prepares bail applications, notices and summaries from verified facts only.', inputs: 'Verified facts, gaps', outputs: 'Draft with evidence references', perms: 'WRITE_DRAFT', tools: 'Templates', risk: 'MEDIUM', verification: 'Human review required', status: 'live' },
  { id: 'res', name: 'Legal Research Agent', icon: <BrainCircuit className="size-5" />, purpose: 'Searches trusted sources for statutes and authorities and verifies every citation.', inputs: 'Issue list', outputs: 'Research memo', perms: 'READ_TRUSTED_SOURCES', tools: 'Licensed legal databases', risk: 'MEDIUM', verification: 'Citation verification', status: 'future' },
  { id: 'kyc', name: 'KYC Agent', icon: <UserCheck className="size-5" />, purpose: 'Verifies degree, identity, Bar enrolment and live face match for lawyers and judges.', inputs: 'Certificates, ID, selfie', outputs: 'Verification report for the desk', perms: 'READ_KYC_VAULT', tools: 'OCR, face-match provider, Bar roll', risk: 'MEDIUM', verification: 'Human approval by desk', status: 'simulated' },
  { id: 'ext', name: 'External Comms', icon: <KeyRound className="size-5" />, purpose: 'Sends drafts or memos outside FormLaw.', inputs: 'Approved artefact', outputs: 'Delivery receipt', perms: 'SEND_EXTERNAL', tools: 'Email / e-filing gateway', risk: 'HIGH', verification: 'Human approval mandatory', status: 'simulated' },
]

const LAYERS = [
  { t: 'User', i: <User className="size-4" /> }, { t: 'Authentication & RBAC', i: <Lock className="size-4" /> }, { t: 'Orchestrator · Planner', i: <Network className="size-4" /> },
  { t: 'Specialised agents', i: <Bot className="size-4" /> }, { t: 'Tool gateway', i: <Workflow className="size-4" /> }, { t: 'Memory (working · episodic · semantic · security)', i: <Database className="size-4" /> },
  { t: 'Verification', i: <ShieldCheck className="size-4" /> }, { t: 'Risk / policy engine', i: <ShieldAlert className="size-4" /> }, { t: 'Human approval', i: <UserCheck className="size-4" /> },
  { t: 'Action', i: <Handshake className="size-4" /> }, { t: 'Audit log', i: <ClipboardCheck className="size-4" /> },
]

export default function HowItWorks() {
  const [sel, setSel] = useState<Agent>(AGENTS[0])
  return (
    <div className="mx-auto max-w-7xl px-6 pt-32">
      <PageHeader eyebrow="Architecture" title="How FormLaw thinks" subtitle="Goal → understand → plan → delegate → retrieve → reason → verify → detect conflicts → adapt → trusted result. Click an agent to inspect its security profile." />
      <div className="grid gap-8 lg:grid-cols-[320px_1fr]">
        <ol className="relative space-y-2">
          <span className="absolute bottom-6 left-[22px] top-6 w-0.5 bg-gradient-to-b from-sky-200 via-sky-400 to-sky-200" aria-hidden />
          {LAYERS.map((l, i) => (
            <motion.li key={l.t} initial={{ opacity: 0, x: -14 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.05 }} className="relative flex items-center gap-3">
              <span className="relative z-10 grid size-11 shrink-0 place-items-center rounded-2xl bg-white text-sky-600 shadow-[var(--shadow-soft)] ring-1 ring-sky-100">{l.i}</span>
              <span className="text-sm font-extrabold">{l.t}</span>
            </motion.li>
          ))}
        </ol>
        <div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
            {AGENTS.map((a) => (
              <button key={a.id} onClick={() => setSel(a)} className={cx('relative rounded-2xl p-4 text-left transition', sel.id === a.id ? 'bg-sky-500 text-white shadow-[var(--shadow-glow)]' : 'card card-hover')}>
                <span className={cx('grid size-10 place-items-center rounded-xl', sel.id === a.id ? 'bg-white/20' : 'bg-sky-50 text-sky-600')}>{a.icon}</span>
                <span className="mt-3 block text-sm font-extrabold">{a.name}</span>
                <span className={cx('mt-1 block text-[10px] font-extrabold uppercase tracking-wider', sel.id === a.id ? 'text-sky-100' : a.status === 'live' ? 'text-emerald-600' : a.status === 'simulated' ? 'text-violet-600' : 'text-slate-400')}>{a.status === 'live' ? '● Live' : a.status === 'simulated' ? 'Simulated' : 'Future backend'}</span>
              </button>
            ))}
          </div>
          <AnimatePresence mode="wait">
            <motion.div key={sel.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="card mt-6 p-6">
              <div className="flex flex-wrap items-center gap-3"><span className="grid size-12 place-items-center rounded-2xl bg-sky-500 text-white">{sel.icon}</span><h2 className="text-2xl">{sel.name}</h2>
                <Badge tone={sel.risk === 'HIGH' ? 'red' : sel.risk === 'MEDIUM' ? 'amber' : 'green'}>Risk: {sel.risk}</Badge>{sel.status === 'live' ? <DemoTag live /> : <DemoTag />}</div>
              <p className="mt-3 font-semibold text-ink-soft">{sel.purpose}</p>
              <dl className="mt-5 grid gap-3 sm:grid-cols-2">
                {([['Inputs', sel.inputs], ['Outputs', sel.outputs], ['Permissions', sel.perms], ['Allowed tools', sel.tools], ['Verification', sel.verification], ['Requires approval', sel.risk === 'HIGH' ? 'YES' : sel.risk === 'MEDIUM' ? 'Human review' : 'NO']] as const).map(([k, v]) => (
                  <div key={k} className="rounded-2xl bg-sky-25 p-3"><dt className="text-xs font-extrabold uppercase tracking-wider text-ink-soft">{k}</dt><dd className={cx('mt-0.5 font-bold', k === 'Permissions' && 'font-mono text-sm')}>{v}</dd></div>
                ))}
              </dl>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      <section id="security" className="mt-20 grid items-center gap-10 lg:grid-cols-2">
        <div>
          <h2 className="text-3xl">Memory, controlled</h2>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {[['Working memory', 'Current task context — discarded after the task.'], ['Episodic memory', 'Previous case outcomes — anonymised, verified.'], ['Semantic memory', 'Validated legal knowledge with sources.'], ['Security memory', 'Threat signatures and policy events.']].map(([t, d]) => (
              <div key={t} className="card p-4"><p className="font-extrabold">{t}</p><p className="mt-1 text-sm font-semibold text-ink-soft">{d}</p></div>
            ))}
          </div>
          <p className="mt-4 text-sm font-semibold text-ink-soft">Memory writes pass verification; nothing from an untrusted document becomes memory. Case data is isolated per organisation and case.</p>
        </div>
        <ConstitutionArt className="mx-auto w-full max-w-md" />
      </section>
    </div>
  )
}
