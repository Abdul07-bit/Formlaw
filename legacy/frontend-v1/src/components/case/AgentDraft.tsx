import { AlertTriangle, BookMarked, CheckCircle2, Cpu, Play, ShieldCheck, ShieldX } from 'lucide-react'
import { useState } from 'react'
import { errorMessage } from '../../services/api/client'
import { createDraft, DRAFT_TYPES, draftLabel } from '../../services/cases'
import type { Analysis } from '../../types'
import { Badge, Button, cx } from '../ui'

const MISSING = '[MISSING INFORMATION]'

/** Statutory draft from the six-agent system (Review → Research → Drafting → Verification) with its release gate. */
export function AgentDraft({ caseId, a, readOnly }: { caseId: string; a: Analysis; readOnly?: boolean }) {
  const p = a.legalPipeline
  const [docType, setDocType] = useState(p?.docType ?? 'bail')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const d = p?.draft
  const v = p?.verification
  const ready = p?.release_status?.startsWith('READY')
  const blocked = p?.release_status?.startsWith('BLOCKED')

  const run = async () => {
    setBusy(true); setErr('')
    try { await createDraft(caseId, docType) } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
  }

  return (
    <div className="space-y-5">
      <div className="card flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <span className="grid size-11 place-items-center rounded-2xl bg-ink text-white"><Cpu className="size-5" /></span>
          <div>
            <p className="font-extrabold">Statutory draft · Research → Drafting → Verification</p>
            <p className="text-sm font-semibold text-ink-soft">Built only from verified facts and the trusted corpus. Quarantined documents are excluded.</p>
          </div>
        </div>
        {!readOnly && (
          <div className="flex gap-2">
            <select value={docType} onChange={(e) => setDocType(e.target.value)} aria-label="Draft type" className="h-11 rounded-2xl border border-sky-200 bg-white px-3 text-sm font-bold outline-none focus:border-sky-500">
              {DRAFT_TYPES.map((t) => <option key={t} value={t}>{draftLabel(t)}</option>)}
            </select>
            <Button onClick={run} loading={busy} icon={<Play className="size-4" />}>{p ? 'Re-draft' : 'Draft'}</Button>
          </div>
        )}
      </div>

      {err && <p className="flex items-center gap-2 rounded-2xl bg-rose-50 p-4 text-sm font-bold text-rose-700" role="alert"><AlertTriangle className="size-4" />{err}</p>}
      {!p && <p className="rounded-2xl bg-sky-50 p-4 text-sm font-bold text-sky-700">No statutory draft yet.</p>}
      {(p?.error || d?.error) && <p className="rounded-2xl bg-amber-50 p-4 text-sm font-bold text-amber-800">{String(p?.error ?? d?.error)}</p>}

      {p && d && !d.error && (
        <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
          <article className="card overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-sky-100 bg-sky-25 px-6 py-4">
              <h2 className="text-lg">{String(d.document_title ?? draftLabel(p.docType))}</h2>
              <Badge tone="amber">{String(d.status ?? 'Draft')}</Badge>
            </div>
            <div className="max-h-[720px] space-y-6 overflow-auto p-6 text-[15px] scrollbar-thin">
              {Object.entries(d).filter(([k]) => !['document_title', 'status', 'provenance', 'verification'].includes(k)).map(([k, val]) => (
                <section key={k}>
                  <h3 className="mb-2 text-xs font-extrabold uppercase tracking-[0.14em] text-sky-700">{k.replace(/_/g, ' ')}</h3>
                  <Value v={val} />
                </section>
              ))}
            </div>
          </article>

          <aside className="space-y-4">
            <div className={cx('rounded-3xl border-2 p-5', ready ? 'border-emerald-200 bg-emerald-50/60' : blocked ? 'border-rose-200 bg-rose-50/60' : 'border-amber-200 bg-amber-50/60')}>
              <p className="flex items-center gap-2 font-extrabold">{ready ? <ShieldCheck className="size-5 text-emerald-600" /> : <ShieldX className="size-5 text-rose-600" />}Release gate</p>
              <p className="mt-2 text-sm font-bold">{p.release_status}</p>
              {v && (
                <>
                  <p className="mt-3 text-sm font-semibold text-ink-soft">{v.final_result}</p>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs font-extrabold">
                    <span className="rounded-xl bg-white p-2"><span className="block text-lg text-emerald-600">{v.verified_claims.length}</span>verified</span>
                    <span className="rounded-xl bg-white p-2"><span className="block text-lg text-rose-600">{v.unsupported_claims.length}</span>unsupported</span>
                    <span className="rounded-xl bg-white p-2"><span className="block text-lg text-amber-600">{v.missing_information.length}</span>missing</span>
                  </div>
                </>
              )}
            </div>
            {p.research && (
              <div className="card p-5">
                <p className="flex items-center gap-2 font-extrabold"><BookMarked className="size-4 text-sky-500" />Verified authorities</p>
                <ul className="mt-3 space-y-2 text-sm">
                  {p.research.relevant_laws?.map((l) => <li key={l.doc_id} className="font-semibold"><CheckCircle2 className="mr-1 inline size-3.5 text-emerald-500" />{l.section ? `Section ${l.section}, ` : ''}{l.title}</li>)}
                  {p.research.relevant_judgments?.map((j) => <li key={j.doc_id} className="font-semibold"><CheckCircle2 className="mr-1 inline size-3.5 text-emerald-500" /><i>{j.title}</i> {j.citation}</li>)}
                  {!p.research.relevant_laws?.length && !p.research.relevant_judgments?.length && <li className="text-ink-soft">Nothing verified in the trusted corpus.</li>}
                </ul>
                <p className="mt-3 text-xs font-semibold text-ink-soft">Corpus covers IPC/CrPC; matters after 1 July 2024 fall under BNS/BNSS/BSA.</p>
              </div>
            )}
            <p className="text-xs font-semibold text-ink-soft">A draft for a qualified advocate. Never file it unreviewed.</p>
          </aside>
        </div>
      )}
    </div>
  )
}

function Value({ v }: { v: unknown }) {
  if (v === null || v === undefined || v === '' || v === MISSING) return <Missing />
  if (typeof v === 'string') return <p className="whitespace-pre-wrap font-semibold leading-relaxed">{v}</p>
  if (typeof v !== 'object') return <p className="font-semibold">{String(v)}</p>
  if (Array.isArray(v)) {
    if (!v.length) return <Missing />
    return (
      <ol className="list-decimal space-y-1.5 pl-5 font-semibold">
        {v.map((x, i) => {
          const o = x as Record<string, unknown>
          return <li key={i}>{typeof x === 'object' && x ? String(o.citation ?? o.title ?? JSON.stringify(x)) : String(x)}</li>
        })}
      </ol>
    )
  }
  return (
    <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-[180px_1fr]">
      {Object.entries(v as Record<string, unknown>).map(([k, x]) => (
        <div key={k} className="contents">
          <dt className="text-sm font-extrabold capitalize text-ink-soft">{k.replace(/_/g, ' ')}</dt>
          <dd className="font-semibold">{x === MISSING || x === null || x === '' ? <Missing /> : typeof x === 'object' ? JSON.stringify(x) : String(x)}</dd>
        </div>
      ))}
    </dl>
  )
}

const Missing = () => <span className="rounded-lg bg-amber-100 px-2 py-0.5 text-sm font-extrabold text-amber-800">Missing information</span>
