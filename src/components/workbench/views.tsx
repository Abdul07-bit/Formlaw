import { useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, FileText, Plus, ShieldAlert, Upload, X } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, errorMessage } from '../../lib/api'
import { useCaseView, useDocuments, useOverview } from '../../lib/queries'
import type { Case, Citation as Cite } from '../../lib/types'
import { bytes, cx, fmtDate, label, timeAgo } from '../../lib/util'
import { Badge, Button, Card, ConflictPill, EmptyState, Input, SectionTitle, Skeleton, StatusBadge, Textarea } from '../ui'
import { ApprovalDialog } from './ApprovalDialog'
import { Citation, Quote } from './Citation'

type Ev = Cite & { evidenceId: string }
interface ClaimRow { id: string; text: string; kind: string; agent: string; status: string; confidence: string; reason: string; reviewStatus: string; citations: Ev[] }
interface ContraRow { id: string; topic: string; nature: string; confidence: string; status: string; statementA: string; statementB: string; a: Ev | null; b: Ev | null; provenance: { assessment?: string }; resolutionNote: string | null }
interface MissingRow { id: string; title: string; why: string; basis: string; importance: string; status: string; citation: Ev | null }
interface TimelineRow { id: string; date: string | null; dateText: string; description: string; eventType: string; status: string; citation: Ev | null }
interface AuthorityRow { id: string; type: string; title: string; citation: string | null; court: string | null; date: string | null; page: number | null; quote: string; issue: string; source: string; sourceUrl: string | null; license: string | null }
interface DraftRow { id: string; kind: string; title: string; body: string; status: string; version: number; createdAt: string; sections: { recommendations?: string[] } }
interface TaskRow { id: string; title: string; status: string; dueDate: string | null; source: string }
interface ActivityRow { id: string; taskId: string; goal: string; intent: string; status: string; engine: string; steps: number; toolCalls: number; replans: number; tokens: number; latencyMs: number | null; createdAt: string; plan: { id: string; agent: string; label: string; status: string; origin: string; summary: string }[]; tools: { agent: string; tool: string; status: string; latencyMs: number; risk: string; model: string | null }[] }

function Loading() { return <div className="space-y-2"><Skeleton className="h-16" /><Skeleton className="h-16" /><Skeleton className="h-16" /></div> }
function Wrap({ title, intro, children, right }: { title: string; intro?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6">
      <div className="mb-4 flex items-end justify-between gap-3">
        <div><h2 className="font-serif text-xl">{title}</h2>{intro && <p className="mt-0.5 text-sm text-muted">{intro}</p>}</div>{right}
      </div>
      {children}
    </div>
  )
}

export function OverviewView({ kase, onAsk }: { kase: Case; onAsk: (p: string) => void }) {
  const { data } = useOverview(kase.id)
  const items: [string, number | undefined, string][] = [
    ['Documents', data?.documents, 'documents'], ['Verified statements', data && data.claims - data.unverified, 'claims'],
    ['Open contradictions', data?.contradictions, 'contradictions'], ['Missing records', data?.missing, 'missing'],
    ['Timeline events', data?.timeline, 'timeline'], ['Authorities', data?.authorities, 'research'], ['Drafts', data?.drafts, 'drafts'],
    ['Open tasks', data?.openTasks, 'tasks'], ['Security events', data?.securityEvents, 'audit'],
  ]
  const [, setParams] = useSearchParams()
  return (
    <Wrap title="Overview" intro={kase.description || 'No description.'}>
      <dl className="grid gap-2 sm:grid-cols-3">
        {items.map(([k, v, view]) => (
          <button key={k} type="button" onClick={() => setParams({ view })} className="rounded-xl border border-line bg-surface px-4 py-3 text-left hover:border-line-strong">
            <dt className="text-[12px] text-muted">{k}</dt>
            <dd className={cx('text-2xl font-semibold', k === 'Security events' && v ? 'text-bad' : k === 'Open contradictions' && v ? 'text-warn' : '')}>{v ?? '—'}</dd>
          </button>
        ))}
      </dl>
      <div className="mt-6 grid gap-2 sm:grid-cols-2">
        <Card className="p-4">
          <SectionTitle>Matter</SectionTitle>
          <dl className="grid grid-cols-[110px_1fr] gap-y-1 text-sm">
            <dt className="text-muted">Reference</dt><dd>{kase.reference}</dd>
            <dt className="text-muted">Type</dt><dd>{label(kase.matterType)}</dd>
            <dt className="text-muted">Court</dt><dd>{kase.court || '—'}</dd>
            <dt className="text-muted">Jurisdiction</dt><dd>{kase.jurisdiction || '—'}</dd>
            <dt className="text-muted">Client</dt><dd>{kase.clientName || '—'}</dd>
          </dl>
        </Card>
        <Card className="p-4">
          <SectionTitle>Next steps</SectionTitle>
          <div className="flex flex-wrap gap-1.5">
            {['Review this case and identify the biggest weaknesses.', 'Build a timeline of events.', 'What documents or information are missing?', 'Summarize the case for senior counsel.'].map((p) => (
              <button key={p} type="button" onClick={() => onAsk(p)} className="rounded-full border border-line px-3 py-1 text-[12.5px] text-muted hover:border-accent hover:text-accent">{p.replace(/\.$/, '')}</button>
            ))}
          </div>
        </Card>
      </div>
    </Wrap>
  )
}

export function DocumentsView({ kase, onUpload, onOpen }: { kase: Case; onUpload: () => void; onOpen: (docId: string) => void }) {
  const { data, isLoading } = useDocuments(kase.id)
  return (
    <Wrap title="Documents" intro="Documents are untrusted input: validated, hashed, encrypted at rest, scanned for instructions, then indexed by page and paragraph."
      right={<Button variant="primary" onClick={onUpload}><Upload className="size-4" />Add documents</Button>}>
      {isLoading ? <Loading /> : !data?.length ? <EmptyState icon={<FileText className="size-6" />} title="No documents yet" action={<Button onClick={onUpload}>Upload</Button>}>Add the FIR, contracts, statements or orders for this matter.</EmptyState> : (
        <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
          {data.map((d) => (
            <li key={d.id}>
              <button type="button" onClick={() => onOpen(d.id)} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface-2">
                <FileText className="size-5 text-muted" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{d.filename}</p>
                  <p className="text-[12px] text-muted">{label(d.docType ?? 'document')} · {d.pages ?? '?'} page(s) · {bytes(d.size)} · {timeAgo(d.uploadedAt)}{d.source !== 'lawyer_upload' ? ` · from client` : ''}</p>
                </div>
                {d.securityFlags?.length ? <Badge tone="bad"><ShieldAlert className="size-3" />instructions detected</Badge> : null}
                {d.docType === 'template' ? <Badge tone="warn" title="Unfilled form: its placeholders are never used as case facts">blank template</Badge> : null}
                <Badge tone={d.status === 'indexed' ? 'ok' : d.status === 'needs_ocr' ? 'warn' : d.status === 'failed' ? 'bad' : 'neutral'}>{label(d.status)}</Badge>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Wrap>
  )
}

export function EvidenceView({ kase }: { kase: Case }) {
  const { data, isLoading } = useCaseView<(Ev & { contentHash: string })[]>(kase.id, 'evidence')
  return (
    <Wrap title="Evidence" intro="Every passage FormLaw has cited in this case, exactly as it appears in the document.">
      {isLoading ? <Loading /> : !data?.length ? <EmptyState title="No evidence cited yet">Ask a question or run a review to build the evidence record.</EmptyState> : (
        <div className="space-y-2">{data.map((e) => <Quote key={e.evidenceId} c={e} />)}</div>
      )}
    </Wrap>
  )
}

export function TimelineView({ kase, compact }: { kase: Case; compact?: boolean }) {
  const { data, isLoading } = useCaseView<TimelineRow[]>(kase.id, 'timeline')
  const body = isLoading ? <Loading /> : !data?.length ? <EmptyState title="No dated events yet">Ask “Build a timeline of events”.</EmptyState> : (
    <ol className="relative space-y-3 border-l border-line pl-5">
      {data.map((t) => (
        <li key={t.id} className="relative">
          <span className={cx('absolute -left-[25px] top-1.5 size-2.5 rounded-full ring-4 ring-bg', t.status === 'conflicted' ? 'bg-warn' : 'bg-accent')} />
          <p className="text-[13px] font-semibold">{t.dateText}{t.status === 'conflicted' && <Badge tone="warn" className="ml-2">conflicted</Badge>}</p>
          <p className="text-[14px]">{t.description}</p>
          {t.citation && <div className="mt-0.5"><Citation c={t.citation} /></div>}
        </li>
      ))}
    </ol>
  )
  return compact ? body : <Wrap title="Timeline" intro="Dated events extracted from the documents. Conflicting dates are marked, never merged.">{body}</Wrap>
}

export function ClaimsView({ kase, compact }: { kase: Case; compact?: boolean }) {
  const { data, isLoading } = useCaseView<ClaimRow[]>(kase.id, 'claims')
  const qc = useQueryClient()
  const [filter, setFilter] = useState<'all' | 'unverified' | 'unreviewed'>('all')
  const review = async (id: string, decision: string) => {
    await api.patch(`/claims/${id}`, { decision })
    qc.invalidateQueries({ queryKey: ['claims', kase.id] })
  }
  const rows = (data ?? []).filter((c) => filter === 'all' || (filter === 'unverified' ? !['SUPPORTED', 'PARTIALLY_SUPPORTED'].includes(c.status) : c.reviewStatus === 'unreviewed'))
  const body = isLoading ? <Loading /> : (
    <>
      <div className="mb-3 flex gap-1">
        {(['all', 'unverified', 'unreviewed'] as const).map((f) => (
          <button key={f} type="button" onClick={() => setFilter(f)} className={cx('rounded-md px-2 py-1 text-[12.5px]', filter === f ? 'bg-surface-3 font-medium' : 'text-muted')}>{label(f)}</button>
        ))}
      </div>
      {!rows.length ? <EmptyState title="No statements here" /> : (
        <ul className="space-y-1.5">
          {rows.map((c) => (
            <li key={c.id} className={cx('rounded-lg border bg-surface px-3 py-2', c.reviewStatus === 'rejected' ? 'border-line opacity-60' : 'border-line')}>
              <p className="text-[14px]">{c.text}</p>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <StatusBadge status={c.status} reason={c.reason} />
                <Badge>{label(c.kind)}</Badge>
                {c.citations.map((ci) => <Citation key={ci.evidenceId} c={ci} compact={compact} />)}
                <span className="ml-auto flex items-center gap-1">
                  {c.reviewStatus !== 'unreviewed' && <span className={cx('text-[11px] font-medium', c.reviewStatus === 'accepted' ? 'text-ok' : 'text-bad')}>{c.reviewStatus}</span>}
                  <button type="button" title="Accept" aria-label="Accept" onClick={() => review(c.id, 'accepted')} className="rounded p-1 text-muted hover:bg-ok-soft hover:text-ok"><Check className="size-3.5" /></button>
                  <button type="button" title="Reject" aria-label="Reject" onClick={() => review(c.id, 'rejected')} className="rounded p-1 text-muted hover:bg-bad-soft hover:text-bad"><X className="size-3.5" /></button>
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  )
  return compact ? body : <Wrap title="Claims" intro="Statements agents extracted, each with its verification status. Accept or reject them — your decision is never overwritten by a later run.">{body}</Wrap>
}

export function ContradictionsView({ kase, compact }: { kase: Case; compact?: boolean }) {
  const { data, isLoading } = useCaseView<ContraRow[]>(kase.id, 'contradictions')
  const qc = useQueryClient()
  const set = async (id: string, status: string) => {
    await api.patch(`/contradictions/${id}`, { status })
    qc.invalidateQueries({ queryKey: ['contradictions', kase.id] })
  }
  const body = isLoading ? <Loading /> : !data?.length ? <EmptyState title="No contradictions recorded">Ask “Find contradictions between the documents”.</EmptyState> : (
    <div className="space-y-2">
      {data.map((x) => (
        <div key={x.id} className={cx('rounded-xl border p-3', x.status === 'open' ? 'border-warn/40 bg-warn-soft/30' : 'border-line bg-surface opacity-70')}>
          <div className="mb-2 flex items-center gap-2">
            <AlertTriangle className="size-4 text-warn" /><p className="font-semibold">{x.topic}</p><Badge>{x.status}</Badge>
            {!compact && <span className="ml-auto"><ConflictPill level={x.confidence} /></span>}
          </div>
          <div className={cx('grid gap-2', !compact && 'sm:grid-cols-2')}>
            {x.a && <Quote c={x.a} />}{x.b && <Quote c={x.b} />}
          </div>
          {x.provenance?.assessment && <p className="mt-2 text-[13px] text-muted">{x.provenance.assessment}</p>}
          {x.status === 'open' && (
            <div className="mt-2 flex gap-1.5">
              <Button size="sm" onClick={() => set(x.id, 'resolved')}>Mark resolved</Button>
              <Button size="sm" variant="ghost" onClick={() => set(x.id, 'dismissed')}>Dismiss</Button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
  return compact ? body : <Wrap title="Contradictions" intro="Conflicts between sources. FormLaw reports both sides and checks provenance; it never picks one for you.">{body}</Wrap>
}

export function MissingView({ kase, compact }: { kase: Case; compact?: boolean }) {
  const { data, isLoading } = useCaseView<MissingRow[]>(kase.id, 'missing-information')
  const qc = useQueryClient()
  const set = async (id: string, status: string) => {
    await api.patch(`/missing-information/${id}`, { status })
    qc.invalidateQueries({ queryKey: ['missing-information', kase.id] })
  }
  const addTask = async (title: string) => {
    await api.post(`/cases/${kase.id}/tasks`, { title: `Obtain: ${title}`, source: 'agent' })
    qc.invalidateQueries({ queryKey: ['tasks', kase.id] })
  }
  const body = isLoading ? <Loading /> : !data?.length ? <EmptyState title="Nothing recorded as missing">Ask “What documents are missing?”.</EmptyState> : (
    <ul className="space-y-1.5">
      {data.map((m) => (
        <li key={m.id} className={cx('rounded-lg border border-line bg-surface px-3 py-2', m.status !== 'open' && 'opacity-60')}>
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium">{m.title}</p>
            <Badge tone={m.importance === 'high' ? 'bad' : 'neutral'}>{m.importance}</Badge>
            <Badge>{m.status}</Badge>
            {!compact && m.status === 'open' && (
              <span className="ml-auto flex gap-1">
                <Button size="sm" variant="ghost" onClick={() => addTask(m.title)}>Create task</Button>
                <Button size="sm" variant="ghost" onClick={() => set(m.id, 'requested')}>Requested</Button>
                <Button size="sm" variant="ghost" onClick={() => set(m.id, 'resolved')}>Received</Button>
              </span>
            )}
          </div>
          <p className="text-[13px] text-muted">{m.why}</p>
          {m.citation && <div className="mt-1"><Citation c={m.citation} /></div>}
        </li>
      ))}
    </ul>
  )
  return compact ? body : <Wrap title="Missing information" intro="Records the case file refers to but does not contain, and records a matter of this type normally needs.">{body}</Wrap>
}

export function AuthoritiesView({ kase, onAsk }: { kase: Case; onAsk: (p: string) => void }) {
  const { data, isLoading } = useCaseView<AuthorityRow[]>(kase.id, 'authorities')
  const [q, setQ] = useState('')
  return (
    <Wrap title="Legal research" intro="Authorities come only from FormLaw's verified corpus (Supreme Court of India judgments, CC-BY-4.0). Nothing is generated.">
      <form className="mb-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (q.trim()) onAsk(`Find authorities on ${q.trim()}`) }}>
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Legal issue, e.g. bail where trial is delayed" />
        <Button variant="primary" type="submit">Research</Button>
      </form>
      {isLoading ? <Loading /> : !data?.length ? <EmptyState title="No authorities saved for this case" /> : (
        <ul className="space-y-2">
          {data.map((a) => (
            <li key={a.id} className="rounded-xl border border-line bg-surface p-3">
              <p className="font-medium">{a.title}</p>
              <p className="text-[12px] text-muted">{[a.court, a.date, a.citation, a.page ? `p.${a.page}` : null].filter(Boolean).join(' · ')}</p>
              <blockquote className="mt-2 border-l-2 border-gold pl-3 font-serif text-[14px]">{a.quote}</blockquote>
              <p className="mt-1 text-[11px] text-faint">Issue: {a.issue} · {a.source}{a.sourceUrl && <> · <a href={a.sourceUrl} target="_blank" rel="noreferrer noopener" className="text-accent underline">original</a></>}</p>
            </li>
          ))}
        </ul>
      )}
    </Wrap>
  )
}

export function DraftsView({ kase, onAsk }: { kase: Case; onAsk: (p: string) => void }) {
  const { data, isLoading, refetch } = useCaseView<DraftRow[]>(kase.id, 'drafts')
  const [params, setParams] = useSearchParams()
  const selected = data?.find((d) => d.id === params.get('draft')) ?? data?.[0]
  const [body, setBody] = useState('')
  const [msg, setMsg] = useState('')
  const [share, setShare] = useState(false)
  useEffect(() => { setBody(selected?.body ?? ''); setMsg('') }, [selected?.id, selected?.body])
  const save = async () => {
    try { await api.patch(`/drafts/${selected!.id}`, { body }); setMsg('Saved — approval reset'); refetch() } catch (e) { setMsg(errorMessage(e)) }
  }
  const approve = async () => {
    try { await api.post(`/drafts/${selected!.id}/approve`); setMsg('Approved'); refetch() } catch (e) { setMsg(errorMessage(e)) }
  }
  const kinds = [['case_summary', 'Case summary'], ['briefing_note', 'Briefing note'], ['cross_examination_questions', 'Cross-examination questions'], ['legal_notice', 'Legal notice'], ['chronology', 'Chronology'], ['client_update', 'Client update']]
  return (
    <Wrap title="Drafts" intro="Drafts are assembled only from verified facts and verified authorities. You edit, approve and decide whether anything leaves the firm.">
      <div className="mb-4 flex flex-wrap gap-1.5">
        {kinds.map(([k, l]) => (
          <button key={k} type="button" onClick={() => onAsk(`Draft a ${l.toLowerCase()} for this case.`)} className="inline-flex items-center gap-1 rounded-full border border-line px-3 py-1 text-[12.5px] text-muted hover:border-accent hover:text-accent"><Plus className="size-3" />{l}</button>
        ))}
      </div>
      {isLoading ? <Loading /> : !data?.length ? <EmptyState title="No drafts yet">Choose a draft type above.</EmptyState> : (
        <div className="grid gap-4 md:grid-cols-[220px_1fr]">
          <ul className="space-y-1">
            {data.map((d) => (
              <li key={d.id}>
                <button type="button" onClick={() => setParams({ view: 'drafts', draft: d.id })}
                  className={cx('w-full rounded-lg px-3 py-2 text-left text-[13px]', d.id === selected?.id ? 'bg-surface-3' : 'hover:bg-surface-2')}>
                  <p className="truncate font-medium">{d.title}</p>
                  <p className="text-[11px] text-muted">v{d.version} · {d.status} · {timeAgo(d.createdAt)}</p>
                </button>
              </li>
            ))}
          </ul>
          {selected && (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={selected.status === 'approved' ? 'ok' : selected.status === 'shared' ? 'info' : 'warn'}>{selected.status}</Badge>
                <span className="ml-auto flex gap-1.5">
                  <Button size="sm" onClick={save} disabled={body === selected.body}>Save</Button>
                  <Button size="sm" onClick={approve} disabled={selected.status !== 'draft' || body !== selected.body}>Approve</Button>
                  <Button size="sm" variant="primary" onClick={() => setShare(true)} disabled={selected.status !== 'approved'}>Share with client…</Button>
                </span>
              </div>
              <Textarea value={body} onChange={(e) => setBody(e.target.value)} className="h-[60vh] font-serif text-[14.5px] leading-relaxed" aria-label="Draft text" />
              {msg && <p className="text-[13px] text-muted">{msg}</p>}
              <ApprovalDialog open={share} onClose={() => { setShare(false); refetch() }} action="draft.share" resourceId={selected.id} />
            </div>
          )}
        </div>
      )}
    </Wrap>
  )
}

export function TasksView({ kase }: { kase: Case }) {
  const { data, refetch } = useCaseView<TaskRow[]>(kase.id, 'tasks')
  const [title, setTitle] = useState('')
  const add = async () => { if (!title.trim()) return; await api.post(`/cases/${kase.id}/tasks`, { title }); setTitle(''); refetch() }
  const toggle = async (t: TaskRow) => { await api.patch(`/tasks/${t.id}`, { status: t.status === 'open' ? 'done' : 'open' }); refetch() }
  return (
    <Wrap title="Tasks">
      <form className="mb-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); add() }}>
        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Add a task" /><Button type="submit">Add</Button>
      </form>
      <ul className="space-y-1">
        {(data ?? []).map((t) => (
          <li key={t.id} className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2">
            <input type="checkbox" checked={t.status === 'done'} onChange={() => toggle(t)} aria-label={t.title} className="size-4 accent-[var(--accent)]" />
            <span className={cx('flex-1 text-[14px]', t.status === 'done' && 'text-muted line-through')}>{t.title}</span>
            {t.source === 'agent' && <Badge>suggested</Badge>}
            {t.dueDate && <span className="text-[12px] text-muted">{fmtDate(t.dueDate)}</span>}
          </li>
        ))}
      </ul>
    </Wrap>
  )
}

export function SavedView({ kase }: { kase: Case }) {
  const { data } = useCaseView<{ id: string; title: string; note: string; createdAt: string; content: { findings?: { text: string; status: string; citations: Cite[] }[] } }[]>(kase.id, 'findings')
  return (
    <Wrap title="Saved findings">
      {!data?.length ? <EmptyState title="Nothing saved yet">Use “Save finding” under any answer.</EmptyState> : (
        <ul className="space-y-2">
          {data.map((f) => (
            <li key={f.id} className="rounded-xl border border-line bg-surface p-3">
              <p className="font-serif text-[15px]">{f.title}</p>
              <p className="text-[11px] text-faint">{timeAgo(f.createdAt)}</p>
              <ul className="mt-2 space-y-1">{(f.content.findings ?? []).map((x, i) => (
                <li key={i} className="text-[13px]"><StatusBadge status={x.status} /> {x.text} {x.citations.map((c) => <Citation key={c.chunkId} c={c} compact />)}</li>
              ))}</ul>
            </li>
          ))}
        </ul>
      )}
    </Wrap>
  )
}

export function ActivityView({ kase, compact }: { kase: Case; compact?: boolean }) {
  const { data, isLoading } = useCaseView<ActivityRow[]>(kase.id, 'activity')
  const [open, setOpen] = useState<string | null>(null)
  const body = isLoading ? <Loading /> : !data?.length ? <EmptyState title="No agent runs yet" /> : (
    <ul className="space-y-1.5">
      {data.map((r) => (
        <li key={r.id} className="rounded-lg border border-line bg-surface">
          <button type="button" onClick={() => setOpen(open === r.id ? null : r.id)} className="w-full px-3 py-2 text-left">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] text-faint">{r.taskId}</span>
              <Badge tone={r.status === 'completed' ? 'ok' : r.status === 'refused' ? 'bad' : r.status === 'partial' ? 'warn' : 'neutral'}>{r.status}</Badge>
              <span className="ml-auto text-[11px] text-faint">{timeAgo(r.createdAt)}</span>
            </div>
            <p className="mt-0.5 truncate text-[13.5px]">{r.goal}</p>
            {!compact && <p className="text-[11.5px] text-muted">{label(r.intent ?? '')} · {r.steps} steps · {r.toolCalls} tool calls · {r.replans} replans · {r.latencyMs ?? 0} ms · {r.engine}</p>}
          </button>
          {open === r.id && (
            <div className="border-t border-line px-3 py-2 text-[12.5px]">
              <ol className="space-y-0.5">
                {r.plan.map((s) => (
                  <li key={s.id}><span className={cx(s.status === 'done' ? 'text-ok' : s.status === 'failed' ? 'text-bad' : 'text-faint')}>●</span> <span className="font-medium">{s.agent}</span> — {s.label}{s.origin !== 'plan' && <span className="text-gold"> ({s.origin})</span>}<span className="block pl-4 text-muted">{s.summary}</span></li>
                ))}
              </ol>
              {!compact && (
                <table className="mt-2 w-full text-left text-[11.5px]">
                  <thead className="text-faint"><tr><th>Agent</th><th>Tool</th><th>Risk</th><th>Status</th><th>ms</th></tr></thead>
                  <tbody>{r.tools.map((t, i) => <tr key={i} className="border-t border-line"><td>{t.agent}</td><td className="font-mono">{t.tool}</td><td>{t.risk}</td><td>{t.status}</td><td>{t.latencyMs}</td></tr>)}</tbody>
                </table>
              )}
            </div>
          )}
        </li>
      ))}
    </ul>
  )
  return compact ? body : <Wrap title="Agent activity" intro="Every run: the plan, how it adapted, and every tool call the gateway allowed or denied.">{body}</Wrap>
}

export function AuditView({ kase }: { kase: Case }) {
  const { data } = useCaseView<{ audit: { id: string; at: string; action: string; result: string; risk: string; agent: string | null; taskId: string | null; detail: string | null }[]; security: { id: string; at: string; kind: string; source: string; snippet: string; actions: string[] }[] }>(kase.id, 'audit')
  return (
    <Wrap title="Audit log" intro="Who did what, with which risk level and result. Document content is never logged.">
      {!!data?.security.length && (
        <div className="mb-4 space-y-1.5">
          <SectionTitle>Security events</SectionTitle>
          {data.security.map((s) => (
            <div key={s.id} className="rounded-lg border border-bad/30 bg-bad-soft/40 px-3 py-2 text-[13px]">
              <p className="font-medium text-bad">{label(s.kind)} — {s.source} <span className="font-normal text-faint">{timeAgo(s.at)}</span></p>
              <p className="font-mono text-[12px] text-muted">“{s.snippet}”</p>
              <p className="text-[12px] text-muted">{s.actions.join(' · ')}</p>
            </div>
          ))}
        </div>
      )}
      <div className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-left text-[12.5px]">
          <thead className="bg-surface-2 text-[11px] uppercase tracking-wide text-muted"><tr><th className="px-3 py-2">When</th><th>Action</th><th>Risk</th><th>Result</th><th>Detail</th></tr></thead>
          <tbody>{(data?.audit ?? []).map((a) => (
            <tr key={a.id} className="border-t border-line"><td className="whitespace-nowrap px-3 py-1.5 text-muted">{timeAgo(a.at)}</td><td className="font-mono">{a.action}</td>
              <td><Badge tone={a.risk === 'HIGH' ? 'bad' : a.risk === 'MEDIUM' ? 'warn' : 'neutral'}>{a.risk}</Badge></td><td>{a.result}</td><td className="text-muted">{a.detail}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </Wrap>
  )
}

