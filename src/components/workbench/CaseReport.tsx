import { AlertTriangle, BookOpen, CalendarDays, ClipboardList, FileQuestion, FileSearch, Info, ListChecks, Scale, Users } from 'lucide-react'
import type { ReactNode } from 'react'
import type { RunClaim, RunResult } from '../../lib/types'
import { cx } from '../../lib/util'
import { Badge } from '../ui'
import { AuthorityCard, ClaimRow, ContradictionCard, MissingCard, Section } from './AssistantMessage'
import { Citation } from './Citation'

const NATURE: Record<string, string> = {
  fact: 'Documented statement', allegation: 'Allegation', admission: 'Admission', disputed: 'Disputed', procedural: 'Procedural record',
}
const EVIDENCE_KINDS = new Set(Object.keys(NATURE))

/** Per-item documentary support. Describes what the cited document contains — not whether it is true. */
function support(c: RunClaim, conflicted: Set<string>): { label: string; tone: 'ok' | 'warn' | 'bad' | 'neutral' } {
  if (c.citations.some((ci) => conflicted.has(ci.chunkId))) return { label: 'Conflicting evidence', tone: 'warn' }
  if (c.status === 'SUPPORTED') return { label: 'Direct documentary support', tone: 'ok' }
  if (c.status === 'PARTIALLY_SUPPORTED') return { label: 'Partial support', tone: 'warn' }
  if (c.status === 'CONTRADICTED') return { label: 'Conflicting evidence', tone: 'warn' }
  return { label: 'Unsupported', tone: 'bad' }
}

/**
 * Structured case report (case review / summary): A overview · B findings · C evidence table · D timeline ·
 * E claims & counterarguments · F missing information · G legal analysis · H next steps · I limitations.
 * Every value shown here comes from the run result; absent information is labelled, never filled.
 */
export function CaseReport({ r }: { r: RunResult }) {
  const rep = r.report!
  const findings = r.claims.filter((c) => r.answer.claimIds.includes(c.id))
  const evidence = r.claims.filter((c) => EVIDENCE_KINDS.has(c.kind) && c.citations.length && c.status !== 'UNSUPPORTED')
  const conflicted = new Set(r.contradictions.flatMap((x) => [x.a.citation?.chunkId, x.b.citation?.chunkId].filter(Boolean) as string[]))
  const positions = (['allegation', 'admission', 'disputed'] as const).map((k) => ({ k, items: r.claims.filter((c) => c.kind === k && c.status !== 'UNSUPPORTED') }))
  const issues = r.claims.filter((c) => c.kind === 'issue' && c.status !== 'UNSUPPORTED')
  const nf = <span className="italic text-faint">{rep.notFound}</span>

  return (
    <div className="space-y-6">
      <Section icon={<Users className="size-3.5" />} title="A. Case overview">
        <div className="overflow-hidden rounded-xl border border-line bg-surface">
          <dl className="divide-y divide-line text-[13.5px]">
            <Row label="Case title (as entered)">{rep.overview.title}</Row>
            <Row label="Matter type (as entered)">{rep.overview.matterType}</Row>
            {rep.overview.fields.map((f) => (
              <Row key={f.key} label={f.label}>
                {f.value ? <span className="flex flex-wrap items-center gap-1.5"><span className="font-medium">{f.value}</span>{f.citation && <Citation c={f.citation} compact />}</span> : nf}
              </Row>
            ))}
            <Row label="Parties">
              {rep.overview.parties.length ? (
                <ul className="space-y-1">{rep.overview.parties.map((p) => (
                  <li key={p.name + p.role} className="flex flex-wrap items-center gap-1.5"><span className="font-medium">{p.name}</span><Badge>{p.role}</Badge>{p.citation && <Citation c={p.citation} compact />}</li>
                ))}</ul>
              ) : nf}
            </Row>
          </dl>
        </div>
      </Section>

      <Section icon={<ListChecks className="size-3.5" />} title="B. Case-specific findings" count={findings.length}>
        {findings.length ? <ul className="space-y-1.5">{findings.map((c) => <ClaimRow key={c.id} c={c} />)}</ul>
          : <p className="text-[13px] text-muted">No case-specific finding could be established from the reviewed documents.</p>}
      </Section>

      <Section icon={<FileSearch className="size-3.5" />} title="C. Evidence table" count={evidence.length}>
        {evidence.length ? (
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full min-w-[720px] text-left text-[13px]">
              <thead className="bg-surface-2 text-[11.5px] uppercase tracking-wide text-muted">
                <tr>{['ID', 'Actual evidence', 'Source', 'Location', 'Nature', 'Assessment'].map((h) => <th key={h} className="whitespace-nowrap px-3 py-2 font-semibold">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-line bg-surface">
                {evidence.map((c, i) => {
                  const ci = c.citations[0]
                  const s = support(c, conflicted)
                  return (
                    <tr key={c.id} className="align-top">
                      <td className="whitespace-nowrap px-3 py-2 font-mono text-[12px] text-muted">E-{String(i + 1).padStart(3, '0')}</td>
                      <td className="min-w-[260px] px-3 py-2 font-serif">“{ci.quote}”</td>
                      <td className="max-w-[170px] px-3 py-2"><Citation c={ci} compact /></td>
                      <td className="whitespace-nowrap px-3 py-2 text-muted">p.{ci.page} ¶{ci.paragraph}{ci.section ? <span className="block max-w-[140px] truncate text-[11.5px]">{ci.section}</span> : null}</td>
                      <td className="px-3 py-2">{NATURE[c.kind]}</td>
                      <td className="px-3 py-2"><Badge tone={s.tone} title={c.reason} className="whitespace-nowrap">{s.label}</Badge></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : <p className="text-[13px] text-muted">No case-specific evidence was found in the reviewed documents.</p>}
        <p className="text-[12px] text-faint">A statement appearing in a document establishes that the document contains it — not that it is true.</p>
      </Section>

      <Section icon={<CalendarDays className="size-3.5" />} title="D. Timeline" count={r.timeline.length}>
        {r.timeline.length ? (
          <ol className="space-y-1.5 border-l border-line pl-3">
            {r.timeline.map((t) => (
              <li key={t.id} className="text-[13.5px]">
                <span className={cx('font-medium', t.status === 'conflicted' && 'text-warn')}>{t.dateText}</span>
                <span className="text-muted"> — {t.description}</span>
                {t.status === 'conflicted' && <Badge tone="warn" className="ml-1.5">conflicting date</Badge>}
                {t.citation && <span className="ml-1.5"><Citation c={t.citation} compact /></span>}
              </li>
            ))}
          </ol>
        ) : <p className="text-[13px] text-muted">No dated event is documented in the reviewed material.</p>}
      </Section>

      <Section icon={<Scale className="size-3.5" />} title="E. Claims and counterarguments">
        <p className="text-[12px] text-faint">Positions as recorded in the documents. Recording a position does not establish it.</p>
        {positions.every((p) => !p.items.length) && !r.contradictions.length
          ? <p className="text-[13px] text-muted">No party's position is documented in the reviewed material.</p>
          : positions.filter((p) => p.items.length).map((p) => (
            <div key={p.k} className="space-y-1.5">
              <p className="text-[12.5px] font-medium">{NATURE[p.k]}s</p>
              <ul className="space-y-1.5">{p.items.map((c) => <ClaimRow key={c.id} c={c} />)}</ul>
            </div>
          ))}
        {r.contradictions.length > 0 && <div className="space-y-2">{r.contradictions.map((x) => <ContradictionCard key={x.id} x={x} />)}</div>}
      </Section>

      <Section icon={<FileQuestion className="size-3.5" />} title="F. Missing information" count={r.missing.length}>
        {r.missing.length ? <ul className="space-y-1.5">{r.missing.map((m) => <MissingCard key={m.id} m={m} />)}</ul>
          : <p className="text-[13px] text-muted">No missing record was identified.</p>}
      </Section>

      <Section icon={<BookOpen className="size-3.5" />} title="G. Legal analysis">
        <p className="text-[12px] text-faint">Issues and provisions are as raised in the documents. FormLaw has not independently verified them as current law, and does not assess the merits.</p>
        {!issues.length && !rep.overview.provisions.length && !r.authorities.length && <p className="text-[13px] text-muted">No legal issue or provision is identifiable from the reviewed documents.</p>}
        {issues.length > 0 && <ul className="space-y-1.5">{issues.map((c) => <ClaimRow key={c.id} c={c} />)}</ul>}
        {rep.overview.provisions.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 text-[13px]">
            <span className="text-muted">Provisions cited in the documents:</span>
            {rep.overview.provisions.map((p) => <span key={p.value} className="inline-flex items-center gap-1"><Badge tone="info">{p.value}</Badge>{p.citation && <Citation c={p.citation} compact />}</span>)}
          </div>
        )}
        {r.authorities.length > 0 && <ul className="space-y-2">{r.authorities.map((a) => <AuthorityCard key={a.id} a={a} />)}</ul>}
      </Section>

      <Section icon={<ClipboardList className="size-3.5" />} title="H. Recommended next steps">
        <ol className="list-decimal space-y-1 pl-5 text-[13.5px]">{rep.nextSteps.map((s) => <li key={s}>{s}</li>)}</ol>
      </Section>

      <Section icon={<Info className="size-3.5" />} title="I. Limitations">
        <ul className="space-y-0.5 text-[13px] text-muted">
          <li>• Reviewed: {rep.documents.reviewed.length ? rep.documents.reviewed.join(', ') : 'no document with case-specific content'} ({rep.documents.total} document(s) in the case).</li>
          {rep.documents.templates.length > 0 && <li>• Unfilled template(s), not used as evidence: {rep.documents.templates.join(', ')}.</li>}
          {rep.documents.unreadable.length > 0 && <li className="text-warn">• Not readable, not reviewed: {rep.documents.unreadable.join(', ')}.</li>}
          {r.answer.limitations.map((l) => <li key={l}>• {l}</li>)}
          <li>• Legal research has not been independently verified against current official sources.</li>
        </ul>
      </Section>
      {r.contradictions.length > 0 && <p className="flex items-center gap-1.5 text-[12px] text-warn"><AlertTriangle className="size-3.5" />The documents conflict; FormLaw reports both sides and does not choose.</p>}
    </div>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 px-3 py-2 sm:grid-cols-[180px_1fr] sm:gap-3">
      <dt className="text-[12.5px] text-muted">{label}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  )
}
