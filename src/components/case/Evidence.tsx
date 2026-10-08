import { motion } from 'framer-motion'
import { AlertTriangle, ArrowRightLeft, BadgeCheck, FileSearch, FileText, Fingerprint, Lightbulb, ShieldAlert, ShieldCheck } from 'lucide-react'
import { Fragment } from 'react'
import type { Analysis, CaseDocument, Contradiction, Evidence, Fact, MissingItem, SecurityEvent } from '../../types'
import { Badge, claimLabel, claimTone, cx, DemoTag } from '../ui'

function hashOf(s: string) {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) }
  return (h >>> 0).toString(16).padStart(8, '0')
}

/** Renders text with the evidence highlight marked — never as HTML, so uploaded content cannot inject markup. */
export function Highlighted({ text, mark }: { text: string; mark: string }) {
  const idx = mark ? text.toLowerCase().indexOf(mark.toLowerCase()) : -1
  if (idx < 0) return <>{text}</>
  return <>{text.slice(0, idx)}<mark className="rounded bg-amber-200/80 px-0.5 text-ink">{text.slice(idx, idx + mark.length)}</mark>{text.slice(idx + mark.length)}</>
}

export function EvidenceChip({ ev, onOpen, tone = 'sky' }: { ev: Evidence; onOpen: (id: string) => void; tone?: 'sky' | 'red' }) {
  return (
    <button onClick={() => onOpen(ev.id)} className={cx('inline-flex items-center gap-1.5 rounded-xl px-2.5 py-1 text-xs font-extrabold ring-1 ring-inset transition hover:-translate-y-0.5', tone === 'red' ? 'bg-rose-50 text-rose-700 ring-rose-200 hover:bg-rose-100' : 'bg-sky-50 text-sky-700 ring-sky-200 hover:bg-sky-100')}>
      <FileSearch className="size-3.5" />{ev.id} · {ev.docName.replace(/\.\w+$/, '').replace(/_/g, ' ')} p.{ev.page}
    </button>
  )
}

export function EvidencePanel({ ev, doc }: { ev: Evidence; doc?: CaseDocument }) {
  const pageText = doc?.text.split(/\[\[PAGE (\d+)\]\]/)
  let context = ev.excerpt
  if (pageText) {
    for (let i = 1; i < pageText.length; i += 2) if (Number(pageText[i]) === ev.page) context = pageText[i + 1].trim()
  }
  return (
    <div className="overflow-hidden rounded-3xl border border-sky-100 bg-white">
      <div className="flex items-center justify-between gap-3 border-b border-sky-100 bg-sky-25 px-5 py-3">
        <div className="flex min-w-0 items-center gap-2"><FileText className="size-4 shrink-0 text-sky-600" /><span className="truncate text-sm font-extrabold">{ev.docName}</span></div>
        <Badge tone="sky">Page {ev.page}</Badge>
      </div>
      <div className="relative bg-[linear-gradient(#fff_0_0)] px-6 py-6">
        <div className="absolute inset-y-0 left-0 w-1 bg-sky-400" />
        <p className="whitespace-pre-wrap font-mono text-[13px] leading-7 text-ink-soft"><Highlighted text={context} mark={ev.excerpt} /></p>
      </div>
      <dl className="grid grid-cols-3 gap-3 border-t border-sky-100 px-5 py-3 text-xs">
        <div><dt className="font-bold text-ink-soft">Evidence ID</dt><dd className="font-mono font-bold">{ev.id}</dd></div>
        <div><dt className="font-bold text-ink-soft">Source</dt><dd className="font-bold">Case document</dd></div>
        <div><dt className="font-bold text-ink-soft">Hash</dt><dd className="flex items-center gap-1 font-mono font-bold text-emerald-600"><Fingerprint className="size-3" />{hashOf(ev.excerpt)}</dd></div>
      </dl>
    </div>
  )
}

export function FactCard({ fact, evidence, onOpen, i }: { fact: Fact; evidence: Evidence[]; onOpen: (id: string) => void; i: number }) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} className="card card-hover p-5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-extrabold uppercase tracking-[0.14em] text-ink-soft">{fact.label}</span>
        <Badge tone={claimTone[fact.status]}>{claimLabel[fact.status]}</Badge>
      </div>
      <p className="mt-2 text-[15px] font-bold leading-relaxed">{fact.statement}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {fact.evidenceIds.map((id) => { const ev = evidence.find((e) => e.id === id); return ev ? <EvidenceChip key={id} ev={ev} onOpen={onOpen} tone={fact.status === 'conflicted' ? 'red' : 'sky'} /> : null })}
      </div>
    </motion.div>
  )
}

export function ContradictionCard({ c, evidence, onCompare }: { c: Contradiction; evidence: Evidence[]; onCompare: (c: Contradiction) => void }) {
  const a = evidence.find((e) => e.id === c.a.evidenceId)!
  const b = evidence.find((e) => e.id === c.b.evidenceId)!
  return (
    <motion.button
      onClick={() => onCompare(c)} initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} whileHover={{ y: -3 }}
      className="relative block w-full overflow-hidden rounded-3xl border-2 border-rose-200 bg-gradient-to-br from-rose-50 via-white to-amber-50 p-6 text-left shadow-[var(--shadow-soft)]"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-[0.18em] text-rose-600"><AlertTriangle className="size-4" />Contradiction detected</span>
        <Badge tone="amber">Requires review</Badge>
      </div>
      <h3 className="mt-2 text-2xl">{c.topic}</h3>
      <div className="mt-5 grid items-center gap-3 md:grid-cols-[1fr_auto_1fr]">
        {[{ v: c.a.value, e: a }, null, { v: c.b.value, e: b }].map((x, i) =>
          x ? (
            <div key={i} className="rounded-2xl bg-white p-4 ring-1 ring-rose-100">
              <p className="text-2xl font-extrabold text-rose-600">{x.v}</p>
              <p className="mt-1 text-xs font-bold text-ink-soft">{x.e.docName.replace(/\.\w+$/, '').replace(/_/g, ' ')} — Page {x.e.page}</p>
            </div>
          ) : <span key={i} className="mx-auto grid size-10 place-items-center rounded-full bg-ink text-xs font-black text-white">VS</span>,
        )}
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs font-bold text-ink-soft">
        <span>Detection confidence {Math.round(c.confidence * 100)}% · not a legal finding</span>
        <span className="flex items-center gap-1 text-sky-600"><ArrowRightLeft className="size-3.5" />Compare both sources</span>
      </div>
    </motion.button>
  )
}

export function MissingCard({ m, i }: { m: MissingItem; i: number }) {
  return (
    <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }} className="card border-l-4 !border-l-amber-400 p-5">
      <p className="flex items-center gap-2 font-extrabold"><AlertTriangle className="size-4 text-amber-500" />{m.title}</p>
      <p className="mt-2 text-sm text-ink-soft"><span className="font-extrabold text-ink">Why it matters: </span>{m.why}</p>
      <p className="mt-2 flex items-start gap-1.5 text-sm font-bold text-sky-700"><Lightbulb className="mt-0.5 size-4 shrink-0" />{m.action}</p>
    </motion.div>
  )
}

export function VerificationPanel({ v }: { v: Analysis['verification'] }) {
  const rows: [string, number, string][] = [
    ['Supported', v.supported, 'bg-emerald-500'], ['Partially supported', v.partial, 'bg-amber-400'],
    ['Conflicted', v.conflicted, 'bg-rose-500'], ['Unsupported', v.unsupported, 'bg-slate-300'],
  ]
  const trust = v.analysed ? Math.round(((v.supported + v.partial * 0.5) / v.analysed) * 100) : 0
  const R = 52, C = 2 * Math.PI * R
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-lg"><ShieldCheck className="size-5 text-sky-500" />Verification</h3>
        <DemoTag live />
      </div>
      <div className="mt-5 flex flex-col items-center gap-5">
        <div className="relative size-32 shrink-0">
          <svg viewBox="0 0 120 120" className="size-full -rotate-90">
            <circle cx="60" cy="60" r={R} stroke="#e0f2fe" strokeWidth="12" fill="none" />
            <motion.circle cx="60" cy="60" r={R} stroke="#0ea5e9" strokeWidth="12" fill="none" strokeLinecap="round" strokeDasharray={C} initial={{ strokeDashoffset: C }} animate={{ strokeDashoffset: C * (1 - trust / 100) }} transition={{ duration: 1.2, ease: 'easeOut' }} />
          </svg>
          <div className="absolute inset-0 grid place-items-center text-center"><div><div className="text-3xl font-extrabold">{trust}%</div><div className="text-[10px] font-extrabold uppercase tracking-wider text-ink-soft">Supported</div></div></div>
        </div>
        <ul className="w-full space-y-2 text-sm">
          <li className="flex justify-between font-extrabold"><span>Claims analysed</span><span>{v.analysed}</span></li>
          {rows.map(([l, n, c]) => (
            <li key={l} className="flex items-center justify-between font-semibold text-ink-soft"><span className="flex items-center gap-2"><span className={cx('size-2.5 rounded-full', c)} />{l}</span><span className="font-extrabold text-ink">{n}</span></li>
          ))}
          <li className="flex justify-between border-t border-sky-100 pt-2 font-semibold text-ink-soft"><span>Evidence coverage</span><span className="font-extrabold text-ink">{v.coverage}%</span></li>
          <li className="flex justify-between font-semibold text-ink-soft"><span>Citation integrity</span><span className="font-extrabold text-ink">{v.analysed ? '100%' : '—'}</span></li>
        </ul>
      </div>
      <p className="mt-4 text-xs font-semibold text-ink-soft">Scores measure how well claims are backed by uploaded documents — not the legal merit of the case.</p>
    </div>
  )
}

export function SecurityEventCard({ e }: { e: SecurityEvent }) {
  return (
    <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="overflow-hidden rounded-3xl border-2 border-rose-200 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-2 bg-rose-500 px-5 py-3 text-white">
        <span className="flex items-center gap-2 font-extrabold"><ShieldAlert className="size-5" />Prompt injection blocked</span>
        <span className="rounded-full bg-white/20 px-2.5 py-0.5 text-xs font-extrabold">RISK: {e.risk}</span>
      </div>
      <div className="space-y-3 p-5">
        <p className="text-sm font-bold">Document: <span className="font-mono">{e.docName}</span></p>
        <blockquote className="rounded-2xl bg-rose-50 p-3 font-mono text-xs leading-6 text-rose-800 line-through decoration-rose-300">{e.snippet}</blockquote>
        <ul className="grid gap-1.5 sm:grid-cols-2">
          {e.actions.map((a) => <li key={a} className="flex items-center gap-2 text-sm font-bold"><BadgeCheck className="size-4 text-emerald-500" />{a}</li>)}
        </ul>
      </div>
    </motion.div>
  )
}

export function CompareView({ c, evidence, docs }: { c: Contradiction; evidence: Evidence[]; docs: CaseDocument[] }) {
  const pair = [c.a, c.b].map((x) => evidence.find((e) => e.id === x.evidenceId)!)
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {pair.map((ev, i) => (
        <Fragment key={ev.id}>
          <div>
            <p className="mb-2 text-xs font-extrabold uppercase tracking-wider text-rose-600">Source {i === 0 ? 'A' : 'B'} · {i === 0 ? c.a.value : c.b.value}</p>
            <EvidencePanel ev={ev} doc={docs.find((d) => d.id === ev.docId)} />
          </div>
        </Fragment>
      ))}
      <p className="text-sm font-semibold text-ink-soft md:col-span-2">FormLaw preserves both sources. Recommended: obtain the arrest memo or first production order to resolve the conflict — a human must decide.</p>
    </div>
  )
}
