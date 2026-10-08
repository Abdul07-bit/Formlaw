import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, ArrowRight, Check, FileText, Trash2 } from 'lucide-react'
import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DocumentUpload } from '../../components/case/Upload'
import { Badge, Button, cx, Field, inputCls, PageHeader } from '../../components/ui'
import { useSession } from '../../hooks/useStore'
import { createCase, inr } from '../../services/api'
import { formatBytes } from '../../services/ingest'
import type { CaseDocument } from '../../types'

const STEPS = ['Describe', 'Upload evidence', 'Review & run']

export default function NewCase() {
  const user = useSession()!
  const nav = useNavigate()
  const [step, setStep] = useState(0)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [city, setCity] = useState(user.city ?? '')
  const [budget, setBudget] = useState(50000)
  const [docs, setDocs] = useState<CaseDocument[]>([])
  const onDocs = useCallback((d: CaseDocument[]) => setDocs((p) => [...p, ...d]), [])

  const canNext = step === 0 ? title.trim().length > 2 && description.trim().length > 10 : step === 1 ? docs.length > 0 || description.length > 40 : true
  const submit = () => {
    const c = createCase({ title: title.trim().slice(0, 140), description: description.trim().slice(0, 4000), city: city.trim(), budget, documents: docs })
    nav(`/app/cases/${c.id}?run=1`)
  }

  return (
    <>
      <PageHeader eyebrow="New case" title="Tell us what happened" subtitle="FormLaw agents will review your documents, ground every fact in evidence and match you with verified counsel." />
      <ol className="mb-8 flex items-center gap-2" aria-label="Progress">
        {STEPS.map((s, i) => (
          <li key={s} className="flex flex-1 items-center gap-2">
            <span className={cx('grid size-9 shrink-0 place-items-center rounded-full text-sm font-extrabold transition', i < step ? 'bg-emerald-500 text-white' : i === step ? 'bg-sky-500 text-white shadow-[var(--shadow-glow)]' : 'bg-white text-ink-soft ring-1 ring-sky-200')}>{i < step ? <Check className="size-4" strokeWidth={3} /> : i + 1}</span>
            <span className={cx('hidden text-sm font-extrabold sm:block', i === step ? 'text-ink' : 'text-ink-soft')}>{s}</span>
            {i < STEPS.length - 1 && <span className="h-1 flex-1 overflow-hidden rounded-full bg-sky-100"><motion.span className="block h-full bg-sky-500" animate={{ width: i < step ? '100%' : '0%' }} /></span>}
          </li>
        ))}
      </ol>

      <AnimatePresence mode="wait">
        <motion.div key={step} initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -30 }} transition={{ duration: 0.3 }}>
          {step === 0 && (
            <div className="card grid gap-5 p-6 md:p-8">
              <Field label="Case title"><input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={140} placeholder="e.g. Refund dispute with online seller" /></Field>
              <Field label="What happened?" hint="Plain language is fine — in English or Hinglish. Don’t include passwords or bank PINs.">
                <textarea className={inputCls} rows={6} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={4000} placeholder="Describe the events, dates, people involved and what outcome you want…" />
              </Field>
              <div className="grid gap-5 sm:grid-cols-2">
                <Field label="City (for lawyer matching)"><input className={inputCls} value={city} onChange={(e) => setCity(e.target.value)} placeholder="e.g. Bengaluru" /></Field>
                <Field label={`Budget: ${inr(budget)}`} hint="Used to rank lawyers by estimated total fee.">
                  <input type="range" min={5000} max={500000} step={5000} value={budget} onChange={(e) => setBudget(Number(e.target.value))} className="mt-3 w-full accent-sky-500" />
                </Field>
              </div>
            </div>
          )}
          {step === 1 && <DocumentUpload onDocuments={onDocs} />}
          {step === 2 && (
            <div className="card p-6 md:p-8">
              <h3 className="text-xl">{title}</h3>
              <p className="mt-2 whitespace-pre-wrap text-sm font-semibold text-ink-soft">{description}</p>
              <div className="mt-4 flex flex-wrap gap-2"><Badge>{city || 'Any city'}</Badge><Badge tone="green">Budget {inr(budget)}</Badge><Badge tone="slate">{docs.length} documents</Badge></div>
              <ul className="mt-6 divide-y divide-sky-100">
                {docs.map((d) => (
                  <li key={d.id} className="flex items-center gap-3 py-3">
                    <FileText className="size-5 text-sky-500" />
                    <span className="min-w-0 flex-1 truncate text-sm font-bold">{d.name}</span>
                    <span className="text-xs font-bold text-ink-soft">{formatBytes(d.size)}</span>
                    <Badge tone={d.extraction === 'live' ? 'green' : 'violet'}>{d.extraction === 'live' ? 'text ready' : 'server OCR'}</Badge>
                    <button onClick={() => setDocs((p) => p.filter((x) => x.id !== d.id))} className="rounded-lg p-1.5 text-ink-soft hover:bg-rose-50 hover:text-rose-600" aria-label={`Remove ${d.name}`}><Trash2 className="size-4" /></button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      <div className="mt-6 flex justify-between">
        <Button variant="ghost" onClick={() => (step ? setStep(step - 1) : nav(-1))} icon={<ArrowLeft className="size-4" />}>Back</Button>
        {step < 2 ? <Button disabled={!canNext} onClick={() => setStep(step + 1)}>Continue <ArrowRight className="size-4" /></Button>
          : <Button size="lg" onClick={submit}>Run agentic review</Button>}
      </div>
    </>
  )
}
