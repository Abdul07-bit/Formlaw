import { motion } from 'framer-motion'
import { Briefcase, Clock, Gavel, Languages, MapPin, Sparkles, Star } from 'lucide-react'
import { ShieldAlert } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { errorMessage } from '../../services/api/client'
import { decideAction, prepareAction } from '../../services/connections'
import type { Approval, CompletedCase, Lawyer, LawyerMatch, RelatedCase } from '../../types'
import { inr } from '../../utils/format'
import { Avatar, Badge, Button, DemoTag, Field, inputCls, KycBadge, Modal } from '../ui'

export function LawyerCard({ l, match, onConnect, basePath = '/lawyers', i = 0 }: { l: Lawyer; match?: LawyerMatch; onConnect?: () => void; basePath?: string; i?: number }) {
  return (
    <motion.article initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: (i % 6) * 0.06 }} className="card card-hover group relative flex flex-col p-5">
      {match && (
        <div className="absolute -top-3 right-5 flex items-center gap-1 rounded-full bg-sky-500 px-3 py-1 text-xs font-extrabold text-white shadow-[var(--shadow-glow)]"><Sparkles className="size-3.5" />{match.score}% match</div>
      )}
      <div className="flex items-start gap-4">
        <Avatar initials={l.initials} hue={l.photoHue} size={56} verified={l.kyc === 'verified'} />
        <div className="min-w-0 flex-1">
          <Link to={`${basePath}/${l.id}`} className="block truncate text-lg font-extrabold hover:text-sky-600">{l.name}</Link>
          <p className="text-sm font-semibold text-ink-soft">{l.title} · {l.experienceYears} yrs</p>
          <p className="mt-1 flex items-center gap-1 text-xs font-bold text-ink-soft"><MapPin className="size-3.5" />{l.city}{l.courts[0] ? ` · ${l.courts[0]}` : ''}</p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-1.5">
        {l.practiceAreas.map((a) => <Badge key={a}>{a}</Badge>)}
        {l.role === 'judge' && <Badge tone="violet" icon={<Gavel className="size-3" />}>Arbitrator / Mediator</Badge>}
        {l.isDemo && <DemoTag />}
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2 rounded-2xl bg-sky-25 p-3 text-center">
        <div><div className="flex items-center justify-center gap-1 font-extrabold"><Star className="size-4 fill-amber-400 text-amber-400" />{l.rating ? l.rating.toFixed(1) : 'New'}</div><div className="text-[11px] font-bold text-ink-soft">{l.reviews} reviews</div></div>
        <div><div className="font-extrabold">{l.experienceYears}</div><div className="text-[11px] font-bold text-ink-soft">years</div></div>
        <div><div className="font-extrabold">{l.casesHandled}</div><div className="text-[11px] font-bold text-ink-soft">cases</div></div>
      </div>
      {match && (
        <ul className="mt-4 space-y-1">
          {match.reasons.slice(0, 3).map((r) => <li key={r} className="flex items-center gap-2 text-sm font-semibold text-ink-soft"><span className="size-1.5 rounded-full bg-sky-500" />{r}</li>)}
        </ul>
      )}
      <div className="mt-auto flex items-end justify-between gap-3 pt-5">
        <div>
          <p className="text-[11px] font-extrabold uppercase tracking-wider text-ink-soft">{match ? 'Indicative total' : 'Consultation'}</p>
          <p className="text-lg font-extrabold">{match ? `${inr(match.estimate[0])} – ${inr(match.estimate[1])}` : inr(l.consultationFee)}</p>
        </div>
        {onConnect ? <Button size="sm" onClick={onConnect}>Connect</Button> : <Button size="sm" variant="secondary" to={`${basePath}/${l.id}`}>View profile</Button>}
      </div>
    </motion.article>
  )
}

export function LawyerMeta({ l }: { l: Lawyer }) {
  return (
    <ul className="space-y-2 text-sm font-semibold text-ink-soft">
      <li className="flex items-center gap-2"><Briefcase className="size-4 text-sky-500" />{l.barCouncil || 'Bar Council pending'} · {l.enrolmentNo || '—'}</li>
      <li className="flex items-center gap-2"><Languages className="size-4 text-sky-500" />{l.languages.join(', ')}</li>
      <li className="flex items-center gap-2"><Clock className="size-4 text-sky-500" />Usually replies in ~{l.responseHours}h</li>
      <li className="flex items-center gap-2"><KycBadge status={l.kyc} /></li>
    </ul>
  )
}

export function RelatedCaseCard({ r, c, lawyer, plain }: { r: RelatedCase; c: CompletedCase; lawyer?: Lawyer; plain?: boolean }) {
  return (
    <div className="card card-hover p-5">
      <div className="flex items-center justify-between gap-2">
        <Badge tone="slate">{c.id}</Badge>
        {plain ? <span className="text-xs font-extrabold text-ink-soft">{c.area}</span> : <span className="text-sm font-extrabold text-sky-600">{Math.round(r.similarity * 100)}% similar</span>}
      </div>
      <p className="mt-2 font-extrabold">{c.title}</p>
      <p className="text-xs font-bold text-ink-soft">{c.court} · {c.year} · {c.durationMonths} mo</p>
      <p className="mt-2 text-sm text-ink-soft">{c.summary}</p>
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <Badge tone={/granted|Acquitted|Allowed|Decree|Settled/.test(c.outcome) ? 'green' : 'amber'}>{c.outcome}</Badge>
        {c.sections.map((s) => <Badge key={s} tone="sky">{s}</Badge>)}
      </div>
      {r.sharedTerms.length > 0 && <p className="mt-3 text-xs font-semibold text-ink-soft">Shared: {r.sharedTerms.join(' · ')}</p>}
      {lawyer && <p className="mt-2 text-xs font-extrabold text-ink">Handled by {lawyer.name}</p>}
    </div>
  )
}

/** Sharing a brief is external communication (HIGH risk): the server prepares it, the client approves it. */
export function useConnectFlow(caseId: string, lawyerId: string | undefined, onSent: () => void) {
  const [req, setReq] = useState<Approval | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const prepare = async (note: string) => {
    if (!lawyerId) return
    setBusy(true); setErr('')
    try { setReq(await prepareAction('connection.request', caseId, { lawyerId, note: note.trim() })) } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
  }
  const decide = async (approve: boolean) => {
    if (!req) return
    setBusy(true); setErr('')
    try { await decideAction(req.id, approve); setReq(null); if (approve) onSent() } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
  }
  return { req, busy, err, prepare, decide, reset: () => { setReq(null); setErr('') } }
}

export function ApprovalBox({ req, busy, onDecide }: { req: Approval; busy: boolean; onDecide: (approve: boolean) => void }) {
  return (
    <div className="rounded-2xl border-2 border-amber-200 bg-amber-50 p-4">
      <p className="flex items-center gap-2 font-extrabold text-amber-900"><ShieldAlert className="size-4" />Approval required · {req.riskLevel} risk</p>
      <p className="mt-2 text-sm font-bold text-ink">{req.summary}</p>
      <p className="mt-1 text-xs font-semibold text-ink-soft">Nothing is shared until you approve. This decision is recorded in the audit log.</p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Button loading={busy} onClick={() => onDecide(true)}>Approve & send</Button>
        <Button variant="secondary" disabled={busy} onClick={() => onDecide(false)}>Cancel</Button>
      </div>
    </div>
  )
}

export function ConnectModal({ open, onClose, lawyer, caseId, onSent }: { open: boolean; onClose: () => void; lawyer?: Lawyer; caseId: string; onSent: () => void }) {
  const [note, setNote] = useState('')
  const flow = useConnectFlow(caseId, lawyer?.id, () => { setNote(''); onSent() })
  if (!lawyer) return null
  return (
    <Modal open={open} onClose={() => { flow.reset(); onClose() }} title={`Connect with ${lawyer.name}`}>
      <div className="flex items-center gap-3 rounded-2xl bg-sky-25 p-3">
        <Avatar initials={lawyer.initials} hue={lawyer.photoHue} verified size={44} />
        <div className="text-sm"><p className="font-extrabold">{lawyer.title} · {lawyer.city}</p><p className="font-semibold text-ink-soft">Consultation {inr(lawyer.consultationFee)} · Hearing {inr(lawyer.hearingFee)}</p></div>
      </div>
      <p className="mt-4 text-sm font-semibold text-ink-soft">FormLaw will share an evidence-backed case brief (facts, contradictions, missing documents). Raw document text is never shared with counsel through FormLaw.</p>
      {flow.req ? <div className="mt-4"><ApprovalBox req={flow.req} busy={flow.busy} onDecide={flow.decide} /></div> : (
        <>
          <div className="mt-4"><Field label="Message (optional)"><textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={1000} className={inputCls} placeholder="e.g. We need a bail hearing this week." /></Field></div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button loading={flow.busy} onClick={() => flow.prepare(note)}>Review & send brief</Button>
          </div>
        </>
      )}
      {flow.err && <p className="mt-3 text-sm font-bold text-rose-600" role="alert">{flow.err}</p>}
    </Modal>
  )
}
