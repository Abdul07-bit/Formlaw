import { motion } from 'framer-motion'
import { BookOpen, Database, ExternalLink, FileText, Info, MessageSquareText, Search, ShieldCheck, ShieldQuestion } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Badge, Button, cx, EmptyState, Field, inputCls, PageHeader } from '../components/ui'
import { errorMessage } from '../services/api/client'
import { askCorpus, corpusStats, KIND_LABEL, research, type CorpusFilters } from '../services/research'
import type { Authority, AuthorityKind, CorpusStats, LegalAnswer, LegalEvidence } from '../types'

const KINDS = Object.keys(KIND_LABEL) as AuthorityKind[]
const EXAMPLES = ['bail and personal liberty when trial is delayed', 'appeal against acquittal', 'Article 21 personal liberty', 'Section 302 IPC murder']

function CorpusPanel({ st }: { st: CorpusStats | null }) {
  if (!st) return null
  const t = st.totals
  return (
    <div className="card mb-6 p-5">
      <p className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-[0.16em] text-ink-soft"><Database className="size-4 text-sky-500" />Legal corpus · live counts</p>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
        {[['Documents indexed', t.documents.toLocaleString('en-IN')], ['Coverage', t.coverage ?? '—'], ['Sources with data', t.sources_with_data],
          ['Courts', t.courts], ['Constitution', t.constitution_provisions ? `${t.constitution_provisions} provisions` : 'not imported']].map(([k, v]) => (
          <div key={k as string} className="rounded-2xl bg-sky-25 p-3"><p className="text-lg font-extrabold">{v}</p><p className="text-xs font-bold text-ink-soft">{k}</p></div>
        ))}
      </div>
      <p className="mt-3 text-xs font-semibold text-ink-soft">
        Only sources whose licence permits reuse are ingested. {t.embedded_chunks ? `${t.embedded_chunks.toLocaleString('en-IN')} passages semantically indexed.` : 'Keyword search only (no embeddings yet).'}
        {' '}Statutes and the Constitution await permission from their official publisher.
      </p>
    </div>
  )
}

function EvidenceCard({ e }: { e: LegalEvidence }) {
  return (
    <div className="rounded-2xl border border-sky-100 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="slate">{e.evidenceId}</Badge>
        <span className="font-extrabold">{e.documentName}</span>
        {e.dataClass === 'SYNTHETIC' && <Badge tone="violet">SYNTHETIC</Badge>}
      </div>
      <p className="mt-1 text-xs font-bold text-ink-soft">
        {[e.court, e.date, e.neutralCitation, e.citation, e.caseNumber, e.page ? `p.${e.page}` : null].filter(Boolean).join(' · ')}
      </p>
      <p className="mt-2 max-h-40 overflow-auto whitespace-pre-line text-sm font-semibold leading-relaxed text-ink-soft scrollbar-thin">{e.text}</p>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs font-bold text-ink-soft">
        <span>Source: {e.source}</span>
        {e.documentUrl && <a href={e.documentUrl} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-sky-600 hover:underline">Original document <ExternalLink className="size-3" /></a>}
        {e.sourceUrl && <a href={e.sourceUrl} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-sky-600 hover:underline">Source & licence <ExternalLink className="size-3" /></a>}
        {e.contentHash && <span className="font-mono" title="SHA-256 of the passage">#{e.contentHash.slice(0, 12)}</span>}
      </div>
    </div>
  )
}

function AnswerBox({ a }: { a: LegalAnswer }) {
  const ok = a.status === 'SUPPORTED'
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className={cx('mt-6 rounded-3xl border-2 p-5', ok ? 'border-emerald-200 bg-emerald-50/40' : 'border-slate-200 bg-slate-50')}>
      <div className="flex flex-wrap items-center gap-2">
        {ok ? <Badge tone="green" icon={<ShieldCheck className="size-3" />}>Verified against sources</Badge>
          : <Badge tone="slate" icon={<ShieldQuestion className="size-3" />}>{a.status === 'NOT_FOUND' ? 'Not found in corpus' : 'Insufficient evidence'}</Badge>}
        {ok && <Badge tone="slate">{a.engine === 'llm' ? 'Model-phrased · each sentence re-verified' : 'Verbatim passages'}</Badge>}
      </div>
      <p className="mt-3 whitespace-pre-line text-[15px] font-bold leading-relaxed">{a.answer}</p>
      {a.note && <p className="mt-2 flex items-start gap-1.5 text-sm font-semibold text-ink-soft"><Info className="mt-0.5 size-4 shrink-0" />{a.note}</p>}
      {ok && a.claims.length > 0 && (
        <ul className="mt-4 space-y-1.5 text-sm">
          {a.claims.map((c, i) => (
            <li key={i} className="flex items-start gap-2 font-semibold">
              <Badge tone={c.status === 'SUPPORTED' ? 'green' : c.status === 'PARTIALLY_SUPPORTED' ? 'amber' : 'red'}>{c.status.replace('_', ' ').toLowerCase()}</Badge>
              <span className={cx(!['SUPPORTED', 'PARTIALLY_SUPPORTED'].includes(c.status) && 'text-ink-soft line-through')}>{c.text.slice(0, 220)}</span>
              <span className="text-xs text-ink-soft">{c.evidenceIds.join(', ')}</span>
            </li>
          ))}
        </ul>
      )}
      {a.evidence.length > 0 && <div className="mt-4 space-y-3">{a.evidence.map((e) => <EvidenceCard key={e.evidenceId} e={e} />)}</div>}
    </motion.div>
  )
}

function ResultCard({ r, i }: { r: Authority; i: number }) {
  return (
    <motion.article initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }} className="card p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={r.kind === 'judgment' ? 'violet' : r.kind === 'constitution_article' ? 'amber' : 'sky'}>{KIND_LABEL[r.kind]}</Badge>
        {r.reference && <span className="font-mono text-sm font-extrabold">{r.reference}</span>}
        {r.court && <span className="text-xs font-bold text-ink-soft">{r.court}</span>}
        {r.date && <span className="text-xs font-bold text-ink-soft">{r.date}</span>}
        {r.page && <span className="text-xs font-bold text-ink-soft">p.{r.page}</span>}
        {r.sourceStatus === 'REVIEW_REQUIRED' && <Badge tone="amber">Source terms under review</Badge>}
      </div>
      <h3 className="mt-2 text-lg">{r.title}</h3>
      {r.citation && r.citation !== r.reference && <p className="text-xs font-bold text-ink-soft">{r.citation}</p>}
      <p className="mt-2 max-h-48 overflow-auto whitespace-pre-line text-sm font-semibold leading-relaxed text-ink-soft scrollbar-thin">{r.text}</p>
      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs font-bold text-ink-soft">
        <span>Source: {r.sourceName}</span>
        {r.documentUrl && <a href={r.documentUrl} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-sky-600 hover:underline"><FileText className="size-3" />Original document</a>}
        {r.sourceUrl && <a href={r.sourceUrl} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-sky-600 hover:underline">Source <ExternalLink className="size-3" /></a>}
        <span className="font-mono" title="SHA-256 of the passage">#{r.contentHash.slice(0, 12)}</span>
      </div>
    </motion.article>
  )
}

export default function Research() {
  const [mode, setMode] = useState<'ask' | 'search'>('ask')
  const [query, setQuery] = useState('')
  const [kinds, setKinds] = useState<AuthorityKind[]>([])
  const [f, setF] = useState<CorpusFilters>({})
  const [stats, setStats] = useState<CorpusStats | null>(null)
  const [res, setRes] = useState<{ query: string; results: Authority[]; note?: string | null } | null>(null)
  const [ans, setAns] = useState<LegalAnswer | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => { corpusStats().then(setStats).catch(() => undefined) }, [])
  const set = <K extends keyof CorpusFilters>(k: K, v: CorpusFilters[K]) => setF((x) => ({ ...x, [k]: v }))

  const run = async (q = query) => {
    if (q.trim().length < 3) return
    setBusy(true); setErr(''); setQuery(q)
    try {
      if (mode === 'ask') { setAns(await askCorpus(q.trim(), { ...f, kinds })); setRes(null) }
      else { setRes(await research(q.trim(), { ...f, kinds })); setAns(null) }
    } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
  }
  const submit = (e: FormEvent) => { e.preventDefault(); void run() }

  return (
    <>
      <PageHeader eyebrow="Legal research" title="Research the verified legal corpus"
        subtitle="Every answer traces claim → evidence → document → original source. If the corpus cannot support an answer, FormLaw says so instead of inventing one." />
      <CorpusPanel st={stats} />
      <form onSubmit={submit} className="card grid gap-4 p-5">
        <div className="flex w-fit gap-1 rounded-2xl bg-sky-50 p-1" role="tablist">
          {([['ask', 'Ask a question', <MessageSquareText key="a" className="size-4" />], ['search', 'Search authorities', <Search key="s" className="size-4" />]] as const).map(([id, label, icon]) => (
            <button key={id} type="button" role="tab" aria-selected={mode === id} onClick={() => setMode(id)}
              className={cx('flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-extrabold', mode === id ? 'bg-sky-500 text-white' : 'text-sky-700')}>{icon}{label}</button>
          ))}
        </div>
        <div className="relative">
          <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-slate-400" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} maxLength={500} aria-label="Research query"
            placeholder={mode === 'ask' ? 'e.g. When can bail be granted if the trial is delayed?' : 'e.g. appeal against acquittal, 2024 INSC 735'}
            className="h-12 w-full rounded-2xl border border-sky-100 bg-sky-25 pl-12 pr-4 font-semibold outline-none focus:border-sky-400" />
        </div>
        <div className="flex flex-wrap gap-2">
          {KINDS.map((k) => {
            const on = kinds.includes(k)
            return <button type="button" key={k} aria-pressed={on} onClick={() => setKinds(on ? kinds.filter((x) => x !== k) : [...kinds, k])}
              className={cx('rounded-full px-4 py-1.5 text-sm font-extrabold transition', on ? 'bg-sky-500 text-white' : 'bg-sky-50 text-sky-700 hover:bg-sky-100')}>{KIND_LABEL[k]}</button>
          })}
        </div>
        <details className="rounded-2xl bg-sky-25 p-4">
          <summary className="cursor-pointer text-sm font-extrabold">Filters</summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <Field label="Court"><input className={inputCls} value={f.court ?? ''} onChange={(e) => set('court', e.target.value)} placeholder="Supreme Court of India" /></Field>
            <Field label="Year from"><input type="number" min={1950} max={2100} className={inputCls} value={f.yearFrom ?? ''} onChange={(e) => set('yearFrom', Number(e.target.value) || undefined)} /></Field>
            <Field label="Year to"><input type="number" min={1950} max={2100} className={inputCls} value={f.yearTo ?? ''} onChange={(e) => set('yearTo', Number(e.target.value) || undefined)} /></Field>
            <Field label="Case type"><input className={inputCls} value={f.caseType ?? ''} onChange={(e) => set('caseType', e.target.value)} placeholder="CRIMINAL APPEAL" /></Field>
            <Field label="Legal topic"><input className={inputCls} value={f.topic ?? ''} onChange={(e) => set('topic', e.target.value)} placeholder="bail, pension…" /></Field>
            <Field label="Citation"><input className={inputCls} value={f.citation ?? ''} onChange={(e) => set('citation', e.target.value)} placeholder="2024 INSC 735" /></Field>
            <Field label="Constitutional Article"><input className={inputCls} value={f.article ?? ''} onChange={(e) => set('article', e.target.value.replace(/[^0-9A-Za-z]/g, '').slice(0, 5))} placeholder="21" /></Field>
            <Field label="Statute / section"><input className={inputCls} value={f.statute ?? ''} onChange={(e) => set('statute', e.target.value)} placeholder="Section 439 CrPC" /></Field>
            <Field label="Source"><select className={inputCls} value={f.source ?? ''} onChange={(e) => set('source', e.target.value || undefined)}>
              <option value="">All approved sources</option>
              {stats?.sources.filter((s) => s.documents).map((s) => <option key={s.source} value={s.source}>{s.name}</option>)}
            </select></Field>
          </div>
        </details>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">{EXAMPLES.map((x) => <button type="button" key={x} onClick={() => void run(x)} className="rounded-full border border-sky-200 px-3 py-1 text-xs font-extrabold text-sky-700 hover:bg-sky-50">{x}</button>)}</div>
          <Button type="submit" loading={busy} icon={<BookOpen className="size-4" />}>{mode === 'ask' ? 'Ask' : 'Search'}</Button>
        </div>
      </form>

      {err && <p className="mt-6 rounded-2xl bg-rose-50 p-4 text-sm font-bold text-rose-700" role="alert">{err}</p>}
      {ans && <AnswerBox a={ans} />}
      {res?.note && <p className="mt-6 flex items-start gap-2 rounded-2xl bg-amber-50 p-4 text-sm font-bold text-amber-900"><Info className="mt-0.5 size-4 shrink-0" />{res.note}</p>}
      {res && !res.results.length && !res.note && <div className="mt-6"><EmptyState icon={<Search className="size-7" />} title="No authorities found" body="Try different terms or remove filters." /></div>}
      <div className="mt-6 space-y-4">{res?.results.map((r, i) => <ResultCard key={r.id} r={r} i={i} />)}</div>
      <p className="mt-8 text-xs font-semibold text-ink-soft">Research supports a qualified advocate's work and is not legal advice. Judgment texts come from openly licensed datasets (CC BY 4.0) of court records; verify against the official record before relying on them.</p>
    </>
  )
}
