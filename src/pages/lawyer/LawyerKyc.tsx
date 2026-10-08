import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, ArrowRight, BadgeCheck, Check, Clock, FileBadge2, IdCard, ScanFace, UserRound, XCircle } from 'lucide-react'
import { useRef, useState } from 'react'
import { KycArt } from '../../components/art'
import { FaceVerification, type FaceResult } from '../../components/kyc/FaceVerification'
import { Badge, Button, cx, Field, inputCls, KycBadge, PageHeader } from '../../components/ui'
import { useLawyer, useSession } from '../../hooks/useStore'
import { ALL_AREAS, submitKyc } from '../../services/api'
import { formatBytes, sanitizeFilename } from '../../services/ingest'
import type { KycSubmission, PracticeArea } from '../../types'

const STEPS = [
  { t: 'Professional profile', i: <UserRound className="size-5" /> },
  { t: 'Law degree certificate', i: <FileBadge2 className="size-5" /> },
  { t: 'Identity card', i: <IdCard className="size-5" /> },
  { t: 'Facial verification', i: <ScanFace className="size-5" /> },
]
const BAR_COUNCILS = ['Bar Council of Delhi', 'Bar Council of Maharashtra & Goa', 'Bar Council of Tamil Nadu & Puducherry', 'Bar Council of Karnataka', 'Bar Council of Telangana', 'Bar Council of Uttar Pradesh', 'Bar Council of West Bengal', 'Bar Council of Punjab & Haryana', 'Bar Council of Rajasthan', 'Bar Council of Kerala', 'Bar Council of Gujarat', 'Other State Bar Council']
const ID_ACCEPT = '.pdf,.png,.jpg,.jpeg'

function FilePick({ label, hint, value, onPick }: { label: string; hint: string; value?: File; onPick: (f: File) => void }) {
  const ref = useRef<HTMLInputElement>(null)
  const [err, setErr] = useState('')
  return (
    <div>
      <button type="button" onClick={() => ref.current?.click()} className={cx('flex w-full items-center gap-4 rounded-3xl border-2 border-dashed p-6 text-left transition', value ? 'border-emerald-300 bg-emerald-50' : 'border-sky-200 bg-white hover:border-sky-400')}>
        <span className={cx('grid size-14 shrink-0 place-items-center rounded-2xl', value ? 'bg-emerald-500 text-white' : 'bg-sky-50 text-sky-600')}>{value ? <Check className="size-6" strokeWidth={3} /> : <FileBadge2 className="size-6" />}</span>
        <span className="min-w-0"><span className="block font-extrabold">{value ? sanitizeFilename(value.name) : label}</span><span className="block text-sm font-semibold text-ink-soft">{value ? `${formatBytes(value.size)} · encrypted upload queued` : hint}</span></span>
      </button>
      <input ref={ref} type="file" accept={ID_ACCEPT} className="sr-only" aria-label={label} onChange={(e) => {
        const f = e.target.files?.[0]; e.target.value = ''
        if (!f) return
        if (!/\.(pdf|png|jpe?g)$/i.test(f.name) || !['application/pdf', 'image/png', 'image/jpeg'].includes(f.type)) return setErr('Upload a PDF, PNG or JPG file.')
        if (f.size > 8 * 1024 * 1024) return setErr('File must be under 8 MB.')
        setErr(''); onPick(f)
      }} />
      {err && <p className="mt-2 text-sm font-bold text-rose-600" role="alert">{err}</p>}
    </div>
  )
}

export default function LawyerKyc() {
  const user = useSession()!
  const lawyer = useLawyer(user.lawyerId)
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({
    barCouncil: lawyer?.barCouncil || BAR_COUNCILS[0], enrolmentNo: lawyer?.enrolmentNo ?? '', experienceYears: lawyer?.experienceYears || 3,
    city: lawyer?.city ?? '', state: lawyer?.state ?? '', courts: lawyer?.courts.join(', ') ?? '', languages: lawyer?.languages.join(', ') ?? 'English, Hindi',
    practiceAreas: (lawyer?.practiceAreas ?? []) as PracticeArea[], consultationFee: lawyer?.consultationFee ?? 1500, hearingFee: lawyer?.hearingFee ?? 10000, bio: lawyer?.bio ?? '',
  })
  const [degree, setDegree] = useState<File>()
  const [idCard, setIdCard] = useState<File>()
  const [idType, setIdType] = useState<KycSubmission['idType']>('Bar Council ID')
  const [face, setFace] = useState<FaceResult>()
  const [submitting, setSubmitting] = useState(false)
  const [restart, setRestart] = useState(false)

  if (!lawyer) return null
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm((f) => ({ ...f, [k]: v }))

  if ((lawyer.kyc === 'pending' || lawyer.kyc === 'verified' || lawyer.kyc === 'rejected') && !restart) {
    const s = lawyer.kycSubmission
    return (
      <>
        <PageHeader eyebrow="KYC verification" title={lawyer.kyc === 'verified' ? 'You’re verified ✓' : lawyer.kyc === 'pending' ? 'Verification in progress' : 'Verification needs attention'} />
        <div className="card grid gap-8 p-8 md:grid-cols-[1fr_280px] md:items-center">
          <div>
            <KycBadge status={lawyer.kyc} />
            <p className="mt-4 font-semibold text-ink-soft">
              {lawyer.kyc === 'verified' ? 'Your profile is live in the FormLaw marketplace and can receive client briefs.' : lawyer.kyc === 'pending' ? 'The FormLaw verification desk is reviewing your documents. Usually within 24 hours. (Demo: switch to the Admin persona to approve.)' : `Reason: ${s?.reviewNote || 'Documents could not be verified.'}`}
            </p>
            {s && (
              <ul className="mt-6 space-y-2 text-sm font-bold">
                <li className="flex items-center gap-2"><BadgeCheck className="size-4 text-emerald-500" />Degree certificate: {s.degreeCertificate}</li>
                <li className="flex items-center gap-2"><BadgeCheck className="size-4 text-emerald-500" />{s.idType}: {s.idCard}</li>
                <li className="flex items-center gap-2"><BadgeCheck className="size-4 text-emerald-500" />Liveness {s.livenessPassed ? 'passed' : 'failed'} · face match {Math.round(s.faceMatchScore * 100)}%</li>
                <li className="flex items-center gap-2 text-ink-soft"><Clock className="size-4" />Submitted {new Date(s.submittedAt).toLocaleString('en-IN')}</li>
              </ul>
            )}
            {lawyer.kyc === 'rejected' && <Button className="mt-6" onClick={() => { setRestart(true); setStep(0) }} icon={<XCircle className="size-4" />}>Resubmit</Button>}
          </div>
          <KycArt className="w-full" />
        </div>
      </>
    )
  }

  const canNext = [
    form.enrolmentNo.trim().length >= 4 && form.practiceAreas.length > 0 && form.city.trim().length > 1,
    !!degree, !!idCard, !!face?.livenessPassed,
  ][step]

  const submit = async () => {
    setSubmitting(true)
    await submitKyc(lawyer.id, {
      barCouncil: form.barCouncil, enrolmentNo: form.enrolmentNo.trim().toUpperCase().slice(0, 30), experienceYears: form.experienceYears,
      city: form.city.trim(), state: form.state.trim(), courts: form.courts.split(',').map((s) => s.trim()).filter(Boolean),
      languages: form.languages.split(',').map((s) => s.trim()).filter(Boolean), practiceAreas: form.practiceAreas,
      consultationFee: form.consultationFee, hearingFee: form.hearingFee, bio: form.bio.trim().slice(0, 600),
    }, {
      degreeCertificate: sanitizeFilename(degree!.name), idCard: sanitizeFilename(idCard!.name), idType,
      faceMatchScore: face!.faceMatchScore, livenessPassed: face!.livenessPassed,
    })
    setSubmitting(false)
    setRestart(false)
  }

  return (
    <>
      <PageHeader eyebrow="KYC verification" title="Verify your legal credentials" subtitle="Only verified advocates and judges can receive client briefs. Documents are encrypted and visible only to the verification desk." />
      <div className="grid gap-8 lg:grid-cols-[260px_1fr]">
        <ol className="flex gap-2 overflow-x-auto lg:flex-col">
          {STEPS.map((s, i) => (
            <li key={s.t} className={cx('flex shrink-0 items-center gap-3 rounded-2xl px-4 py-3 text-sm font-extrabold transition', i === step ? 'bg-sky-500 text-white shadow-[var(--shadow-glow)]' : i < step ? 'bg-emerald-50 text-emerald-800' : 'bg-white text-ink-soft ring-1 ring-sky-100')}>
              <span className="shrink-0">{i < step ? <Check className="size-5" strokeWidth={3} /> : s.i}</span><span className="whitespace-nowrap">{s.t}</span>
            </li>
          ))}
        </ol>
        <div>
          <AnimatePresence mode="wait">
            <motion.div key={step} initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }} transition={{ duration: 0.28 }} className="card p-6 md:p-8">
              {step === 0 && (
                <div className="grid gap-5">
                  <div className="grid gap-5 sm:grid-cols-2">
                    <Field label="State Bar Council"><select className={inputCls} value={form.barCouncil} onChange={(e) => set('barCouncil', e.target.value)}>{BAR_COUNCILS.map((b) => <option key={b}>{b}</option>)}</select></Field>
                    <Field label="Enrolment number" hint="e.g. D/1234/2015"><input className={inputCls} value={form.enrolmentNo} onChange={(e) => set('enrolmentNo', e.target.value)} maxLength={30} /></Field>
                    <Field label="City"><input className={inputCls} value={form.city} onChange={(e) => set('city', e.target.value)} /></Field>
                    <Field label="State"><input className={inputCls} value={form.state} onChange={(e) => set('state', e.target.value)} /></Field>
                    <Field label="Courts of practice" hint="Comma separated"><input className={inputCls} value={form.courts} onChange={(e) => set('courts', e.target.value)} placeholder="Delhi High Court, Saket District Court" /></Field>
                    <Field label="Languages" hint="Comma separated"><input className={inputCls} value={form.languages} onChange={(e) => set('languages', e.target.value)} /></Field>
                  </div>
                  <Field label="Practice areas">
                    <div className="flex flex-wrap gap-2">
                      {ALL_AREAS.map((a) => {
                        const on = form.practiceAreas.includes(a)
                        return <button type="button" key={a} onClick={() => set('practiceAreas', on ? form.practiceAreas.filter((x) => x !== a) : [...form.practiceAreas, a])} className={cx('rounded-full px-4 py-2 text-sm font-extrabold transition', on ? 'bg-sky-500 text-white' : 'bg-sky-50 text-sky-700 hover:bg-sky-100')} aria-pressed={on}>{a}</button>
                      })}
                    </div>
                  </Field>
                  <div className="grid gap-5 sm:grid-cols-3">
                    <Field label={`Experience: ${form.experienceYears} yrs`}><input type="range" min={0} max={45} value={form.experienceYears} onChange={(e) => set('experienceYears', Number(e.target.value))} className="mt-3 w-full accent-sky-500" /></Field>
                    <Field label="Consultation fee (₹)"><input type="number" min={0} max={500000} className={inputCls} value={form.consultationFee} onChange={(e) => set('consultationFee', Math.max(0, Number(e.target.value)))} /></Field>
                    <Field label="Fee per hearing (₹)"><input type="number" min={0} max={2000000} className={inputCls} value={form.hearingFee} onChange={(e) => set('hearingFee', Math.max(0, Number(e.target.value)))} /></Field>
                  </div>
                  <Field label="Short bio"><textarea className={inputCls} rows={3} maxLength={600} value={form.bio} onChange={(e) => set('bio', e.target.value)} placeholder="Your practice focus, notable expertise…" /></Field>
                </div>
              )}
              {step === 1 && (
                <div className="space-y-4">
                  <h3 className="text-xl">Upload your law degree</h3>
                  <p className="font-semibold text-ink-soft">LL.B (3-year / 5-year integrated) or LL.M certificate from a recognised university. Provisional certificates are accepted for advocates enrolled within 2 years.</p>
                  <FilePick label="Select degree certificate" hint="PDF, PNG or JPG · max 8 MB" value={degree} onPick={setDegree} />
                  <Badge tone="violet">Backend: OCR + university registry cross-check</Badge>
                </div>
              )}
              {step === 2 && (
                <div className="space-y-4">
                  <h3 className="text-xl">Upload an identity card</h3>
                  <div className="flex flex-wrap gap-2">
                    {(['Bar Council ID', 'Aadhaar', 'PAN', 'Passport'] as const).map((t) => <button key={t} type="button" onClick={() => setIdType(t)} className={cx('rounded-full px-4 py-2 text-sm font-extrabold', idType === t ? 'bg-ink text-white' : 'bg-slate-100 text-ink-soft')}>{t}</button>)}
                  </div>
                  <FilePick label={`Select ${idType}`} hint="Front side with clear photo · PDF, PNG or JPG" value={idCard} onPick={setIdCard} />
                  {idType === 'Aadhaar' && <p className="text-sm font-bold text-amber-700">Please mask the first 8 digits of your Aadhaar number before uploading.</p>}
                  <Badge tone="violet">Backend: name match with Bar Council roll · photo extracted for face match</Badge>
                </div>
              )}
              {step === 3 && (
                <div className="space-y-4">
                  <h3 className="text-xl">Live facial verification</h3>
                  <p className="font-semibold text-ink-soft">Look at the camera in good light. We check that you are a live person and match your face with your ID photo.</p>
                  <FaceVerification onComplete={setFace} />
                </div>
              )}
            </motion.div>
          </AnimatePresence>
          <div className="mt-6 flex justify-between">
            <Button variant="ghost" disabled={step === 0} onClick={() => setStep(step - 1)} icon={<ArrowLeft className="size-4" />}>Back</Button>
            {step < 3 ? <Button disabled={!canNext} onClick={() => setStep(step + 1)}>Continue <ArrowRight className="size-4" /></Button>
              : <Button size="lg" disabled={!canNext} loading={submitting} onClick={submit}>Submit for verification</Button>}
          </div>
        </div>
      </div>
    </>
  )
}
