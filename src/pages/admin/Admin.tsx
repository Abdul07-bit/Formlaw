import { AnimatePresence, motion } from 'framer-motion'
import {
  Activity, BadgeCheck, CheckCircle2, Clock, Cpu, Database, FileBadge2, IdCard, IndianRupee, ScanFace,
  ShieldAlert, ShieldCheck, Timer, Wrench, XCircle,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { RelatedCaseCard } from '../../components/case/Lawyers'
import { SecurityEventCard } from '../../components/case/Evidence'
import { Avatar, Badge, Button, DemoTag, EmptyState, Field, inputCls, PageHeader, Stat } from '../../components/ui'
import { useDB } from '../../hooks/useStore'
import { reviewKyc, verifyCompletedCase } from '../../services/api'

// ── KYC verification desk ────────────────────────────────────────────────────
export function AdminKyc() {
  const lawyers = useDB((d) => d.lawyers)
  const pending = useMemo(() => lawyers.filter((l) => l.kyc === 'pending'), [lawyers])
  const reviewed = useMemo(() => lawyers.filter((l) => l.kycSubmission?.reviewedAt), [lawyers])
  const [note, setNote] = useState('')
  return (
    <>
      <PageHeader eyebrow="Admin" title="KYC verification desk" subtitle="Approve advocates and judges after checking degree, identity and live face match. Approved profiles go live in the marketplace instantly." />
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Awaiting review" value={pending.length} icon={<Clock className="size-4" />} tone="amber" />
        <Stat label="Verified professionals" value={lawyers.filter((l) => l.kyc === 'verified').length} icon={<BadgeCheck className="size-4" />} tone="green" />
        <Stat label="Rejected" value={lawyers.filter((l) => l.kyc === 'rejected').length} icon={<XCircle className="size-4" />} tone="red" />
      </div>
      <h2 className="mb-4 mt-8 text-xl">Queue</h2>
      {pending.length === 0 ? (
        <EmptyState icon={<ScanFace className="size-7" />} title="Queue is clear" body="New submissions appear here. Demo: sign up as an advocate on the Get Started page, complete KYC, then return to this Admin persona." />
      ) : (
        <div className="space-y-5">
          <AnimatePresence>
            {pending.map((l) => {
              const s = l.kycSubmission!
              const auto = [
                { ok: true, label: 'Degree certificate received', detail: s.degreeCertificate, icon: <FileBadge2 className="size-4" /> },
                { ok: true, label: `${s.idType} received`, detail: s.idCard, icon: <IdCard className="size-4" /> },
                { ok: s.livenessPassed, label: 'Liveness check', detail: s.livenessPassed ? 'Passed' : 'Failed', icon: <ScanFace className="size-4" /> },
                { ok: s.faceMatchScore >= 0.85, label: 'Face match vs ID photo', detail: `${Math.round(s.faceMatchScore * 100)}% (threshold 85%)`, icon: <ScanFace className="size-4" /> },
                { ok: /^[A-Z]{1,4}\/?\d{2,5}\/\d{4}$/.test(l.enrolmentNo) || l.enrolmentNo.length >= 4, label: 'Enrolment number format', detail: `${l.enrolmentNo} · ${l.barCouncil}`, icon: <BadgeCheck className="size-4" /> },
              ]
              return (
                <motion.div key={l.id} layout exit={{ opacity: 0, x: 60 }} className="card overflow-hidden">
                  <div className="flex flex-col gap-4 border-b border-sky-100 p-5 md:flex-row md:items-center">
                    <Avatar initials={l.initials} hue={l.photoHue} size={52} />
                    <div className="flex-1"><p className="text-lg font-extrabold">{l.name}</p><p className="text-sm font-semibold text-ink-soft">{l.title} · {l.city || '—'} · {l.practiceAreas.join(', ')} · {l.experienceYears} yrs</p></div>
                    <Badge tone="amber">Submitted {new Date(s.submittedAt).toLocaleString('en-IN')}</Badge>
                  </div>
                  <div className="grid gap-5 p-5 md:grid-cols-[1fr_300px]">
                    <ul className="grid gap-2 sm:grid-cols-2">
                      {auto.map((a) => (
                        <li key={a.label} className={`flex items-start gap-3 rounded-2xl p-3 ${a.ok ? 'bg-emerald-50' : 'bg-rose-50'}`}>
                          <span className={a.ok ? 'text-emerald-600' : 'text-rose-600'}>{a.ok ? <CheckCircle2 className="size-5" /> : <XCircle className="size-5" />}</span>
                          <span className="min-w-0"><span className="block text-sm font-extrabold">{a.label}</span><span className="block truncate text-xs font-bold text-ink-soft">{a.detail}</span></span>
                        </li>
                      ))}
                      <li className="flex items-center gap-2 rounded-2xl bg-violet-50 p-3 text-xs font-bold text-violet-800 sm:col-span-2"><Wrench className="size-4" />Backend: Bar Council roll lookup, document forgery detection, certified face-match provider.</li>
                    </ul>
                    <div className="space-y-3">
                      <Field label="Reviewer note"><textarea className={inputCls} rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional (required for rejection)" /></Field>
                      <div className="grid grid-cols-2 gap-2">
                        <Button onClick={() => { reviewKyc(l.id, true, note || 'All checks passed'); setNote('') }} icon={<CheckCircle2 className="size-4" />}>Approve</Button>
                        <Button variant="secondary" disabled={!note.trim()} onClick={() => { reviewKyc(l.id, false, note); setNote('') }} icon={<XCircle className="size-4" />}>Reject</Button>
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
  const pending = useMemo(() => completed.filter((c) => !c.verified), [completed])
  const verified = useMemo(() => completed.filter((c) => c.verified), [completed])
  return (
    <>
      <PageHeader eyebrow="Admin" title="Verified case database" subtitle="Lawyer-contributed outcomes are checked against court records before they power related-case retrieval and lawyer matching." />
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
              <div className="grid grid-cols-2 gap-2"><Button size="sm" onClick={() => verifyCompletedCase(c.id, true)}>Verify & publish</Button><Button size="sm" variant="secondary" onClick={() => verifyCompletedCase(c.id, false)}>Reject</Button></div>
            </div>
          ))}
        </div>
      )}
      <h2 className="mb-4 mt-10 text-xl">Published</h2>
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{verified.map((c) => <RelatedCaseCard key={c.id} r={{ caseId: c.id, similarity: 0, sharedTerms: [] }} c={c} lawyer={lawyers.find((l) => l.id === c.lawyerId)} plain />)}</div>
    </>
  )
}

// ── Security center ──────────────────────────────────────────────────────────
export function SecurityCenter() {
  const log = useDB((d) => d.securityLog)
  const injections = log.filter((e) => e.kind === 'prompt_injection').length
  const tools = log.filter((e) => e.kind !== 'prompt_injection').length
  return (
    <>
      <PageHeader eyebrow="Security" title="Security Center" subtitle="Every document is untrusted. Agents run with least-privilege permissions, and high-risk actions need human approval." actions={<Badge tone="green" icon={<ShieldCheck className="size-3.5" />}>System status: Protected</Badge>} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="Threats blocked" value={log.length} icon={<ShieldAlert className="size-4" />} tone="red" />
        <Stat label="Prompt injections" value={injections} icon={<ShieldAlert className="size-4" />} tone="amber" />
        <Stat label="Tool / exfil attempts" value={tools} icon={<Wrench className="size-4" />} tone="amber" />
        <Stat label="Data isolation violations" value={0} icon={<Database className="size-4" />} tone="green" />
        <Stat label="Unauthorized tool calls" value={0} icon={<Cpu className="size-4" />} tone="green" />
      </div>
      <div className="mt-8 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-4">
          <h2 className="text-xl">Security events</h2>
          {log.length ? log.map((e) => <SecurityEventCard key={e.id} e={e} />) : <EmptyState icon={<ShieldCheck className="size-7" />} title="No threats detected" body="Run the demo case with the malicious document to see indirect prompt injection get blocked." />}
        </div>
        <div className="card p-6">
          <h3 className="text-lg">Agent permission model</h3>
          <table className="mt-4 w-full text-left text-sm">
            <thead><tr className="text-xs uppercase tracking-wider text-ink-soft"><th className="pb-2">Agent</th><th className="pb-2">Permission</th><th className="pb-2">Risk</th></tr></thead>
            <tbody className="divide-y divide-sky-100 font-bold">
              {[
                ['Case Review', 'READ_CASE_DOCS', 'LOW'], ['Retrieval', 'READ_INDEX', 'LOW'], ['Verification', 'READ_EVIDENCE', 'LOW'],
                ['Matching', 'READ_LAWYER_DIR', 'LOW'], ['Drafting', 'WRITE_DRAFT', 'MEDIUM'], ['External comms', 'SEND_EXTERNAL', 'HIGH · approval'],
              ].map(([a, p, r]) => <tr key={a}><td className="py-2">{a}</td><td className="py-2 font-mono text-xs">{p}</td><td className="py-2"><Badge tone={r.startsWith('HIGH') ? 'red' : r === 'MEDIUM' ? 'amber' : 'green'}>{r}</Badge></td></tr>)}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}

// ── Observability ────────────────────────────────────────────────────────────
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const TASKS = [142, 168, 155, 201, 236, 118, 97]
const LATENCY = [6.8, 6.1, 5.9, 6.4, 5.2, 4.9, 4.7]

function BarChart({ data, labels, unit }: { data: number[]; labels: string[]; unit: string }) {
  const [hover, setHover] = useState<number | null>(null)
  const max = Math.max(...data)
  return (
    <div className="relative">
      <svg viewBox="0 0 350 180" className="w-full" role="img" aria-label={`Bar chart: ${labels.map((l, i) => `${l} ${data[i]} ${unit}`).join(', ')}`}>
        {[0, 0.5, 1].map((g) => <line key={g} x1="0" x2="350" y1={150 - g * 130} y2={150 - g * 130} stroke="#e0f2fe" strokeWidth="1" />)}
        {data.map((v, i) => {
          const h = (v / max) * 130, x = i * 50 + 9
          return (
            <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={x - 6} y="0" width="44" height="170" fill="transparent" />
              <motion.path initial={{ d: `M${x} 150 h32 v0 h-32z` }} animate={{ d: `M${x} 150 V${150 - h + 4} q0 -4 4 -4 h24 q4 0 4 4 V150z` }} transition={{ delay: i * 0.05, duration: 0.6 }} fill={hover === i ? '#0369a1' : '#0ea5e9'} />
              <text x={x + 16} y="168" textAnchor="middle" fontSize="11" fontWeight="700" fill="#3b4a6b">{labels[i]}</text>
            </g>
          )
        })}
      </svg>
      {hover !== null && <div className="pointer-events-none absolute -top-2 rounded-xl bg-ink px-2.5 py-1 text-xs font-bold text-white" style={{ left: `${((hover * 50 + 25) / 350) * 100}%`, transform: 'translateX(-50%)' }}>{labels[hover]} · {data[hover]} {unit}</div>}
    </div>
  )
}

function LineChart({ data, labels, unit }: { data: number[]; labels: string[]; unit: string }) {
  const [hover, setHover] = useState<number | null>(null)
  const min = Math.min(...data) - 0.5, max = Math.max(...data) + 0.5
  const pts = data.map((v, i) => [i * 55 + 10, 150 - ((v - min) / (max - min)) * 130] as const)
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0]} ${p[1]}`).join(' ')
  return (
    <div className="relative">
      <svg viewBox="0 0 350 180" className="w-full" role="img" aria-label={`Line chart: ${labels.map((l, i) => `${l} ${data[i]}${unit}`).join(', ')}`} onMouseLeave={() => setHover(null)}>
        {[0, 0.5, 1].map((g) => <line key={g} x1="0" x2="350" y1={150 - g * 130} y2={150 - g * 130} stroke="#e0f2fe" />)}
        <motion.path d={d} fill="none" stroke="#0ea5e9" strokeWidth="2" strokeLinecap="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1 }} />
        {hover !== null && <line x1={pts[hover][0]} x2={pts[hover][0]} y1="10" y2="150" stroke="#94a3b8" strokeDasharray="3 3" />}
        {pts.map((p, i) => (
          <g key={i} onMouseEnter={() => setHover(i)}>
            <rect x={p[0] - 27} y="0" width="55" height="170" fill="transparent" />
            <circle cx={p[0]} cy={p[1]} r={hover === i ? 6 : 4} fill="#0ea5e9" stroke="#fff" strokeWidth="2" />
            <text x={p[0]} y="168" textAnchor="middle" fontSize="11" fontWeight="700" fill="#3b4a6b">{labels[i]}</text>
          </g>
        ))}
      </svg>
      {hover !== null && <div className="pointer-events-none absolute -top-2 rounded-xl bg-ink px-2.5 py-1 text-xs font-bold text-white" style={{ left: `${(pts[hover][0] / 350) * 100}%`, transform: 'translateX(-50%)' }}>{labels[hover]} · {data[hover]}{unit}</div>}
    </div>
  )
}

export function Observability() {
  const cases = useDB((d) => d.cases)
  const log = useDB((d) => d.securityLog)
  const live = cases.filter((c) => c.analysis).length
  return (
    <>
      <PageHeader eyebrow="Admin" title="Observability" subtitle="Agent health, latency, verification pass-rate and cost." actions={<DemoTag />} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Agent success rate" value="98.6%" icon={<Activity className="size-4" />} tone="green" hint="7-day · simulated" />
        <Stat label="Avg. review latency" value="5.7s" icon={<Timer className="size-4" />} hint="p50 · simulated" />
        <Stat label="Reviews this session" value={live} icon={<CheckCircle2 className="size-4" />} hint="Live count" />
        <Stat label="Est. AI cost / review" value="₹4.20" icon={<IndianRupee className="size-4" />} tone="violet" hint="simulated" />
        <Stat label="Verification pass rate" value="91%" icon={<ShieldCheck className="size-4" />} tone="green" hint="simulated" />
        <Stat label="Failed tasks" value="3" icon={<XCircle className="size-4" />} tone="red" hint="7-day · simulated" />
        <Stat label="Security events" value={log.length} icon={<ShieldAlert className="size-4" />} tone="amber" hint="Live count" />
        <Stat label="Tool calls" value="12,408" icon={<Wrench className="size-4" />} hint="7-day · simulated" />
      </div>
      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <div className="card p-6"><h3 className="text-lg">Tasks completed per day</h3><p className="mb-4 text-sm font-semibold text-ink-soft">Last 7 days · simulated</p><BarChart data={TASKS} labels={DAYS} unit="tasks" /></div>
        <div className="card p-6"><h3 className="text-lg">Average review latency</h3><p className="mb-4 text-sm font-semibold text-ink-soft">Seconds · last 7 days · simulated</p><LineChart data={LATENCY} labels={DAYS} unit="s" /></div>
      </div>
    </>
  )
}
