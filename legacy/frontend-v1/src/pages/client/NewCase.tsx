import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, ArrowRight, Check, FileText, Trash2 } from 'lucide-react'
import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DocumentUpload, processingNote, toItems, type UploadItem } from '../../components/case/Upload'
import { Badge, Button, cx, Field, inputCls, PageHeader } from '../../components/ui'
import { useSession } from '../../hooks/useStore'
import { errorMessage } from '../../services/api/client'
import { createCase, uploadDocuments } from '../../services/cases'
import { formatBytes } from '../../services/ingest'
import { inr } from '../../utils/format'

const STEPS = ['Describe', 'Upload evidence', 'Review & run']

export default function NewCase() {
  const user = useSession()!
  const nav = useNavigate()
  const [step, setStep] = useState(0)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [city, setCity] = useState(user.city ?? '')
  const [budget, setBudget] = useState(50000)
  const [items, setItems] = useState<UploadItem[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const onFiles = useCallback((f: File[]) => setItems((p) => [...p, ...toItems(f)]), [])
  const patch = (key: string, v: Partial<UploadItem>) => setItems((p) => p.map((x) => (x.key === key ? { ...x, ...v } : x)))

  const canNext = step === 0 ? title.trim().length > 2 && description.trim().length > 10 : step === 1 ? items.length > 0 : true
  const submit = async () => {
    setBusy(true); setErr('')
    try {
      const c = await createCase({ title: title.trim().slice(0, 140), description: description.trim().slice(0, 4000), city: city.trim(), budget })
      let uploaded = 0
      for (const it of items) {
        patch(it.key, { status: 'uploading' })
        try {
          const [doc] = await uploadDocuments(c.id, [it.file])
          patch(it.key, { status: 'done', note: processingNote(doc.processingStatus) })
          uploaded++
        } catch (e) { patch(it.key, { status: 'error', error: errorMessage(e) }) }
      }
      if (!uploaded) { setErr('No document could be uploaded. Your case was saved — add documents from the case page.'); nav(`/app/cases/${c.id}`); return }
      nav(`/app/cases/${c.id}?run=1`)
    } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
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
          {step === 1 && <DocumentUpload onFiles={onFiles} items={items} onRemove={(k) => setItems((p) => p.filter((x) => x.key !== k))} />}
          {step === 2 && (
            <div className="card p-6 md:p-8">
              <h3 className="text-xl">{title}</h3>
              <p className="mt-2 whitespace-pre-wrap text-sm font-semibold text-ink-soft">{description}</p>
              <div className="mt-4 flex flex-wrap gap-2"><Badge>{city || 'Any city'}</Badge><Badge tone="green">Budget {inr(budget)}</Badge><Badge tone="slate">{items.length} documents</Badge></div>
              <ul className="mt-6 divide-y divide-sky-100">
                {items.map((d) => (
                  <li key={d.key} className="flex items-center gap-3 py-3">
                    <FileText className="size-5 text-sky-500" />
                    <span className="min-w-0 flex-1 truncate text-sm font-bold">{d.file.name}</span>
                    <span className="text-xs font-bold text-ink-soft">{formatBytes(d.file.size)}</span>
                    {d.status === 'error' ? <Badge tone="red">{d.error}</Badge> : d.note ? <Badge tone={d.note === 'Text extracted' ? 'green' : 'violet'}>{d.note}</Badge> : <Badge tone="slate">{d.status === 'uploading' ? 'uploading…' : 'ready'}</Badge>}
                    {d.status === 'ready' && <button onClick={() => setItems((p) => p.filter((x) => x.key !== d.key))} className="rounded-lg p-1.5 text-ink-soft hover:bg-rose-50 hover:text-rose-600" aria-label={`Remove ${d.file.name}`}><Trash2 className="size-4" /></button>}
                  </li>
                ))}
              </ul>
              {err && <p className="mt-4 text-sm font-bold text-rose-600" role="alert">{err}</p>}
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      <div className="mt-6 flex justify-between">
        <Button variant="ghost" onClick={() => (step ? setStep(step - 1) : nav(-1))} icon={<ArrowLeft className="size-4" />}>Back</Button>
        {step < 2 ? <Button disabled={!canNext} onClick={() => setStep(step + 1)}>Continue <ArrowRight className="size-4" /></Button>
          : <Button size="lg" loading={busy} onClick={submit}>Upload & run agentic review</Button>}
      </div>
    </>
  )
}
