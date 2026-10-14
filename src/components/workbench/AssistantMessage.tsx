import { AlertTriangle, BookOpen, Bookmark, ChevronDown, ChevronRight, FileQuestion, FilePen, Scale, ShieldAlert, Sparkles } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../../lib/api'
import type { RunAuthority, RunClaim, RunContradiction, RunMissing, RunResult } from '../../lib/types'
import { cx, label } from '../../lib/util'
import { AssessmentPill, Badge, ConflictPill, StatusBadge } from '../ui'
import { AgentPlan } from './AgentPlan'
import { CaseReport } from './CaseReport'
import { Citation, Quote } from './Citation'

const INTENT: Record<string, string> = {
  CASE_REVIEW: 'Case review', EVIDENCE_QA: 'Evidence question', CONTRADICTIONS: 'Contradictions', TIMELINE: 'Timeline',
  MISSING_INFO: 'Missing information', CONTRACT_REVIEW: 'Contract review', LEGAL_RESEARCH: 'Legal research', DRAFT: 'Draft',
  COMPARE_DOCUMENTS: 'Document comparison', SUMMARY: 'Summary', OUT_OF_SCOPE: 'Out of scope',
}

export function Section({ icon, title, count, children, tone }: { icon: ReactNode; title: string; count?: number; children: ReactNode; tone?: 'warn' | 'bad' }) {
  return (
    <section className="space-y-2">
      <h4 className={cx('flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wider', tone === 'bad' ? 'text-bad' : tone === 'warn' ? 'text-warn' : 'text-muted')}>
        {icon}{title}{count !== undefined && <span className="text-faint">{count}</span>}
      </h4>
      {children}
    </section>
  )
}

export function ClaimRow({ c }: { c: RunClaim }) {
  return (
    <li className="flex flex-col gap-1 rounded-lg border border-line bg-surface px-3 py-2">
      <p className="text-[14px] leading-relaxed">{c.text}</p>
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusBadge status={c.status} reason={c.reason} />
        {c.citations.map((ci) => <Citation key={ci.chunkId + ci.quote.slice(0, 10)} c={ci} />)}
      </div>
    </li>
  )
}

export function ContradictionCard({ x }: { x: RunContradiction }) {
  const sides = x.provenance.sides ?? {}
  return (
    <div className="rounded-xl border border-warn/40 bg-warn-soft/40 p-3">
      <div className="mb-2 flex items-center gap-2">
        <AlertTriangle className="size-4 text-warn" />
        <p className="font-semibold">{x.topic}</p>
        <Badge tone="warn">{x.nature}</Badge>
        <span className="ml-auto"><ConflictPill level={x.confidence} /></span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {(['a', 'b'] as const).map((k) => (
          <div key={k} className="rounded-lg border border-line bg-surface p-2.5">
            <p className="text-[12px] text-muted">{k === 'a' ? 'Source A' : 'Source B'}{sides[k] ? ` — ${sides[k].role}` : ''}</p>
            <p className="my-1 text-lg font-semibold">{x[k].value}</p>
            {x[k].citation && <Quote c={x[k].citation!} />}
          </div>
        ))}
      </div>
      {x.provenance.assessment && <p className="mt-2 text-[13px] text-muted"><span className="font-medium text-fg">Provenance check: </span>{x.provenance.assessment}</p>}
    </div>
  )
}

export function MissingCard({ m }: { m: RunMissing }) {
  return (
    <li className="rounded-lg border border-line bg-surface px-3 py-2">
      <div className="flex items-center gap-2">
        <FileQuestion className="size-4 text-muted" />
        <p className="font-medium">{m.title}</p>
        <Badge tone={m.importance === 'high' ? 'bad' : 'neutral'}>{m.importance}</Badge>
        <span className="ml-auto text-[11px] text-faint">{m.basis === 'referenced_in_documents' ? 'referenced in the record' : m.basis === 'conflict_resolution' ? 'would settle a conflict' : m.basis === 'template_field' ? 'blank template field' : 'checklist'}</span>
      </div>
      <p className="mt-0.5 text-[13px] text-muted">{m.why}</p>
      {m.citation && <div className="mt-1"><Citation c={m.citation} /></div>}
    </li>
  )
}

export function AuthorityCard({ a }: { a: RunAuthority }) {
  return (
    <li className="rounded-lg border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Scale className="size-4 text-gold" />
        <p className="font-medium">{a.title}</p>
        <Badge tone="info">{label(a.type)}</Badge>
        <StatusBadge status={a.status} reason={a.status === 'SUPPORTED' ? 'Passage re-read from the verified corpus; hash matches' : 'Could not re-verify against the corpus'} />
      </div>
      <p className="mt-0.5 text-[12px] text-muted">{[a.court, a.date, a.citation, a.page ? `p.${a.page}` : null].filter(Boolean).join(' · ')}</p>
      <blockquote className="mt-2 border-l-2 border-gold pl-3 font-serif text-[14px] leading-relaxed">{a.quote}</blockquote>
      <p className="mt-1 text-[11px] text-faint">Source: {a.source}{a.license ? ` · ${a.license}` : ''}{a.sourceUrl && <> · <a className="text-accent underline" href={a.sourceUrl} target="_blank" rel="noreferrer noopener">original</a></>}</p>
    </li>
  )
}

export function AssistantMessage({ result, caseId, messageId, onAsk }: { result: RunResult; caseId: string; messageId?: string; onAsk: (p: string) => void }) {
  const r = result
  const [showUnverified, setShowUnverified] = useState(false)
  const [saved, setSaved] = useState<string | null>(null)
  const findings = r.claims.filter((c) => r.answer.claimIds.includes(c.id))
  const save = async () => {
    try {
      await api.post(`/cases/${caseId}/findings`, { title: r.answer.summary.slice(0, 200), messageId, content: { summary: r.answer.summary, runId: r.runId, findings: findings.map((f) => ({ text: f.text, status: f.status, citations: f.citations })) } })
      setSaved('Saved to findings')
    } catch (e) { setSaved(errorMessage(e)) }
  }
  const stats = `${r.stats.steps} steps · ${r.stats.toolCalls} tool calls · ${(r.stats.latencyMs / 1000).toFixed(1)}s · ${r.stats.engines.join(', ')}`
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
        <Badge tone="accent">{INTENT[r.intent] ?? r.intent}</Badge>
        {r.status === 'partial' && <Badge tone="warn" title={r.stopReason ?? ''}>partial</Badge>}
        {r.status === 'refused' && <Badge tone="bad">refused</Badge>}
      </div>
      <AgentPlan steps={r.plan} stats={stats} />

      <div className="font-serif text-[17px] leading-relaxed text-fg">{r.answer.summary}</div>
      {r.answer.assessment && (
        <div className="flex flex-wrap items-center gap-2">
          <AssessmentPill {...r.answer.assessment} />
          <span className="text-[12px] text-muted">{r.answer.assessment.reason}</span>
        </div>
      )}
      {r.answer.requiresLawyerReview && (
        <div className="rounded-lg border border-line bg-surface-2 px-3 py-2 text-[13px]">
          <span className="font-medium">Needs your review: </span>
          <span className="text-muted">{r.answer.reviewReasons.join(' · ')}</span>
        </div>
      )}

      {r.security.length > 0 && (
        <Section icon={<ShieldAlert className="size-3.5" />} title="Security" tone="bad">
          {r.security.map((s, i) => (
            <div key={i} className="rounded-lg border border-bad/30 bg-bad-soft/50 px-3 py-2 text-[13px]">
              <p className="font-medium text-bad">{s.action === 'request_refused' ? 'Request refused' : `Instructions found in ${s.source} — blocked from AI context, kept as evidence`}</p>
              <p className="mt-0.5 font-mono text-[12px] text-muted">“{s.snippet.slice(0, 180)}”</p>
            </div>
          ))}
        </Section>
      )}

      {r.report && <CaseReport r={r} />}

      {!r.report && r.contradictions.length > 0 && (
        <Section icon={<AlertTriangle className="size-3.5" />} title="Contradictions" count={r.contradictions.length} tone="warn">
          <div className="space-y-2">{r.contradictions.map((x) => <ContradictionCard key={x.id} x={x} />)}</div>
        </Section>
      )}

      {!r.report && findings.length > 0 && (
        <Section icon={<Sparkles className="size-3.5" />} title="Evidence" count={findings.length}>
          <ul className="space-y-1.5">{findings.map((c) => <ClaimRow key={c.id} c={c} />)}</ul>
        </Section>
      )}

      {!r.report && r.missing.length > 0 && (
        <Section icon={<FileQuestion className="size-3.5" />} title="Missing information" count={r.missing.length}>
          <ul className="space-y-1.5">{r.missing.map((m) => <MissingCard key={m.id} m={m} />)}</ul>
        </Section>
      )}

      {r.contractGaps.length > 0 && (
        <Section icon={<FileQuestion className="size-3.5" />} title="Standard provisions not found" count={r.contractGaps.length}>
          <ul className="grid gap-1.5 sm:grid-cols-2">{r.contractGaps.map((g) => (
            <li key={g.title} className="rounded-lg border border-line bg-surface px-3 py-2 text-[13px]"><p className="font-medium">{g.title}</p><p className="text-muted">{g.why}</p></li>
          ))}</ul>
        </Section>
      )}

      {!r.report && r.authorities.length > 0 && (
        <Section icon={<BookOpen className="size-3.5" />} title="Authorities (verified corpus)" count={r.authorities.length}>
          <ul className="space-y-2">{r.authorities.map((a) => <AuthorityCard key={a.id} a={a} />)}</ul>
        </Section>
      )}

      {r.draft && (
        <Section icon={<FilePen className="size-3.5" />} title="Draft">
          <div className="rounded-xl border border-line bg-surface p-3">
            <p className="font-medium">{r.draft.title}</p>
            <pre className="mt-2 max-h-56 overflow-hidden whitespace-pre-wrap font-serif text-[13.5px] text-muted [mask-image:linear-gradient(to_bottom,black_70%,transparent)]">{r.draft.body}</pre>
            <Link to={`/cases/${caseId}/drafts${r.draft.id ? `?draft=${r.draft.id}` : ''}`} className="mt-2 inline-flex text-[13px] font-medium text-accent hover:underline">Open in the draft editor →</Link>
          </div>
        </Section>
      )}

      {!r.report && r.answer.limitations.length > 0 && (
        <ul className="space-y-0.5 text-[13px] text-muted">{r.answer.limitations.map((l) => <li key={l}>• {l}</li>)}</ul>
      )}

      {r.unverified.length > 0 && (
        <div className="rounded-lg border border-line">
          <button type="button" className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] text-muted" onClick={() => setShowUnverified(!showUnverified)}>
            {showUnverified ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
            {r.unverified.length} statement(s) failed verification and are not part of the answer
          </button>
          {showUnverified && <ul className="space-y-1.5 border-t border-line p-2">{r.unverified.map((c) => <ClaimRow key={c.id} c={c} />)}</ul>}
        </div>
      )}

      <div className="flex flex-wrap gap-1.5 pt-1">
        {r.actions.filter((a) => a.prompt).map((a) => (
          <button key={a.label} type="button" onClick={() => onAsk(a.prompt!)} className="rounded-full border border-line px-3 py-1 text-[12.5px] text-muted hover:border-accent hover:text-accent">{a.label}</button>
        ))}
        {r.status !== 'refused' && (
          <button type="button" onClick={save} className="inline-flex items-center gap-1 rounded-full border border-line px-3 py-1 text-[12.5px] text-muted hover:border-accent hover:text-accent">
            <Bookmark className="size-3" />{saved ?? 'Save finding'}
          </button>
        )}
      </div>
    </div>
  )
}
