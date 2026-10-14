import { useQueryClient } from '@tanstack/react-query'
import { Bell, Bookmark, FilePen, Inbox } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Badge, Button, EmptyState, ErrorNote, Skeleton, Textarea } from '../../components/ui'
import { api, errorMessage } from '../../lib/api'
import { useApi, useCases, useNotifications } from '../../lib/queries'
import type { Case } from '../../lib/types'
import { label, timeAgo } from '../../lib/util'

function Page({ title, intro, children }: { title: string; intro?: string; children: ReactNode }) {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <h1 className="font-serif text-2xl">{title}</h1>
        {intro && <p className="mt-1 text-sm text-muted">{intro}</p>}
        <div className="mt-6">{children}</div>
      </div>
    </div>
  )
}

function CaseItems<T extends { id: string }>({ kase, view, render }: { kase: Case; view: string; render: (x: T) => ReactNode }) {
  const { data } = useApi<T[]>([view, kase.id], `/cases/${kase.id}/${view}`)
  if (!data?.length) return null
  return (
    <section className="mb-5">
      <Link to={`/cases/${kase.id}?view=${view === 'findings' ? 'saved' : view}`} className="text-[12px] font-semibold uppercase tracking-wider text-muted hover:text-fg">{kase.title}</Link>
      <ul className="mt-1.5 space-y-1.5">{data.map((x) => <li key={x.id}>{render(x)}</li>)}</ul>
    </section>
  )
}

export function DraftsPage() {
  const { data: cases, isLoading } = useCases()
  const nav = useNavigate()
  return (
    <Page title="Drafts" intro="Every draft across your cases. Drafts are built from verified facts and need your approval before anything is shared.">
      {isLoading ? <Skeleton className="h-40" /> : !cases?.length ? <EmptyState icon={<FilePen className="size-6" />} title="No cases yet" /> :
        cases.map((c) => (
          <CaseItems<{ id: string; title: string; status: string; version: number; createdAt: string }> key={c.id} kase={c} view="drafts" render={(d) => (
            <button type="button" onClick={() => nav(`/cases/${c.id}?view=drafts&draft=${d.id}`)} className="flex w-full items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-left hover:bg-surface-2">
              <FilePen className="size-4 text-muted" /><span className="flex-1 truncate">{d.title}</span>
              <Badge tone={d.status === 'approved' ? 'ok' : d.status === 'shared' ? 'info' : 'warn'}>{d.status}</Badge>
              <span className="text-[12px] text-faint">v{d.version} · {timeAgo(d.createdAt)}</span>
            </button>
          )} />
        ))}
    </Page>
  )
}

export function SavedPage() {
  const { data: cases } = useCases()
  return (
    <Page title="Saved findings" intro="Answers you saved, with the citations they rest on.">
      {(cases ?? []).map((c) => (
        <CaseItems<{ id: string; title: string; createdAt: string }> key={c.id} kase={c} view="findings" render={(f) => (
          <Link to={`/cases/${c.id}?view=saved`} className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 hover:bg-surface-2">
            <Bookmark className="size-4 text-gold" /><span className="flex-1 truncate font-serif">{f.title}</span><span className="text-[12px] text-faint">{timeAgo(f.createdAt)}</span>
          </Link>
        )} />
      ))}
      {!cases?.length && <EmptyState title="Nothing saved yet" />}
    </Page>
  )
}

interface ConflictCheck {
  status: 'PENDING_REVIEW' | 'CLEARED' | 'CONFLICT'
  names: { name: string; role: string }[]
  automatedHits: { reference: string; name: string; role: string; field: string }[]
}
/** Until the conflict check is cleared the API sends only the conflict-check view: no title, summary, note or client name. */
interface Req {
  id: string; status: string; caseId: string | null; clientName?: string; note?: string; createdAt: string; conflictCheck: ConflictCheck
  intake: { matterType: string; urgency: string; city: string; title?: string; documents?: number; securityFlags?: string[]
    structured?: { problem?: string; timeline?: { date_text: string; event: string }[]; documents_mentioned?: string[]; missing_information?: string[]; questions_for_client?: string[]; complexity?: string } }
}

function ConflictPanel({ r, onDone }: { r: Req; onDone: () => void }) {
  const [note, setNote] = useState('')
  const [err, setErr] = useState('')
  const c = r.conflictCheck
  const decide = async (clear: boolean) => {
    setErr('')
    try { await api.post(`/requests/${r.id}/conflict-check`, { clear, note }); onDone() } catch (e) { setErr(errorMessage(e)) }
  }
  return (
    <div className="mt-2 space-y-2 rounded-lg border border-line bg-surface-2 p-3 text-[13px]">
      <p className="font-medium">Conflict check before you see the matter</p>
      <p className="text-muted">Names involved: {c.names.map((n) => `${n.name} (${n.role === 'client' ? 'client' : 'other party'})`).join(', ')}</p>
      {c.automatedHits.length ? (
        <ul className="text-bad">{c.automatedHits.map((h, i) => <li key={i}>Possible match: “{h.name}” appears in your firm's matter {h.reference} ({h.field === 'client' ? 'client name' : 'matter title'})</li>)}</ul>
      ) : <p className="text-muted">No match found in your firm's matters. This search is an aid: check your own records too.</p>}
      <Textarea rows={2} placeholder="Internal note (never shown to the client)" value={note} onChange={(e) => setNote(e.target.value)} />
      <ErrorNote>{err}</ErrorNote>
      <div className="flex gap-2">
        <Button size="sm" variant="primary" onClick={() => decide(true)}>No conflict — show the matter</Button>
        <Button size="sm" variant="danger" onClick={() => decide(false)}>Conflict — decline</Button>
      </div>
      <p className="text-[12px] text-faint">Declining for a conflict tells the client only that you cannot take the matter.</p>
    </div>
  )
}

export function RequestsPage() {
  const { data, isLoading, refetch } = useApi<Req[]>(['requests'], '/requests')
  const [note, setNote] = useState<Record<string, string>>({})
  const [err, setErr] = useState('')
  const qc = useQueryClient()
  const nav = useNavigate()
  const respond = async (r: Req, accept: boolean) => {
    setErr('')
    try {
      const out = await api.post<{ caseId: string | null }>(`/requests/${r.id}/respond`, { accept, note: note[r.id] ?? '' })
      await refetch()
      qc.invalidateQueries({ queryKey: ['cases'] })
      if (accept && out.caseId) nav(`/cases/${out.caseId}`)
    } catch (e) { setErr(errorMessage(e)) }
  }
  return (
    <Page title="Client requests" intro="Clients who chose to contact you. You first check for conflicts using only the names involved; the matter is shown once you clear it. Accepting creates a private case in your workspace.">
      <ErrorNote>{err}</ErrorNote>
      {isLoading ? <Skeleton className="h-40" /> : !data?.length ? <EmptyState icon={<Inbox className="size-6" />} title="No requests yet">Requests appear once your profile is verified and published.</EmptyState> : (
        <ul className="space-y-3">
          {data.map((r) => {
            const cleared = r.conflictCheck.status === 'CLEARED'
            return (
            <li key={r.id} className="rounded-xl border border-line bg-surface p-4">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-medium">{cleared ? r.intake.title : 'New request'}</p>
                <Badge>{label(r.intake.matterType ?? 'other')}</Badge>
                {r.intake.urgency === 'urgent' && <Badge tone="bad">urgent</Badge>}
                <Badge tone={r.status === 'accepted' ? 'ok' : r.status === 'requested' ? 'info' : 'neutral'}>{r.status}</Badge>
                {r.conflictCheck.status === 'CONFLICT' && <Badge tone="bad">conflict</Badge>}
                <span className="ml-auto text-[12px] text-faint">{cleared ? `${r.clientName} · ` : ''}{r.intake.city} · {timeAgo(r.createdAt)}</span>
              </div>
              {r.status === 'requested' && !cleared && <ConflictPanel r={r} onDone={refetch} />}
              {cleared && r.intake.structured && <>
                <p className="mt-2 text-[14px]">{r.intake.structured.problem}</p>
                {!!r.intake.securityFlags?.length && <p className="mt-1 text-[12px] text-bad">The client's text contained instruction-like content; it was treated as plain text.</p>}
                <div className="mt-2 grid gap-3 text-[13px] sm:grid-cols-2">
                  {!!r.intake.structured.timeline?.length && <div><p className="font-medium">Timeline (as described)</p><ul className="text-muted">{r.intake.structured.timeline.map((t, i) => <li key={i}>{t.date_text}: {t.event.slice(0, 120)}</li>)}</ul></div>}
                  {!!r.intake.structured.questions_for_client?.length && <div><p className="font-medium">Questions to ask</p><ul className="text-muted">{r.intake.structured.questions_for_client.map((q) => <li key={q}>• {q}</li>)}</ul></div>}
                </div>
                {r.note && <p className="mt-2 text-[13px] italic text-muted">“{r.note}”</p>}
              </>}
              {r.status === 'requested' && cleared ? (
                <div className="mt-3 space-y-2">
                  <Textarea rows={2} placeholder="Note to the client (optional)" value={note[r.id] ?? ''} onChange={(e) => setNote({ ...note, [r.id]: e.target.value })} />
                  <div className="flex gap-2">
                    <Button variant="primary" onClick={() => respond(r, true)}>Accept & open case</Button>
                    <Button variant="ghost" onClick={() => respond(r, false)}>Decline</Button>
                  </div>
                </div>
              ) : r.caseId && <Link to={`/cases/${r.caseId}`} className="mt-2 inline-block text-[13px] text-accent hover:underline">Open case →</Link>}
            </li>
            )
          })}
        </ul>
      )}
    </Page>
  )
}

export function NotificationsPage() {
  const { data, refetch } = useNotifications()
  const nav = useNavigate()
  const open = async (id: string, link: string | null) => {
    await api.post(`/notifications/${id}/read`)
    refetch()
    if (link) nav(link)
  }
  return (
    <Page title="Notifications">
      {!data?.length ? <EmptyState icon={<Bell className="size-6" />} title="You're all caught up" /> : (
        <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
          {data.map((n) => (
            <li key={n.id}>
              <button type="button" onClick={() => open(n.id, n.link)} className="flex w-full items-start gap-2 px-4 py-3 text-left hover:bg-surface-2">
                {!n.read && <span className="mt-2 size-2 shrink-0 rounded-full bg-accent" />}
                <div className="flex-1"><p className={n.read ? 'text-muted' : 'font-medium'}>{n.title}</p>{n.body && <p className="text-[13px] text-muted">{n.body}</p>}</div>
                <span className="text-[12px] text-faint">{timeAgo(n.createdAt)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Page>
  )
}

export { Page }
