import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, FileText, Inbox, SendHorizonal, ShieldCheck, XCircle } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Avatar, Badge, Button, cx, EmptyState, Field, inputCls, PageHeader } from '../components/ui'
import { useDB, useSession } from '../hooks/useStore'
import { errorMessage } from '../services/api/client'
import { respondToRequest, sendMessage } from '../services/connections'
import { inr } from '../utils/format'

export default function Messages() {
  const user = useSession()!
  const isLawyer = user.role === 'lawyer' || user.role === 'judge'
  const conversations = useDB((d) => d.conversations)
  const lawyers = useDB((d) => d.lawyers)
  const cases = useDB((d) => d.cases)
  const list = useMemo(() => conversations.filter((c) => (isLawyer ? c.lawyerId === user.lawyerId : c.clientId === user.id)), [conversations, isLawyer, user])
  const [activeId, setActiveId] = useState<string | null>(null)
  const active = list.find((c) => c.id === activeId) ?? list[0]
  const [text, setText] = useState('')
  const [quote, setQuote] = useState(0)
  const [err, setErr] = useState('')
  const act = (fn: () => Promise<unknown>) => { setErr(''); fn().catch((e) => setErr(errorMessage(e))) }
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [active?.messages.length])

  const counterpart = (c: typeof active) => (isLawyer ? { name: c!.clientName, initials: c!.clientName.split(' ').map((p) => p[0]).join('').slice(0, 2), hue: 180 } : (() => { const l = lawyers.find((x) => x.id === c!.lawyerId); return { name: l?.name ?? 'Advocate', initials: l?.initials ?? 'AD', hue: l?.photoHue ?? 200 } })())
  const brief = active ? cases.find((c) => c.id === active.caseId) : undefined
  const lawyer = active ? lawyers.find((l) => l.id === active.lawyerId) : undefined

  if (!list.length) return (
    <>
      <PageHeader eyebrow="Messages" title={isLawyer ? 'Client requests' : 'Lawyer connections'} />
      <EmptyState icon={<Inbox className="size-7" />} title="No conversations yet" body={isLawyer ? 'Client briefs will appear here once clients connect with you.' : 'Run a case review and connect with a matched advocate to start a conversation.'} action={!isLawyer ? <Button to="/app/client" size="sm">Go to my cases</Button> : undefined} />
    </>
  )

  return (
    <>
      <PageHeader eyebrow="Messages" title={isLawyer ? 'Client requests' : 'Lawyer connections'} subtitle="End-to-end encrypted in production. Every conversation is scoped to a single case." />
      <div className="grid gap-6 lg:grid-cols-[300px_1fr_320px]">
        <ul className="space-y-2">
          {list.map((c) => {
            const p = counterpart(c)
            return (
              <li key={c.id}>
                <button onClick={() => setActiveId(c.id)} className={cx('flex w-full items-center gap-3 rounded-2xl p-3 text-left transition', active?.id === c.id ? 'bg-white shadow-[var(--shadow-soft)] ring-2 ring-sky-400' : 'hover:bg-white')}>
                  <Avatar initials={p.initials} hue={p.hue} size={42} />
                  <span className="min-w-0 flex-1"><span className="block truncate font-extrabold">{p.name}</span><span className="block truncate text-xs font-bold text-ink-soft">{c.caseTitle}</span></span>
                  <Badge tone={c.status === 'accepted' ? 'green' : c.status === 'declined' ? 'red' : 'amber'}>{c.status}</Badge>
                </button>
              </li>
            )
          })}
        </ul>

        {active && (
          <div className="card flex min-h-[560px] flex-col overflow-hidden">
            <div className="flex items-center gap-3 border-b border-sky-100 px-5 py-4">
              <Avatar initials={counterpart(active).initials} hue={counterpart(active).hue} size={40} verified={!isLawyer} />
              <div className="min-w-0"><p className="truncate font-extrabold">{counterpart(active).name}</p><p className="truncate text-xs font-bold text-ink-soft">{active.caseTitle}</p></div>
            </div>
            <div className="flex-1 space-y-3 overflow-auto p-5 scrollbar-thin">
              <AnimatePresence initial={false}>
                {active.messages.map((m) => {
                  const mine = (m.from === 'lawyer' && isLawyer) || (m.from === 'client' && !isLawyer)
                  return m.from === 'system' ? (
                    <motion.p key={m.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mx-auto w-fit max-w-[90%] rounded-full bg-sky-50 px-4 py-1.5 text-center text-xs font-bold text-sky-700">{m.text}</motion.p>
                  ) : (
                    <motion.div key={m.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={cx('w-fit max-w-[80%] rounded-3xl px-4 py-2.5 text-sm font-semibold', mine ? 'ml-auto rounded-br-lg bg-sky-500 text-white' : 'rounded-bl-lg bg-sky-25 text-ink ring-1 ring-sky-100')}>
                      {m.text}<span className={cx('mt-1 block text-[10px] font-bold', mine ? 'text-sky-100' : 'text-ink-soft')}>{new Date(m.at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</span>
                    </motion.div>
                  )
                })}
              </AnimatePresence>
              <div ref={endRef} />
            </div>
            {err && <p className="border-t border-sky-100 bg-rose-50 px-4 py-2 text-sm font-bold text-rose-700" role="alert">{err}</p>}
            {isLawyer && active.status === 'requested' ? (
              <div className="space-y-3 border-t border-sky-100 bg-sky-25 p-4">
                <Field label="Proposed fee for this matter (₹)"><input type="number" min={0} className={inputCls} value={quote || lawyer?.consultationFee || 0} onChange={(e) => setQuote(Math.max(0, Number(e.target.value)))} /></Field>
                <div className="grid grid-cols-2 gap-2">
                  <Button onClick={() => act(() => respondToRequest(active.id, true, quote || lawyer?.consultationFee))} icon={<CheckCircle2 className="size-4" />}>Accept brief</Button>
                  <Button variant="secondary" onClick={() => act(() => respondToRequest(active.id, false))} icon={<XCircle className="size-4" />}>Decline</Button>
                </div>
              </div>
            ) : active.status === 'accepted' ? (
              <form onSubmit={(e) => { e.preventDefault(); const t = text; setText(''); act(() => sendMessage(active.id, t)) }} className="flex gap-2 border-t border-sky-100 p-4">
                <input value={text} onChange={(e) => setText(e.target.value)} maxLength={4000} placeholder="Write a message…" aria-label="Message" className="h-12 flex-1 rounded-2xl border border-sky-200 px-4 font-semibold outline-none focus:border-sky-500" />
                <button disabled={!text.trim()} className="grid size-12 place-items-center rounded-2xl bg-sky-500 text-white disabled:opacity-40" aria-label="Send"><SendHorizonal className="size-5" /></button>
              </form>
            ) : (
              <p className="border-t border-sky-100 p-4 text-center text-sm font-bold text-ink-soft">{active.status === 'requested' ? 'Waiting for the advocate to accept your brief…' : 'This request was declined.'}</p>
            )}
          </div>
        )}

        {/* Brief panel */}
        <aside className="space-y-4">
          <div className="card p-5">
            <p className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-ink-soft"><ShieldCheck className="size-4 text-sky-500" />Evidence brief</p>
            {brief?.analysis ? (
              <>
                <p className="mt-3 text-sm font-semibold text-ink-soft">{brief.analysis.summary}</p>
                <div className="mt-3 flex flex-wrap gap-1.5"><Badge>{brief.analysis.area}</Badge><Badge tone="slate">{brief.documents.length} docs</Badge><Badge tone="green">{brief.analysis.verification.coverage}% coverage</Badge></div>
                {brief.analysis.contradictions.map((c) => <p key={c.id} className="mt-3 flex items-start gap-2 rounded-xl bg-rose-50 p-2.5 text-xs font-bold text-rose-700"><AlertTriangle className="mt-0.5 size-3.5 shrink-0" />{c.topic}: {c.a.value} vs {c.b.value}</p>)}
                {brief.analysis.missing.length > 0 && <p className="mt-3 text-xs font-bold text-amber-700">Missing: {brief.analysis.missing.map((m) => m.title).join(', ')}</p>}
              </>
            ) : <p className="mt-3 text-sm font-semibold text-ink-soft">Not reviewed yet.</p>}
          </div>
          {active?.quote && <div className="card p-5"><p className="text-xs font-extrabold uppercase tracking-wider text-ink-soft">Agreed fee</p><p className="mt-1 text-2xl font-extrabold">{inr(active.quote)}</p><p className="text-xs font-semibold text-ink-soft">Proposed by the advocate. Payments are arranged directly with counsel.</p></div>}
          {brief && (isLawyer ? active?.status === 'accepted' : true) && (
            <div className="card p-5">
              <p className="text-xs font-extrabold uppercase tracking-wider text-ink-soft">Shared documents</p>
              <ul className="mt-2 space-y-1">{brief.documents.map((d) => <li key={d.id} className="flex items-center gap-2 truncate text-sm font-bold"><FileText className="size-4 shrink-0 text-sky-500" />{d.name}</li>)}</ul>
              <p className="mt-2 text-xs font-semibold text-ink-soft">Document names and the evidence brief only. Raw text stays with the client.</p>
            </div>
          )}
        </aside>
      </div>
    </>
  )
}
