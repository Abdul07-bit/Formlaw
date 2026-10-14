import { useQueryClient } from '@tanstack/react-query'
import { BadgeCheck, Clock, ShieldQuestion, XCircle } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Badge, Button, Card, ErrorNote, Field, Input, Select, Textarea } from '../../components/ui'
import { api, errorMessage } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useApi, useMyProfile } from '../../lib/queries'
import { MATTER_TYPES, type Lawyer, type VerificationEvent } from '../../lib/types'
import { fmtDate, label, timeAgo } from '../../lib/util'
import { Page } from './Workspace'

const STATUS: Record<string, { tone: 'ok' | 'warn' | 'bad' | 'neutral'; icon: ReactNode; text: string }> = {
  NOT_STARTED: { tone: 'neutral', icon: <ShieldQuestion className="size-5" />, text: 'Not verified. Complete your profile and submit documents to appear in the directory.' },
  PENDING: { tone: 'warn', icon: <Clock className="size-5" />, text: 'Submitted — waiting for checks.' },
  UNDER_REVIEW: { tone: 'warn', icon: <Clock className="size-5" />, text: 'Under review by FormLaw. An administrator decides after the provider checks.' },
  VERIFIED: { tone: 'ok', icon: <BadgeCheck className="size-5" />, text: 'Verified. Only admin-verified practice areas are shown to clients.' },
  REJECTED: { tone: 'bad', icon: <XCircle className="size-5" />, text: 'Verification was not approved. Update your details and resubmit.' },
  EXPIRED: { tone: 'bad', icon: <Clock className="size-5" />, text: 'Verification expired. Resubmit to stay listed.' },
  SUSPENDED: { tone: 'bad', icon: <XCircle className="size-5" />, text: 'Verification suspended by FormLaw. Your profile is hidden. Contact FormLaw to request a review.' },
}

export default function Profile() {
  const { data: p, refetch } = useMyProfile()
  const { reload } = useAuth()
  const { data: ver, refetch: refetchVer } = useApi<{ status: string; expiresAt: string | null; history: VerificationEvent[]; checks: { type: string; status: string; provider: string; note: string | null; submittedAt: string; demo: boolean }[] }>(['verification'], '/lawyers/verification')
  const qc = useQueryClient()
  const [f, setF] = useState<Partial<Lawyer> & { languagesText?: string; jurisdictionsText?: string }>({})
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  useEffect(() => { if (p) setF({ ...p, languagesText: p.languages.join(', '), jurisdictionsText: p.jurisdictions.join(', ') }) }, [p])
  if (!p) return null
  const s = STATUS[p.verificationStatus] ?? STATUS.NOT_STARTED

  const save = async (extra: Record<string, unknown> = {}) => {
    setErr(''); setMsg('')
    try {
      await api.put('/lawyers/profile', {
        name: f.name, headline: f.headline, city: f.city, state: f.state, bio: f.bio, barCouncil: f.barCouncil, enrolmentNumber: f.enrolmentNumber,
        experienceYears: Number(f.experienceYears) || 0, practiceAreas: f.practiceAreas, acceptingClients: f.acceptingClients,
        languages: (f.languagesText ?? '').split(',').map((x) => x.trim()).filter(Boolean),
        jurisdictions: (f.jurisdictionsText ?? '').split(',').map((x) => x.trim()).filter(Boolean), ...extra,
      })
      setMsg('Saved'); refetch(); reload(); qc.invalidateQueries({ queryKey: ['verification'] })
    } catch (e) { setErr(errorMessage(e)) }
  }

  return (
    <Page title="Profile & verification" intro="Clients see only verified information. FormLaw never shows ratings, win rates or outcome predictions.">
      <Card className="mb-6 flex gap-3 p-4">
        <span className={s.tone === 'ok' ? 'text-ok' : s.tone === 'bad' ? 'text-bad' : s.tone === 'warn' ? 'text-warn' : 'text-muted'}>{s.icon}</span>
        <div className="flex-1">
          <p className="font-medium">Verification: {label(p.verificationStatus.toLowerCase())}{p.verificationExpiresAt ? ` · valid until ${fmtDate(p.verificationExpiresAt)}` : ''}</p>
          <p className="text-[13px] text-muted">{s.text}</p>
          {p.verificationStatus === 'VERIFIED' && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="text-[13px]">Verified areas:</span>{p.verifiedAreas.map((a) => <Badge key={a} tone="ok">{a}</Badge>)}
              <Button size="sm" variant={p.profileStatus === 'published' ? 'secondary' : 'primary'} onClick={() => save({ publish: p.profileStatus !== 'published' })}>
                {p.profileStatus === 'published' ? 'Hide from directory' : 'Publish to directory'}
              </Button>
            </div>
          )}
        </div>
      </Card>

      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); save() }}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Name"><Input value={f.name ?? ''} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
          <Field label="Headline"><Input value={f.headline ?? ''} onChange={(e) => setF({ ...f, headline: e.target.value })} /></Field>
          <Field label="Bar Council"><Input value={f.barCouncil ?? ''} onChange={(e) => setF({ ...f, barCouncil: e.target.value })} /></Field>
          <Field label="Enrolment number" hint="Changing credentials re-opens verification"><Input value={f.enrolmentNumber ?? ''} onChange={(e) => setF({ ...f, enrolmentNumber: e.target.value })} /></Field>
          <Field label="City"><Input value={f.city ?? ''} onChange={(e) => setF({ ...f, city: e.target.value })} /></Field>
          <Field label="State"><Input value={f.state ?? ''} onChange={(e) => setF({ ...f, state: e.target.value })} /></Field>
          <Field label="Courts / jurisdictions" hint="Comma-separated"><Input value={f.jurisdictionsText ?? ''} onChange={(e) => setF({ ...f, jurisdictionsText: e.target.value })} /></Field>
          <Field label="Languages" hint="Comma-separated"><Input value={f.languagesText ?? ''} onChange={(e) => setF({ ...f, languagesText: e.target.value })} /></Field>
          <Field label="Years of practice" hint="Shown to clients as self-declared"><Input type="number" min={0} value={f.experienceYears ?? 0} onChange={(e) => setF({ ...f, experienceYears: Number(e.target.value) })} /></Field>
          <Field label="Accepting new clients">
            <Select value={f.acceptingClients ? 'yes' : 'no'} onChange={(e) => setF({ ...f, acceptingClients: e.target.value === 'yes' })}><option value="yes">Yes</option><option value="no">No</option></Select>
          </Field>
        </div>
        <Field label="Practice areas" hint="New areas stay unverified until an administrator verifies them">
          <div className="flex flex-wrap gap-1.5">
            {MATTER_TYPES.map((m) => {
              const on = f.practiceAreas?.includes(m)
              return <button key={m} type="button" onClick={() => setF({ ...f, practiceAreas: on ? f.practiceAreas!.filter((x) => x !== m) : [...(f.practiceAreas ?? []), m] })}
                className={`rounded-full border px-2.5 py-1 text-[12.5px] ${on ? 'border-accent bg-accent-soft text-accent' : 'border-line text-muted'}`}>{label(m)}{p.verifiedAreas.includes(m) ? ' ✓' : ''}</button>
            })}
          </div>
        </Field>
        <Field label="Bio"><Textarea rows={3} value={f.bio ?? ''} onChange={(e) => setF({ ...f, bio: e.target.value })} /></Field>
        <ErrorNote>{err}</ErrorNote>
        <div className="flex items-center gap-2"><Button type="submit" variant="primary">Save profile</Button>{msg && <span className="text-[13px] text-ok">{msg}</span>}</div>
      </form>

      <KycForm status={p.verificationStatus} onDone={() => { refetch(); refetchVer(); reload() }} />
      {!!ver?.history.length && (
        <div className="mt-6">
          <p className="mb-2 text-[12px] font-semibold uppercase tracking-wider text-muted">Verification history</p>
          <ol className="space-y-1 text-[13px]">
            {ver.history.map((h, i) => (
              <li key={i} className="flex flex-wrap items-baseline gap-x-2 border-l-2 border-line pl-3">
                <span className="font-medium">{label(h.from.toLowerCase())} → {label(h.to.toLowerCase())}</span>
                <span className="text-faint">{h.by}{h.at ? ` · ${timeAgo(h.at)}` : ''}</span>
                {h.reason && <span className="w-full text-muted">{h.reason}</span>}
              </li>
            ))}
          </ol>
        </div>
      )}
      {!!ver?.checks.length && (
        <div className="mt-6">
          <p className="mb-2 text-[12px] font-semibold uppercase tracking-wider text-muted">Verification checks</p>
          <ul className="space-y-1">
            {ver.checks.map((c, i) => (
              <li key={i} className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-[13px]">
                <span className="flex-1">{label(c.type)}</span>
                {c.demo && <Badge tone="warn" title="No real identity, qualification or Bar roll check was performed">demo provider</Badge>}
                <Badge tone={c.status === 'passed' ? 'ok' : c.status === 'failed' ? 'bad' : 'neutral'}>{label(c.status)}</Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Page>
  )
}

const BLOCKED: Record<string, string> = { PENDING: 'Verification in progress', UNDER_REVIEW: 'Verification in progress', SUSPENDED: 'Verification suspended' }

function KycForm({ status, onDone }: { status: string; onDone: () => void }) {
  const [idType, setIdType] = useState('Bar Council ID')
  const [files, setFiles] = useState<{ governmentId?: File; qualification?: File }>({})
  const [court, setCourt] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const blocked = BLOCKED[status]
  const submit = async () => {
    if (!files.governmentId || !files.qualification) return setErr('Attach both files.')
    const fd = new FormData()
    fd.append('idType', idType); fd.append('governmentId', files.governmentId); fd.append('qualification', files.qualification)
    if (court.trim()) fd.append('judicialCourt', court.trim())
    setBusy(true); setErr('')
    try { await api.post('/lawyers/verification', fd); onDone() } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
  }
  const file = (k: keyof typeof files, accept: string) => (
    <input type="file" accept={accept} onChange={(e) => setFiles({ ...files, [k]: e.target.files?.[0] })} className="block w-full text-[13px] text-muted file:mr-2 file:rounded-md file:border file:border-line file:bg-surface file:px-2 file:py-1 file:text-fg" />
  )
  return (
    <Card className="mt-8 space-y-3 p-4">
      <p className="font-medium">Submit verification documents</p>
      <p className="text-[13px] text-muted">Documents are encrypted at rest and visible only to verification reviewers. FormLaw does not collect selfies or any biometric data. The Bar Council and enrolment number on your profile are part of the review, and an administrator makes the final decision.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="ID type"><Select value={idType} onChange={(e) => setIdType(e.target.value)}>{['Bar Council ID', 'Aadhaar', 'PAN', 'Passport'].map((t) => <option key={t}>{t}</option>)}</Select></Field>
        <Field label="Government / Bar ID (PDF or image)">{file('governmentId', '.pdf,.png,.jpg,.jpeg')}</Field>
        <Field label="Law degree certificate">{file('qualification', '.pdf,.png,.jpg,.jpeg')}</Field>
      </div>
      <Field label="Judicial office (only if you hold or held one)" hint="Judicial status requires its own official check and an explicit administrator decision. Uploading an ID never confers it.">
        <Input value={court} onChange={(e) => setCourt(e.target.value)} placeholder="Court" />
      </Field>
      <ErrorNote>{err}</ErrorNote>
      <Button variant="primary" loading={busy} disabled={!!blocked} onClick={submit}>{blocked ?? 'Submit for verification'}</Button>
    </Card>
  )
}
