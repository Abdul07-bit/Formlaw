import { motion } from 'framer-motion'
import { EyeOff, FileStack, ShieldCheck } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { RelatedCaseCard } from '../../components/case/Lawyers'
import { Badge, Button, EmptyState, Field, inputCls, PageHeader } from '../../components/ui'
import { useDB, useSession } from '../../hooks/useStore'
import { errorMessage } from '../../services/api/client'
import { submitLawyerCase } from '../../services/lawyers'
import { ALL_AREAS } from '../../utils/format'
import type { Outcome, PracticeArea } from '../../types'

const OUTCOMES: Outcome[] = ['Allowed', 'Dismissed', 'Settled', 'Acquitted', 'Convicted', 'Bail granted', 'Decree passed']

// Very small PII scrubber — backend runs a proper NER-based anonymiser before storage.
function scrub(s: string) {
  return s
    .replace(/\b\d{4}\s?\d{4}\s?\d{4}\b/g, '[AADHAAR]')
    .replace(/\b[A-Z]{5}\d{4}[A-Z]\b/g, '[PAN]')
    .replace(/\b[6-9]\d{9}\b/g, '[PHONE]')
    .replace(/[\w.+-]+@[\w-]+\.[\w.]+/g, '[EMAIL]')
}

export default function LawyerCases() {
  const user = useSession()!
  const completed = useDB((d) => d.completedCases)
  const mine = useMemo(() => completed.filter((c) => c.lawyerId === user.lawyerId), [completed, user.lawyerId])
  const [f, setF] = useState({ title: '', area: 'Criminal' as PracticeArea, court: '', year: 2025, outcome: 'Allowed' as Outcome, sections: '', summary: '', durationMonths: 6 })
  const [done, setDone] = useState(false)
  const [err, setErr] = useState('')

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const summary = scrub(f.summary.trim()).slice(0, 800)
    const keywords = [...new Set((summary.toLowerCase().match(/[a-z]{4,}/g) ?? []).filter((w) => !['that', 'with', 'this', 'from', 'were', 'after', 'which', 'court', 'case'].includes(w)))].slice(0, 12)
    setErr('')
    try {
      await submitLawyerCase({
        title: scrub(f.title.trim()).slice(0, 120), area: f.area, court: f.court.trim().slice(0, 120), year: f.year, outcome: f.outcome,
        sections: f.sections.split(',').map((s) => s.trim()).filter(Boolean).slice(0, 6), summary, keywords, durationMonths: f.durationMonths,
      })
    } catch (e) { setErr(errorMessage(e)); return }
    setF({ ...f, title: '', summary: '', sections: '' })
    setDone(true)
    setTimeout(() => setDone(false), 3000)
  }

  const valid = f.title.trim().length > 3 && f.summary.trim().length > 30 && f.court.trim().length > 2
  return (
    <>
      <PageHeader eyebrow="Case record" title="Publish completed cases" subtitle="Your anonymised outcomes become verified credentials on your profile and help FormLaw match similar clients to you." />
      <div className="grid gap-8 lg:grid-cols-[1fr_1fr]">
        <form onSubmit={submit} className="card grid gap-4 p-6">
          <div className="flex items-start gap-2 rounded-2xl bg-sky-50 p-3 text-sm font-bold text-sky-800"><EyeOff className="mt-0.5 size-4 shrink-0" />Use initials only. Aadhaar, PAN, phone numbers and emails are automatically redacted.</div>
          <Field label="Anonymised title"><input className={inputCls} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="State v. R.K. (anonymised)" /></Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Practice area"><select className={inputCls} value={f.area} onChange={(e) => setF({ ...f, area: e.target.value as PracticeArea })}>{ALL_AREAS.map((a) => <option key={a}>{a}</option>)}</select></Field>
            <Field label="Outcome"><select className={inputCls} value={f.outcome} onChange={(e) => setF({ ...f, outcome: e.target.value as Outcome })}>{OUTCOMES.map((a) => <option key={a}>{a}</option>)}</select></Field>
            <Field label="Court / forum"><input className={inputCls} value={f.court} onChange={(e) => setF({ ...f, court: e.target.value })} placeholder="Delhi High Court" /></Field>
            <Field label="Year"><input type="number" min={1980} max={2026} className={inputCls} value={f.year} onChange={(e) => setF({ ...f, year: Number(e.target.value) })} /></Field>
            <Field label="Provisions" hint="Comma separated, e.g. BNSS s.480, Art. 21"><input className={inputCls} value={f.sections} onChange={(e) => setF({ ...f, sections: e.target.value })} /></Field>
            <Field label={`Duration: ${f.durationMonths} months`}><input type="range" min={1} max={120} value={f.durationMonths} onChange={(e) => setF({ ...f, durationMonths: Number(e.target.value) })} className="mt-3 w-full accent-sky-500" /></Field>
          </div>
          <Field label="Summary of facts & outcome"><textarea className={inputCls} rows={5} value={f.summary} onChange={(e) => setF({ ...f, summary: e.target.value })} maxLength={800} placeholder="Key facts, the issue, what was argued and how it ended…" /></Field>
          <Button type="submit" disabled={!valid} size="lg" icon={<FileStack className="size-5" />}>Submit for verification</Button>
          {err && <p className="text-sm font-bold text-rose-600" role="alert">{err}</p>}
          {done && <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2 text-sm font-bold text-emerald-700"><ShieldCheck className="size-4" />Submitted. The verification desk will check it against court records.</motion.p>}
        </form>
        <div>
          <h2 className="mb-4 text-xl">Your published record</h2>
          {mine.length ? <div className="space-y-4">{mine.map((c) => (
            <div key={c.id} className="relative">
              {!c.verified && <Badge tone="amber" className="absolute right-4 top-4 z-10">Pending verification</Badge>}
              <RelatedCaseCard r={{ caseId: c.id, similarity: 1, sharedTerms: [] }} c={c} plain />
            </div>
          ))}</div> : <EmptyState icon={<FileStack className="size-7" />} title="No cases yet" body="Publish your first completed case to build your verified record." />}
        </div>
      </div>
    </>
  )
}
