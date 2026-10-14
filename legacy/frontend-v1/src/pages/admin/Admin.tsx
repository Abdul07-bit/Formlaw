import { AnimatePresence, motion } from 'framer-motion'
import {
  Activity, BadgeCheck, CheckCircle2, Clock, Cpu, Database, FileBadge2, IdCard, KeyRound, Lock, RefreshCw, ScanFace,
  ShieldAlert, ShieldCheck, Timer, Users, Wrench, XCircle,
} from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { RelatedCaseCard } from '../../components/case/Lawyers'
import { SecurityEventCard } from '../../components/case/Evidence'
import { Avatar, Badge, Button, cx, EmptyState, Field, inputCls, PageHeader, Stat } from '../../components/ui'
import { useDB } from '../../hooks/useStore'
import {
  decideKyc, loadAudit, loadHealth, loadKycQueue, loadPendingLawyerCases, loadSecurityEvents, loadUsers, verifyLawyerCase,
  type AdminUser, type SystemHealth,
} from '../../services/admin'
import { errorMessage } from '../../services/api/client'
import type { AuditEntry, KycCheck } from '../../types'

function useLoad(fn: () => Promise<unknown>) {
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(true)
  const run = () => { setBusy(true); setErr(''); fn().catch((e) => setErr(errorMessage(e))).finally(() => setBusy(false)) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(run, [])
  return { err, busy, reload: run }
}

const ErrorNote = ({ err }: { err: string }) => (err ? <p className="mb-4 rounded-2xl bg-rose-50 p-3 text-sm font-bold text-rose-700" role="alert">{err}</p> : null)

const CHECK_ICON: Record<KycCheck['type'], ReactNode> = {
  qualification: <FileBadge2 className="size-4" />, government_id: <IdCard className="size-4" />,
  professional_registration: <BadgeCheck className="size-4" />, face_match: <ScanFace className="size-4" />, judicial_status: <BadgeCheck className="size-4" />,
}

// ── Verification desk ────────────────────────────────────────────────────────
export function AdminKyc() {
  const lawyers = useDB((d) => d.lawyers)
  const { err } = useLoad(loadKycQueue)
  const pending = useMemo(() => lawyers.filter((l) => l.kyc === 'pending' && l.kycSubmission), [lawyers])
  const reviewed = useMemo(() => lawyers.filter((l) => l.kycSubmission?.reviewedAt), [lawyers])
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [actionErr, setActionErr] = useState('')
  const decide = (id: string, approve: boolean) => {
    setActionErr('')
    decideKyc(id, approve, notes[id] ?? '').catch((e) => setActionErr(errorMessage(e)))
  }
  return (
    <>
      <PageHeader eyebrow="Admin" title="Verification desk" subtitle="Provider checks run server-side. You make the final decision and record what you checked. Only this decision can publish a profile." />
      <ErrorNote err={err || actionErr} />
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Awaiting review" value={pending.length} icon={<Clock className="size-4" />} tone="amber" />
        <Stat label="Verified professionals" value={lawyers.filter((l) => l.kyc === 'verified').length} icon={<BadgeCheck className="size-4" />} tone="green" />
        <Stat label="Rejected" value={lawyers.filter((l) => l.kyc === 'rejected').length} icon={<XCircle className="size-4" />} tone="red" />
      </div>
      <h2 className="mb-4 mt-8 text-xl">Queue</h2>
      {pending.length === 0 ? (
        <EmptyState icon={<ScanFace className="size-7" />} title="Queue is clear" body="New submissions appear here. Demo: register as an advocate, complete KYC, then return with the Admin persona." />
      ) : (
        <div className="space-y-5">
          <AnimatePresence>
            {pending.map((l) => {
              const s = l.kycSubmission!
              const demo = s.checks.some((c) => c.demo)
              return (
                <motion.div key={l.id} layout exit={{ opacity: 0, x: 60 }} className="card overflow-hidden">
                  <div className="flex flex-col gap-4 border-b border-sky-100 p-5 md:flex-row md:items-center">
                    <Avatar initials={l.initials} hue={l.photoHue} size={52} />
                    <div className="flex-1"><p className="text-lg font-extrabold">{l.name}</p><p className="text-sm font-semibold text-ink-soft">{l.title} · {l.city || '—'} · {l.practiceAreas.join(', ') || 'no areas'} · {l.experienceYears} yrs · {l.barCouncil} {l.enrolmentNo}</p></div>
                    <Badge tone="amber">Submitted {new Date(s.submittedAt).toLocaleString('en-IN')}</Badge>
                  </div>
                  <div className="grid gap-5 p-5 md:grid-cols-[1fr_300px]">
                    <div>
                      <ul className="grid gap-2 sm:grid-cols-2">
                        {s.checks.map((c) => (
                          <li key={c.type} className={cx('flex items-start gap-3 rounded-2xl p-3', c.status === 'passed' ? 'bg-emerald-50' : c.status === 'failed' ? 'bg-rose-50' : 'bg-amber-50')}>
                            <span className={c.status === 'failed' ? 'text-rose-600' : c.status === 'passed' ? 'text-emerald-600' : 'text-amber-600'}>{CHECK_ICON[c.type]}</span>
                            <span className="min-w-0"><span className="block text-sm font-extrabold capitalize">{c.type.replace(/_/g, ' ')} · {c.status.replace('_', ' ')}</span><span className="block truncate text-xs font-bold text-ink-soft">{c.provider}{c.reference ? ` · ${c.reference}` : ''}</span></span>
                          </li>
                        ))}
                      </ul>
                      <p className="mt-3 text-xs font-bold text-ink-soft">Documents: {s.degreeCertificate} · {s.idType}: {s.idCard}</p>
                      {demo && <p className="mt-3 flex items-start gap-2 rounded-2xl bg-violet-50 p-3 text-xs font-bold text-violet-800"><Wrench className="mt-0.5 size-4 shrink-0" />DEMO VERIFICATION PROVIDER: no real identity, qualification or face-match check ran. Verify against the Bar Council roll and the documents yourself before approving.</p>}
                    </div>
                    <div className="space-y-3">
                      <Field label="Reviewer note (required)"><textarea className={inputCls} rows={3} value={notes[l.id] ?? ''} onChange={(e) => setNotes((n) => ({ ...n, [l.id]: e.target.value }))} placeholder="What did you verify? e.g. enrolment confirmed on Bar Council roll" maxLength={500} /></Field>
                      <div className="grid grid-cols-2 gap-2">
                        <Button disabled={!notes[l.id]?.trim()} onClick={() => decide(l.id, true)} icon={<CheckCircle2 className="size-4" />}>Approve</Button>
                        <Button variant="secondary" disabled={!notes[l.id]?.trim()} onClick={() => decide(l.id, false)} icon={<XCircle className="size-4" />}>Reject</Button>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )
            })}
          </AnimatePresence>
        </div>
      )}
      {reviewed.length > 0 && (
        <>
          <h2 className="mb-3 mt-10 text-xl">Recently reviewed</h2>
          <ul className="card divide-y divide-sky-100">
            {reviewed.map((l) => <li key={l.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm font-bold"><span>{l.name}</span><span className="truncate text-ink-soft">{l.kycSubmission?.reviewNote}</span><Badge tone={l.kyc === 'verified' ? 'green' : 'red'}>{l.kyc}</Badge></li>)}
          </ul>
        </>
      )}
    </>
  )
}

// ── Case database moderation ─────────────────────────────────────────────────
export function AdminCases() {
  const completed = useDB((d) => d.completedCases)
  const lawyers = useDB((d) => d.lawyers)
  const { err } = useLoad(loadPendingLawyerCases)
  const [actionErr, setActionErr] = useState('')
  const pending = useMemo(() => completed.filter((c) => c.verificationStatus === 'pending'), [completed])
  const verified = useMemo(() => completed.filter((c) => c.verified), [completed])
  const verify = (id: string, ok: boolean) => { setActionErr(''); verifyLawyerCase(id, ok).catch((e) => setActionErr(errorMessage(e))) }
  return (
    <>
      <PageHeader eyebrow="Admin" title="Verified case database" subtitle="Lawyer-contributed, anonymised outcomes. Check them against court records before they power related-case retrieval and matching." />
      <ErrorNote err={err || actionErr} />
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Verified records" value={verified.length} icon={<Database className="size-4" />} tone="green" />
        <Stat label="Awaiting verification" value={pending.length} icon={<Clock className="size-4" />} tone="amber" />
        <Stat label="Contributing lawyers" value={new Set(completed.map((c) => c.lawyerId)).size} icon={<BadgeCheck className="size-4" />} />
      </div>
      <h2 className="mb-4 mt-8 text-xl">Pending submissions</h2>
      {pending.length === 0 ? <EmptyState icon={<Database className="size-7" />} title="Nothing to verify" body="Submissions from advocates appear here." /> : (
        <div className="grid gap-5 md:grid-cols-2">
          {pending.map((c) => (
            <div key={c.id} className="space-y-2">
              <RelatedCaseCard r={{ caseId: c.id, similarity: 0, sharedTerms: c.keywords.slice(0, 5) }} c={c} lawyer={lawyers.find((l) => l.id === c.lawyerId)} plain />
              <div className="grid grid-cols-2 gap-2"><Button size="sm" onClick={() => verify(c.id, true)}>Verify & publish</Button><Button size="sm" variant="secondary" onClick={() => verify(c.id, false)}>Reject</Button></div>
            </div>
          ))}
        </div>
      )}
      <h2 className="mb-4 mt-10 text-xl">Published</h2>
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{verified.map((c) => <RelatedCaseCard key={c.id} r={{ caseId: c.id, similarity: 0, sharedTerms: [] }} c={c} lawyer={lawyers.find((l) => l.id === c.lawyerId)} plain />)}</div>
    </>
  )
}

// ── Security events ──────────────────────────────────────────────────────────
const PERMISSIONS: [string, string, string][] = [
  ['Security Agent', 'scan_untrusted_text', 'LOW'], ['Case Review Agent', 'read_case_documents · extract_facts', 'LOW'],
  ['Retrieval / Research', 'search_case_evidence · search_legal_corpus', 'LOW'], ['Verification Agent', 'verify_claims', 'LOW'],
  ['Matching Agent', 'search_verified_lawyers', 'LOW'], ['Drafting Agent', 'compose_draft', 'MEDIUM'],
  ['Chat Agent', 'llm_generate (no tools, output re-verified)', 'MEDIUM'], ['External communication', 'human approval only', 'HIGH · approval'],
]

export function SecurityCenter() {
  const log = useDB((d) => d.securityLog)
  const { err, reload, busy } = useLoad(loadSecurityEvents)
  const count = (k: string) => log.filter((e) => e.kind === k).length
  return (
    <>
      <PageHeader eyebrow="Security" title="Security events" subtitle="Every document is untrusted. Agents only reach tools through the gateway, and high-risk actions need human approval."
        actions={<Button variant="secondary" size="sm" onClick={reload} loading={busy} icon={<RefreshCw className="size-4" />}>Refresh</Button>} />
      <ErrorNote err={err} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="Events" value={log.length} icon={<ShieldAlert className="size-4" />} tone="red" />
        <Stat label="Prompt injections" value={count('prompt_injection')} icon={<ShieldAlert className="size-4" />} tone="amber" />
        <Stat label="Tool / exfil attempts" value={count('tool_request') + count('exfiltration')} icon={<Wrench className="size-4" />} tone="amber" />
        <Stat label="Malicious files" value={count('malicious_file')} icon={<FileBadge2 className="size-4" />} tone="amber" />
        <Stat label="Auth abuse" value={count('auth_abuse')} icon={<KeyRound className="size-4" />} tone="amber" />
      </div>
      <div className="mt-8 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-4">
          {log.length ? log.map((e) => <SecurityEventCard key={e.id} e={e} />) : <EmptyState icon={<ShieldCheck className="size-7" />} title="No events" body="Run the demo case with the malicious document to see indirect prompt injection get blocked." />}
        </div>
        <div className="card p-6">
          <h3 className="text-lg">Agent permission model</h3>
          <p className="mt-1 text-xs font-semibold text-ink-soft">Enforced by the ToolGateway (default deny), independent of any model output.</p>
          <table className="mt-4 w-full text-left text-sm">
            <thead><tr className="text-xs uppercase tracking-wider text-ink-soft"><th className="pb-2">Agent</th><th className="pb-2">Tools</th><th className="pb-2">Risk</th></tr></thead>
            <tbody className="divide-y divide-sky-100 font-bold">
              {PERMISSIONS.map(([a, p, r]) => <tr key={a}><td className="py-2 pr-2">{a}</td><td className="py-2 pr-2 font-mono text-[11px]">{p}</td><td className="py-2"><Badge tone={r.startsWith('HIGH') ? 'red' : r === 'MEDIUM' ? 'amber' : 'green'}>{r}</Badge></td></tr>)}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}

// ── Audit logs ───────────────────────────────────────────────────────────────
export function AuditLogs() {
  const [rows, setRows] = useState<AuditEntry[]>([])
  const [filter, setFilter] = useState('')
  const { err, busy, reload } = useLoad(() => loadAudit(filter || undefined).then(setRows))
  return (
    <>
      <PageHeader eyebrow="Admin" title="Audit logs" subtitle="Actor, action, resource, risk and result for every important operation. Document content is never logged."
        actions={<div className="flex gap-2"><input className={cx(inputCls, 'h-10 w-56')} placeholder="Filter by action prefix" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter actions" /><Button size="sm" onClick={reload} loading={busy}>Apply</Button></div>} />
      <ErrorNote err={err} />
      <div className="card overflow-x-auto">
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead className="bg-sky-25 text-xs uppercase tracking-wider text-ink-soft"><tr>{['Time', 'Action', 'Actor', 'Resource', 'Agent · tool', 'Risk', 'Result', 'Detail'].map((h) => <th key={h} className="px-4 py-3">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-sky-100 font-semibold">
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">{new Date(r.at).toLocaleString('en-IN')}</td>
                <td className="px-4 py-2 font-mono text-xs">{r.action}{r.taskId && <span className="block text-ink-soft">{r.taskId}</span>}</td>
                <td className="px-4 py-2 text-xs">{r.actorRole ?? '—'}</td>
                <td className="px-4 py-2 font-mono text-xs">{r.resourceType ? `${r.resourceType}:${r.resourceId?.slice(0, 8)}` : '—'}</td>
                <td className="px-4 py-2 text-xs">{r.agent ? `${r.agent}${r.tool ? ` · ${r.tool}` : ''}${r.latencyMs != null ? ` · ${r.latencyMs}ms` : ''}` : '—'}</td>
                <td className="px-4 py-2"><Badge tone={r.risk === 'HIGH' ? 'red' : r.risk === 'MEDIUM' ? 'amber' : 'green'}>{r.risk}</Badge></td>
                <td className="px-4 py-2"><Badge tone={r.result === 'success' || r.result === 'ok' ? 'green' : r.result === 'blocked' || r.result === 'denied' ? 'red' : 'amber'}>{r.result}</Badge></td>
                <td className="max-w-[260px] truncate px-4 py-2 text-xs text-ink-soft" title={r.detail ?? ''}>{r.verificationStatus ?? r.detail ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && !busy && <p className="p-6 text-center text-sm font-semibold text-ink-soft">No entries.</p>}
      </div>
    </>
  )
}

// ── Users ────────────────────────────────────────────────────────────────────
export function AdminUsers() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const { err } = useLoad(() => loadUsers().then(setUsers))
  return (
    <>
      <PageHeader eyebrow="Admin" title="Users" subtitle="Accounts on this deployment. Admins cannot read client case files." />
      <ErrorNote err={err} />
      <div className="card overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="bg-sky-25 text-xs uppercase tracking-wider text-ink-soft"><tr>{['Name', 'Email', 'Role', 'Status', 'Created'].map((h) => <th key={h} className="px-4 py-3">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-sky-100 font-semibold">
            {users.map((u) => (
              <tr key={u.id}>
                <td className="px-4 py-2">{u.name} {u.isDemo && <Badge tone="violet">Demo</Badge>}</td>
                <td className="px-4 py-2 text-ink-soft">{u.email}</td>
                <td className="px-4 py-2 capitalize">{u.role}</td>
                <td className="px-4 py-2"><Badge tone={u.status === 'active' ? 'green' : 'red'}>{u.status}</Badge></td>
                <td className="px-4 py-2 text-xs">{new Date(u.createdAt).toLocaleDateString('en-IN')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

// ── System health (live) ─────────────────────────────────────────────────────
function BarChart({ data, labels, unit }: { data: number[]; labels: string[]; unit: string }) {
  const [hover, setHover] = useState<number | null>(null)
  const max = Math.max(1, ...data)
  const w = 350 / Math.max(data.length, 1)
  return (
    <div className="relative">
      <svg viewBox="0 0 350 180" className="w-full" role="img" aria-label={`Bar chart: ${labels.map((l, i) => `${l} ${data[i]} ${unit}`).join(', ')}`}>
        {[0, 0.5, 1].map((g) => <line key={g} x1="0" x2="350" y1={150 - g * 130} y2={150 - g * 130} stroke="#e0f2fe" strokeWidth="1" />)}
        {data.map((v, i) => {
          const h = (v / max) * 130, x = i * w + w * 0.2, bw = w * 0.6
          return (
            <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={i * w} y="0" width={w} height="170" fill="transparent" />
              <motion.rect x={x} width={bw} rx="4" initial={{ y: 150, height: 0 }} animate={{ y: 150 - h, height: h }} transition={{ delay: i * 0.04, duration: 0.5 }} fill={hover === i ? '#0369a1' : '#0ea5e9'} />
              <text x={x + bw / 2} y="168" textAnchor="middle" fontSize="9" fontWeight="700" fill="#3b4a6b">{labels[i]}</text>
            </g>
          )
        })}
      </svg>
      {hover !== null && <div className="pointer-events-none absolute -top-2 rounded-xl bg-ink px-2.5 py-1 text-xs font-bold text-white" style={{ left: `${((hover * w + w / 2) / 350) * 100}%`, transform: 'translateX(-50%)' }}>{labels[hover]} · {data[hover]} {unit}</div>}
    </div>
  )
}

const short = (agent: string) => agent.replace(' Agent', '').replace('Case Review', 'Review').replace('Missing Info', 'Missing').replace('Contract Review', 'Contract')

export function Observability() {
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const { err, busy, reload } = useLoad(() => Promise.all([loadHealth().then(setHealth), loadAudit(undefined, 1000).then(setAudit)]))
  const stats = useMemo(() => {
    const calls = audit.filter((a) => a.action === 'agent.tool_call')
    const byAgent = new Map<string, number[]>()
    for (const c of calls) if (c.agent) byAgent.set(c.agent, [...(byAgent.get(c.agent) ?? []), c.latencyMs ?? 0])
    const agents = [...byAgent.keys()]
    return {
      reviews: audit.filter((a) => a.action === 'case.review' && a.result === 'success').length,
      failed: audit.filter((a) => a.result === 'error').length,
      denied: audit.filter((a) => a.result === 'denied' || a.result === 'blocked').length,
      calls: calls.length,
      agents, counts: agents.map((a) => byAgent.get(a)!.length),
      latency: agents.map((a) => { const l = byAgent.get(a)!; return Math.round(l.reduce((x, y) => x + y, 0) / l.length) }),
    }
  }, [audit])
  return (
    <>
      <PageHeader eyebrow="Admin" title="System health" subtitle="Live figures from the audit log and configuration. Nothing on this page is simulated."
        actions={<Button variant="secondary" size="sm" onClick={reload} loading={busy} icon={<RefreshCw className="size-4" />}>Refresh</Button>} />
      <ErrorNote err={err} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Completed reviews" value={stats.reviews} icon={<CheckCircle2 className="size-4" />} tone="green" hint="last 1,000 audit entries" />
        <Stat label="Agent tool calls" value={stats.calls} icon={<Cpu className="size-4" />} hint="via ToolGateway" />
        <Stat label="Denied / blocked" value={stats.denied} icon={<ShieldAlert className="size-4" />} tone="amber" />
        <Stat label="Errors" value={stats.failed} icon={<XCircle className="size-4" />} tone="red" />
        <Stat label="Database" value={health?.database ?? '—'} icon={<Database className="size-4" />} hint={health?.env} />
        <Stat label="Model provider" value={health?.llmProvider ?? '—'} icon={<Activity className="size-4" />} hint="none = extractive answers only" />
        <Stat label="KYC provider" value={health?.kycProvider ?? '—'} icon={<ScanFace className="size-4" />} tone={health?.kycProvider === 'demo' ? 'violet' : 'green'} />
        <Stat label="File encryption" value={health ? (health.fileEncryption ? 'AES-256-GCM' : 'OFF') : '—'} icon={<Lock className="size-4" />} tone={health?.fileEncryption ? 'green' : 'red'} />
        <Stat label="Users" value={health?.counts.users ?? '—'} icon={<Users className="size-4" />} />
        <Stat label="Demo mode" value={health ? (health.demoMode ? 'ON' : 'off') : '—'} icon={<Wrench className="size-4" />} tone={health?.demoMode ? 'amber' : 'green'} />
        <Stat label="Max agent steps" value={health?.limits.max_agent_steps ?? '—'} icon={<Timer className="size-4" />} hint={health ? `${health.limits.max_tool_calls} tool calls · ${health.limits.max_execution_seconds}s` : ''} />
        <Stat label="Token budget" value={health?.limits.max_token_budget?.toLocaleString('en-IN') ?? '—'} icon={<Timer className="size-4" />} hint={health ? `${health.limits.max_retries} retries` : ''} />
      </div>
      {stats.agents.length > 0 ? (
        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <div className="card p-6"><h3 className="text-lg">Tool calls by agent</h3><p className="mb-4 text-sm font-semibold text-ink-soft">Recent audit window</p><BarChart data={stats.counts} labels={stats.agents.map(short)} unit="calls" /></div>
          <div className="card p-6"><h3 className="text-lg">Average latency by agent</h3><p className="mb-4 text-sm font-semibold text-ink-soft">Milliseconds per tool call</p><BarChart data={stats.latency} labels={stats.agents.map(short)} unit="ms" /></div>
        </div>
      ) : <div className="mt-8"><EmptyState icon={<Activity className="size-7" />} title="No agent activity yet" body="Run a case review to populate these charts." /></div>}
    </>
  )
}
