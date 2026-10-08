import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, Check, Loader2, Scale, SendHorizonal, ShieldQuestion } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Analysis, CaseDocument } from '../../types'
import { answerQuestion, type GroundedAnswer } from '../../services/agents'
import { suggestedQuestions } from '../../data/demoCase'
import { Badge, cx } from '../ui'
import { EvidenceChip } from './Evidence'

interface Turn { q: string; a?: GroundedAnswer; steps: string[]; step: number }

export function GroundedChat({ analysis, docs, onOpenEvidence }: { analysis: Analysis; docs: CaseDocument[]; onOpenEvidence: (id: string) => void }) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [q, setQ] = useState('')
  const busy = turns.some((t) => !t.a)
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [turns])

  const ask = (question: string) => {
    const text = question.trim().slice(0, 500)
    if (!text || busy) return
    setQ('')
    const answer = answerQuestion(text, analysis, docs)
    const idx = turns.length
    setTurns((t) => [...t, { q: text, steps: answer.steps, step: 0 }])
    // Reveal each agent step, then the grounded answer.
    answer.steps.forEach((_, s) => setTimeout(() => setTurns((t) => t.map((x, i) => (i === idx ? { ...x, step: s + 1 } : x))), 450 * (s + 1)))
    setTimeout(() => setTurns((t) => t.map((x, i) => (i === idx ? { ...x, a: answer } : x))), 450 * (answer.steps.length + 1))
  }

  return (
    <div className="card flex flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-sky-100 px-5 py-4">
        <div className="flex items-center gap-2"><Scale className="size-5 text-sky-500" /><h3 className="text-lg">Grounded Legal Assistant</h3></div>
        <Badge tone="green">Answers only from evidence</Badge>
      </div>
      <div className="max-h-[520px] min-h-[220px] flex-1 space-y-5 overflow-auto p-5 scrollbar-thin">
        {!turns.length && <p className="text-center text-sm font-semibold text-ink-soft">Ask anything about this case. Every answer links to the exact page it came from.</p>}
        {turns.map((t, i) => {
          const pending = !t.a
          const steps = t.steps
          return (
            <div key={i} className="space-y-3">
              <div className="ml-auto w-fit max-w-[85%] rounded-3xl rounded-br-lg bg-ink px-4 py-2.5 text-sm font-bold text-white">{t.q}</div>
              <AnimatePresence mode="wait">
                {pending ? (
                  <motion.ul key="steps" exit={{ opacity: 0 }} className="space-y-1.5 rounded-2xl bg-sky-25 p-4">
                    {steps.slice(0, t.step + 1).map((s, k) => (
                      <motion.li key={s} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} className={cx('flex items-center gap-2 text-sm font-bold', /Conflict/.test(s) ? 'text-amber-700' : 'text-ink-soft')}>
                        {k < t.step ? (/Conflict/.test(s) ? <AlertTriangle className="size-4 text-amber-500" /> : <Check className="size-4 text-emerald-500" />) : <Loader2 className="size-4 animate-spin text-sky-500" />}{s}
                      </motion.li>
                    ))}
                  </motion.ul>
                ) : (
                  <motion.div key="answer" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={cx('rounded-3xl rounded-tl-lg border-2 p-5', t.a!.status === 'conflicted' ? 'border-amber-200 bg-amber-50/60' : t.a!.status === 'insufficient' ? 'border-slate-200 bg-slate-50' : 'border-sky-100 bg-white')}>
                    <div className="mb-2 flex items-center gap-2">
                      {t.a!.status === 'conflicted' ? <Badge tone="amber">Conflicting evidence</Badge> : t.a!.status === 'insufficient' ? <Badge tone="slate" icon={<ShieldQuestion className="size-3" />}>Insufficient evidence</Badge> : <Badge tone="green">Evidence-backed</Badge>}
                    </div>
                    <p className="text-[15px] font-bold leading-relaxed">{t.a!.text}</p>
                    {t.a!.evidenceIds.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {t.a!.evidenceIds.map((id) => { const ev = analysis.evidence.find((e) => e.id === id); return ev ? <EvidenceChip key={id} ev={ev} onOpen={onOpenEvidence} tone={t.a!.status === 'conflicted' ? 'red' : 'sky'} /> : null })}
                      </div>
                    )}
                    {t.a!.note && <p className="mt-3 flex items-start gap-1.5 text-sm font-semibold text-ink-soft"><AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-500" />{t.a!.note}</p>}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )
        })}
        <div ref={endRef} />
      </div>
      <div className="border-t border-sky-100 p-4">
        <div className="mb-3 flex gap-2 overflow-x-auto pb-1 scrollbar-thin">
          {suggestedQuestions.map((s) => <button key={s} disabled={busy} onClick={() => ask(s)} className="shrink-0 rounded-full border border-sky-200 bg-white px-3 py-1.5 text-xs font-extrabold text-sky-700 transition hover:bg-sky-50 disabled:opacity-50">{s}</button>)}
        </div>
        <form onSubmit={(e) => { e.preventDefault(); ask(q) }} className="flex gap-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask anything about this case…" aria-label="Ask a question about this case" maxLength={500} className="h-12 flex-1 rounded-2xl border border-sky-200 px-4 text-[15px] font-semibold outline-none focus:border-sky-500 focus:ring-4 focus:ring-sky-100" />
          <button disabled={busy || !q.trim()} className="grid size-12 place-items-center rounded-2xl bg-sky-500 text-white transition hover:bg-sky-600 disabled:opacity-40" aria-label="Send question"><SendHorizonal className="size-5" /></button>
        </form>
      </div>
    </div>
  )
}
