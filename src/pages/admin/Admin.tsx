import { LogOut } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Brand } from '../../components/layout/AppShell'
import { Badge, Button, Card, EmptyState, ErrorNote, Field, IconButton, Input, Select, Tabs, Textarea } from '../../components/ui'
import { api, errorMessage } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useApi } from '../../lib/queries'
import { MATTER_TYPES, type ConnectionPolicyPublic, type Lawyer, type VerificationEvent } from '../../lib/types'
import { label, timeAgo } from '../../lib/util'

type Tab = 'verifications' | 'advocates' | 'policy' | 'corpus' | 'security' | 'audit' | 'health'
interface QueueItem { lawyer: Lawyer; checks: { id: string; type: string; status: string; provider: string; reference: string; documentName: string | null; result: { demo?: boolean; message?: string } }[] }

function StaffShell({ badge, intro, children }: { badge: string; intro: string; children: ReactNode }) {
  const { logout, user } = useAuth()
  const nav = useNavigate()
  return (
    <div className="h-full overflow-y-auto">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-2.5">
          <Brand /><Badge tone="accent">{badge}</Badge>
          <span className="ml-auto text-[13px] text-muted">{user?.name}</span>
          <IconButton label="Sign out" onClick={() => logout().then(() => nav('/'))}><LogOut className="size-4" /></IconButton>
        </div>
      </header>
      <div className="mx-auto max-w-5xl px-4 py-6">
        <p className="mb-4 text-sm text-muted">{intro}</p>
        {children}
      </div>
    </div>
  )
}

export default function Admin() {
  const [tab, setTab] = useState<Tab>('verifications')
  return (
    <StaffShell badge="admin" intro="Platform administration. Administrators verify professionals, draft connection policies and monitor security; they cannot open any case content or approve a connection policy.">
      <Tabs<Tab> value={tab} onChange={setTab} items={[{ id: 'verifications', label: 'Verification queue' }, { id: 'advocates', label: 'Advocates' }, { id: 'policy', label: 'Connection policy' }, { id: 'corpus', label: 'Legal corpus' }, { id: 'security', label: 'Security events' }, { id: 'audit', label: 'Audit log' }, { id: 'health', label: 'System' }]} />
      <div className="mt-4">
        {tab === 'verifications' && <Verifications />}
        {tab === 'advocates' && <Advocates />}
        {tab === 'policy' && <PolicyAdmin mode="admin" />}
        {tab === 'corpus' && <Coverage />}
        {tab === 'security' && <Security />}
        {tab === 'audit' && <Audit />}
        {tab === 'health' && <Health />}
      </div>
    </StaffShell>
  )
}

/** Compliance reviewers: approve or reject connection policies; no case content, no platform administration. */
export function CompliancePage() {
  const { data } = useApi<{ id: string; at: string; action: string; result: string; actorRole: string | null; detail: string | null }[]>(['complianceAudit'], '/compliance/audit')
  return (
    <StaffShell badge="compliance" intro="Compliance review. A connection policy takes effect only when you approve it, citing a counsel review of that exact version. You cannot draft policies or open case content.">
      <PolicyAdmin mode="compliance" />
      <h2 className="mt-8 mb-2 text-[12px] font-semibold uppercase tracking-wider text-muted">Policy and verification decisions</h2>
      <ul className="space-y-1 text-[12.5px]">{(data ?? []).map((a) => (
        <li key={a.id} className="flex gap-2 border-b border-line py-1"><span className="w-24 shrink-0 text-faint">{timeAgo(a.at)}</span><span className="font-mono">{a.action}</span><span className="text-muted">{a.actorRole}</span><span className="text-muted">{a.detail}</span></li>
      ))}</ul>
    </StaffShell>
  )
}

interface CoverageReport {
  window: { start: string; end: string }; overall: string; statement: string; gaps: string[]
  totals: { judgmentsInWindow: number; courts: number; awaitingReview: number }
  sources: { key: string; name: string; registryStatus: string; authoritative: boolean; ingested?: number; awaitingReview?: number; kinds: string[]
    years?: Record<string, { status: string; ingested: number; discovered?: number; note?: string }> }[]
}

function Coverage() {
  const { data } = useApi<CoverageReport>(['coverage'], '/admin/corpus/coverage')
  if (!data) return null
  const judgmentSources = data.sources.filter((s) => s.kinds.includes('judgment') && s.registryStatus === 'APPROVED')
  return (
    <div className="space-y-4 text-[13px]">
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-medium">{data.window.start} → {data.window.end}</p>
          <Badge tone={data.overall === 'COMPLETE' ? 'ok' : 'bad'}>{data.overall}</Badge>
        </div>
        <p className="mt-1 text-muted">{data.statement}</p>
        <p className="mt-1 text-muted">{data.totals.judgmentsInWindow} judgments in window · {data.totals.courts} court(s) · {data.totals.awaitingReview} awaiting review</p>
      </Card>
      <div><p className="mb-1 font-medium">Gaps</p><ul className="space-y-0.5 text-muted">{data.gaps.map((g) => <li key={g}>• {g}</li>)}</ul></div>
      {judgmentSources.map((s) => (
        <div key={s.key}>
          <p className="mb-1 font-medium">{s.name}{!s.authoritative && <span className="ml-2 text-[12px] font-normal text-warn">third-party copy — verify against the official record</span>}</p>
          <div className="overflow-x-auto rounded-xl border border-line bg-surface">
            <table className="w-full text-left text-[12.5px]">
              <thead className="bg-surface-2 text-[11px] uppercase tracking-wide text-muted"><tr><th className="px-3 py-1.5">Year</th><th>Status</th><th>Discovered</th><th>Ingested</th><th>Note</th></tr></thead>
              <tbody>{Object.entries(s.years ?? {}).map(([y, v]) => (
                <tr key={y} className="border-t border-line"><td className="px-3 py-1.5">{y}</td><td><Badge tone={v.status === 'COMPLETE' ? 'ok' : v.status === 'PARTIAL' ? 'warn' : 'neutral'}>{v.status}</Badge></td><td>{v.discovered ?? '—'}</td><td>{v.ingested}</td><td className="text-muted">{v.note}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      ))}
      <p className="text-[12px] text-faint">Same report as <span className="font-mono">python -m app.ingestion report</span>. Full breakdown by court and month is in the CLI output.</p>
    </div>
  )
}

function Verifications() {
  const { data, refetch } = useApi<QueueItem[]>(['adminQueue'], '/admin/verifications')
  if (!data?.length) return <EmptyState title="No verifications waiting" />
  return <div className="space-y-3">{data.map((q) => <Decision key={q.lawyer.id} q={q} onDone={refetch} />)}</div>
}

function Decision({ q, onDone }: { q: QueueItem; onDone: () => void }) {
  const [note, setNote] = useState('')
  const [areas, setAreas] = useState<string[]>(q.lawyer.practiceAreas)
  const [judicial, setJudicial] = useState(false)
  const [err, setErr] = useState('')
  const [roll, setRoll] = useState({ source: q.lawyer.barCouncil ? `${q.lawyer.barCouncil} — roll of advocates` : '', reference: '', checkedOn: '', enrolmentNumberMatches: false, nameMatches: false })
  const hasJudicial = q.checks.some((c) => c.type === 'judicial_status')
  const rollDone = roll.source.length >= 5 && roll.reference.length >= 3 && !!roll.checkedOn && roll.enrolmentNumberMatches && roll.nameMatches
  const decide = async (approve: boolean) => {
    try {
      await api.post(`/admin/verifications/${q.lawyer.id}/decision`, { approve, note, verifiedAreas: approve ? areas : [], judicialStatus: judicial, ...(approve ? { barRollCheck: roll } : {}) })
      onDone()
    } catch (e) { setErr(errorMessage(e)) }
  }
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-medium">{q.lawyer.name}</p><Badge tone="warn">{label(q.lawyer.verificationStatus.toLowerCase())}</Badge>
        <span className="text-[13px] text-muted">{q.lawyer.barCouncil} · {q.lawyer.enrolmentNumber} · {q.lawyer.city}</span>
      </div>
      <ul className="mt-2 grid gap-1 text-[13px] sm:grid-cols-2">
        {q.checks.map((c) => (
          <li key={c.id} className="rounded-lg border border-line px-2.5 py-1.5">
            <span className="font-medium">{label(c.type)}</span> — {label(c.status)} <span className="text-faint">({c.provider})</span>
            {c.result.demo && <p className="text-[12px] text-warn">{c.result.message}</p>}
          </li>
        ))}
      </ul>
      <div className="mt-3 space-y-2">
        <Field label="Verified practice areas"><div className="flex flex-wrap gap-1.5">{MATTER_TYPES.map((m) => (
          <button key={m} type="button" onClick={() => setAreas(areas.includes(m) ? areas.filter((x) => x !== m) : [...areas, m])}
            className={`rounded-full border px-2 py-0.5 text-[12px] ${areas.includes(m) ? 'border-accent bg-accent-soft text-accent' : 'border-line text-muted'}`}>{m}</button>
        ))}</div></Field>
        <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" disabled={!hasJudicial} checked={judicial} onChange={(e) => setJudicial(e.target.checked)} />Judicial status confirmed by official check {!hasJudicial && <span className="text-faint">(no judicial-status check submitted)</span>}</label>
        <fieldset className="space-y-2 rounded-lg border border-line p-3">
          <legend className="px-1 text-[12px] font-medium">Official Bar Council roll check (required to verify)</legend>
          <p className="text-[12px] text-faint">Look the advocate up on the State Bar Council's own roll. Uploaded ID cards are not proof of current standing.</p>
          <div className="grid gap-2 sm:grid-cols-3">
            <Field label="Roll checked"><Input value={roll.source} onChange={(e) => setRoll({ ...roll, source: e.target.value })} /></Field>
            <Field label="Link or register reference"><Input value={roll.reference} onChange={(e) => setRoll({ ...roll, reference: e.target.value })} /></Field>
            <Field label="Checked on"><Input type="date" value={roll.checkedOn} max={new Date().toISOString().slice(0, 10)} onChange={(e) => setRoll({ ...roll, checkedOn: e.target.value })} /></Field>
          </div>
          <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={roll.enrolmentNumberMatches} onChange={(e) => setRoll({ ...roll, enrolmentNumberMatches: e.target.checked })} />The roll shows enrolment number {q.lawyer.enrolmentNumber}</label>
          <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={roll.nameMatches} onChange={(e) => setRoll({ ...roll, nameMatches: e.target.checked })} />The name on the roll matches {q.lawyer.name}</label>
        </fieldset>
        <Field label="Decision note (required)"><Input value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        <ErrorNote>{err}</ErrorNote>
        <div className="flex gap-2"><Button variant="primary" disabled={note.length < 3 || !rollDone} onClick={() => decide(true)}>Verify</Button><Button variant="danger" disabled={note.length < 3} onClick={() => decide(false)}>Reject</Button></div>
      </div>
    </Card>
  )
}

const STATUS_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'neutral'> = { VERIFIED: 'ok', PENDING: 'warn', UNDER_REVIEW: 'warn', REJECTED: 'bad', EXPIRED: 'bad', SUSPENDED: 'bad' }

function Advocates() {
  const [status, setStatus] = useState('')
  const { data, refetch } = useApi<Lawyer[]>(['adminLawyers', status], `/admin/lawyers${status ? `?status=${status}` : ''}`)
  return (
    <div className="space-y-3">
      <Field label="Status"><Select value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">All</option>{Object.keys(STATUS_TONE).concat('NOT_STARTED').map((s) => <option key={s} value={s}>{label(s.toLowerCase())}</option>)}
      </Select></Field>
      {!data?.length ? <EmptyState title="No advocates match" /> : <ul className="space-y-2">{data.map((l) => <AdvocateRow key={l.id} l={l} onDone={refetch} />)}</ul>}
    </div>
  )
}

function AdvocateRow({ l, onDone }: { l: Lawyer; onDone: () => void }) {
  const [note, setNote] = useState('')
  const [open, setOpen] = useState(false)
  const [err, setErr] = useState('')
  const { data: history } = useApi<VerificationEvent[]>(['adminHistory', l.id], open ? `/admin/verifications/${l.id}/history` : null)
  const act = async (kind: 'suspend' | 'reinstate') => {
    setErr('')
    try { await api.post(`/admin/verifications/${l.id}/${kind}`, { note }); setNote(''); onDone() } catch (e) { setErr(errorMessage(e)) }
  }
  return (
    <li className="rounded-xl border border-line bg-surface p-3 text-[13px]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{l.name}</span>
        <Badge tone={STATUS_TONE[l.verificationStatus] ?? 'neutral'}>{label(l.verificationStatus.toLowerCase())}</Badge>
        {l.isDemo && <Badge>demo</Badge>}
        <span className="text-muted">{l.barCouncil} · {l.enrolmentNumber}</span>
        <button type="button" className="ml-auto text-accent hover:underline" onClick={() => setOpen(!open)}>{open ? 'Hide' : 'Manage'}</button>
      </div>
      {open && (
        <div className="mt-2 space-y-2">
          <ol className="space-y-0.5 text-[12.5px] text-muted">{(history ?? []).map((h, i) => <li key={i}>{h.from} → {h.to} · {h.by}{h.at ? ` · ${timeAgo(h.at)}` : ''}{h.reason ? ` — ${h.reason}` : ''}</li>)}</ol>
          {['VERIFIED', 'SUSPENDED'].includes(l.verificationStatus) && (
            <>
              <Field label="Reason (required, shown to the advocate)"><Input value={note} onChange={(e) => setNote(e.target.value)} /></Field>
              <ErrorNote>{err}</ErrorNote>
              {l.verificationStatus === 'VERIFIED'
                ? <Button size="sm" variant="danger" disabled={note.trim().length < 3} onClick={() => act('suspend')}>Suspend verification</Button>
                : <Button size="sm" variant="primary" disabled={note.trim().length < 3} onClick={() => act('reinstate')}>Reinstate</Button>}
            </>
          )}
        </div>
      )}
    </li>
  )
}

interface PolicyRow {
  id: string; version: number; reviewStatus: string; publicDiscoveryEnabled: boolean; matchingEnabled: boolean; clientRequestsEnabled: boolean
  showFees: boolean; visibleProfileFields: string[]; requiredDisclosures: string[]; professionalRules: string[]; rationale: string
  reviewReference: string | null; reviewNote: string | null; draftedBy: string | null; reviewedAt: string | null; createdAt: string
}

type PolicyMode = 'admin' | 'compliance'

function PolicyAdmin({ mode }: { mode: PolicyMode }) {
  const { user } = useAuth()
  const { data, refetch } = useApi<{ effective: ConnectionPolicyPublic; policies: PolicyRow[]; allowedProfileFields: string[] }>(['policies', mode], `/${mode}/connection-policies`)
  if (!data) return null
  const e = data.effective
  return (
    <div className="space-y-4">
      <Card className="p-4 text-[13px]">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-medium">In force: {e.source === 'default' ? 'safe default (all connection features off)' : `version ${e.version}`}</p>
          <Badge tone={e.source === 'approved' ? 'ok' : e.source === 'demo' ? 'warn' : 'neutral'}>{e.source}</Badge>
        </div>
        <p className="mt-1 text-muted">{e.label}</p>
        <p className="mt-1 text-muted">Discovery {e.features.publicDiscovery ? 'on' : 'off'} · Matching {e.features.matching ? 'on' : 'off'} · Client requests {e.features.clientRequests ? 'on' : 'off'} · Fees {e.showFees ? 'shown' : 'hidden'}</p>
        <p className="mt-2 text-[12px] text-faint">Paid placement, paid ranking, outcome-based ranking and referral fees cannot be enabled by any policy. Administrators draft; a policy takes effect only when a compliance reviewer approves it, citing a counsel review of that exact version.</p>
      </Card>
      {mode === 'admin' && <PolicyDraft fields={data.allowedProfileFields} onDone={refetch} />}
      {!data.policies.length && <EmptyState title="No policy versions yet">{mode === 'admin' ? 'Draft one when counsel has advised on the connection model.' : 'Nothing to review.'}</EmptyState>}
      <ul className="space-y-2">{data.policies.map((r) => <PolicyCard key={r.id} r={r} mode={mode} mine={r.draftedBy === user?.id} onDone={refetch} />)}</ul>
    </div>
  )
}

function PolicyDraft({ fields, onDone }: { fields: string[]; onDone: () => void }) {
  const [open, setOpen] = useState(false)
  const [f, setF] = useState({ publicDiscoveryEnabled: false, matchingEnabled: false, clientRequestsEnabled: false, showFees: false })
  const [visible, setVisible] = useState<string[]>([])
  const [disclosures, setDisclosures] = useState('')
  const [rules, setRules] = useState('')
  const [rationale, setRationale] = useState('')
  const [err, setErr] = useState('')
  const lines = (s: string) => s.split('\n').map((x) => x.trim()).filter(Boolean)
  const submit = async () => {
    setErr('')
    try {
      await api.post('/admin/connection-policies', { ...f, visibleProfileFields: visible, requiredDisclosures: lines(disclosures), professionalRules: lines(rules), rationale })
      setOpen(false); onDone()
    } catch (e) { setErr(errorMessage(e)) }
  }
  if (!open) return <Button onClick={() => setOpen(true)}>Draft a new policy version</Button>
  const toggle = (k: keyof typeof f) => <label key={k} className="flex items-center gap-2"><input type="checkbox" checked={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.checked })} />{label(k.replace(/Enabled$/, '').replace(/([A-Z])/g, '_$1').toLowerCase())}</label>
  return (
    <Card className="space-y-3 p-4 text-[13px]">
      <p className="font-medium">New policy version (inactive until reviewed)</p>
      <div className="flex flex-wrap gap-4">{(Object.keys(f) as (keyof typeof f)[]).map(toggle)}</div>
      <Field label="Profile fields clients may see" hint="Name, verification status and the demo label are always shown">
        <div className="flex flex-wrap gap-1.5">{fields.map((x) => (
          <button key={x} type="button" onClick={() => setVisible(visible.includes(x) ? visible.filter((y) => y !== x) : [...visible, x])}
            className={`rounded-full border px-2 py-0.5 text-[12px] ${visible.includes(x) ? 'border-accent bg-accent-soft text-accent' : 'border-line text-muted'}`}>{x}</button>
        ))}</div>
      </Field>
      <Field label="Disclosures shown to clients before they share a matter" hint="One per line. Required if any feature is enabled."><Textarea rows={4} value={disclosures} onChange={(e) => setDisclosures(e.target.value)} /></Field>
      <Field label="Professional rules relied on" hint="One per line, e.g. BCI Rules Part VI Ch. II r.36"><Textarea rows={2} value={rules} onChange={(e) => setRules(e.target.value)} /></Field>
      <Field label="Rationale"><Textarea rows={3} value={rationale} onChange={(e) => setRationale(e.target.value)} /></Field>
      <ErrorNote>{err}</ErrorNote>
      <div className="flex gap-2"><Button variant="primary" disabled={rationale.trim().length < 10} onClick={submit}>Save draft</Button><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button></div>
    </Card>
  )
}

function PolicyCard({ r, mode, mine, onDone }: { r: PolicyRow; mode: PolicyMode; mine: boolean; onDone: () => void }) {
  const [ref, setRef] = useState('')
  const [note, setNote] = useState('')
  const [counsel, setCounsel] = useState(false)
  const [err, setErr] = useState('')
  const call = async (path: string, body: unknown) => {
    setErr('')
    try { await api.post(`/${mode}/connection-policies/${r.id}/${path}`, body); onDone() } catch (e) { setErr(errorMessage(e)) }
  }
  const tone = r.reviewStatus === 'APPROVED' ? 'ok' : r.reviewStatus === 'DEMO_ONLY' || r.reviewStatus === 'DRAFT' ? 'warn' : 'neutral'
  return (
    <li className="rounded-xl border border-line bg-surface p-3 text-[13px]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">Version {r.version}</span><Badge tone={tone}>{label(r.reviewStatus.toLowerCase())}</Badge>
        <span className="text-muted">discovery {r.publicDiscoveryEnabled ? 'on' : 'off'} · matching {r.matchingEnabled ? 'on' : 'off'} · requests {r.clientRequestsEnabled ? 'on' : 'off'}</span>
        <span className="ml-auto text-faint">{timeAgo(r.createdAt)}</span>
      </div>
      <p className="mt-1 text-muted">{r.rationale}</p>
      {!!r.requiredDisclosures.length && <ul className="mt-1 text-[12.5px] text-muted">{r.requiredDisclosures.map((d) => <li key={d}>• {d}</li>)}</ul>}
      {r.reviewReference && <p className="mt-1 text-[12px] text-faint">Review: {r.reviewReference}{r.reviewNote ? ` — ${r.reviewNote}` : ''}</p>}
      {r.reviewStatus === 'DRAFT' && mode === 'admin' && <p className="mt-2 text-[12px] text-faint">Waiting for a compliance reviewer. Administrators cannot approve policies.</p>}
      {r.reviewStatus === 'DRAFT' && mode === 'compliance' && (mine ? <p className="mt-2 text-[12px] text-faint">You drafted this version, so another reviewer must decide it.</p> : (
        <div className="mt-2 space-y-2">
          <Field label="Counsel review reference"><Input value={ref} onChange={(e) => setRef(e.target.value)} placeholder="e.g. opinion reference and date" /></Field>
          <Field label="Decision note"><Input value={note} onChange={(e) => setNote(e.target.value)} /></Field>
          <label className="flex items-center gap-2"><input type="checkbox" checked={counsel} onChange={(e) => setCounsel(e.target.checked)} />Qualified regulatory counsel reviewed this exact version</label>
          <div className="flex gap-2">
            <Button size="sm" variant="primary" disabled={!counsel || ref.trim().length < 3 || note.trim().length < 3} onClick={() => call('review', { approve: true, reviewReference: ref, note, counselReviewed: true })}>Approve</Button>
            <Button size="sm" variant="danger" disabled={ref.trim().length < 3 || note.trim().length < 3} onClick={() => call('review', { approve: false, reviewReference: ref, note, counselReviewed: counsel })}>Reject</Button>
          </div>
        </div>
      ))}
      {['APPROVED', 'DEMO_ONLY'].includes(r.reviewStatus) && (
        <div className="mt-2 flex items-end gap-2">
          <Field label="Revocation reason"><Input value={note} onChange={(e) => setNote(e.target.value)} /></Field>
          <Button size="sm" variant="danger" disabled={note.trim().length < 3} onClick={() => call('revoke', { note })}>Revoke</Button>
        </div>
      )}
      <ErrorNote>{err}</ErrorNote>
    </li>
  )
}

function Security() {
  const { data } = useApi<{ id: string; at: string; kind: string; risk: string; source: string; snippet: string; actions: string[] }[]>(['adminSecurity'], '/admin/security-events')
  if (!data?.length) return <EmptyState title="No security events" />
  return (
    <ul className="space-y-2">{data.map((s) => (
      <li key={s.id} className="rounded-lg border border-line bg-surface px-3 py-2 text-[13px]">
        <div className="flex items-center gap-2"><Badge tone={s.risk === 'HIGH' ? 'bad' : 'warn'}>{s.risk}</Badge><span className="font-medium">{label(s.kind)}</span><span className="text-muted">{s.source}</span><span className="ml-auto text-faint">{timeAgo(s.at)}</span></div>
        <p className="mt-1 font-mono text-[12px] text-muted">“{s.snippet}”</p><p className="text-[12px] text-faint">{s.actions.join(' · ')}</p>
      </li>
    ))}</ul>
  )
}

function Audit() {
  const { data } = useApi<{ id: string; at: string; action: string; result: string; risk: string; actorRole: string | null; agent: string | null; taskId: string | null; detail: string | null }[]>(['adminAudit'], '/admin/audit')
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-surface">
      <table className="w-full text-left text-[12.5px]">
        <thead className="bg-surface-2 text-[11px] uppercase tracking-wide text-muted"><tr><th className="px-3 py-2">When</th><th>Action</th><th>Actor</th><th>Risk</th><th>Result</th><th>Detail</th></tr></thead>
        <tbody>{(data ?? []).map((a) => (
          <tr key={a.id} className="border-t border-line"><td className="whitespace-nowrap px-3 py-1.5 text-muted">{timeAgo(a.at)}</td><td className="font-mono">{a.action}</td><td>{a.agent ?? a.actorRole}</td><td>{a.risk}</td><td>{a.result}</td><td className="text-muted">{a.detail}</td></tr>
        ))}</tbody>
      </table>
    </div>
  )
}

function Health() {
  const { data } = useApi<Record<string, unknown>>(['adminHealth'], '/admin/health')
  return <pre className="overflow-x-auto rounded-xl border border-line bg-surface p-4 text-[12px]">{JSON.stringify(data, null, 2)}</pre>
}
