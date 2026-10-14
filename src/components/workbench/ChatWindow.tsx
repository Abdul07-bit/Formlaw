import { useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, FileSearch, GitCompareArrows, ListChecks, Scale, ScrollText, Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, errorMessage } from '../../lib/api'
import { useInvalidateCase, useMessages } from '../../lib/queries'
import { parseRunResult, type Case, type RunResult } from '../../lib/types'
import { useRunStream } from '../../lib/useRunStream'
import { ErrorNote } from '../ui'
import { AgentPlan } from './AgentPlan'
import { AssistantMessage } from './AssistantMessage'
import { Composer } from './Composer'

const QUICK: Record<string, { icon: ReactNode; label: string; prompt: string }[]> = {
  default: [
    { icon: <ListChecks className="size-4" />, label: 'Review case', prompt: 'Review this case and identify the biggest weaknesses.' },
    { icon: <AlertTriangle className="size-4" />, label: 'Find contradictions', prompt: 'Find contradictions between the documents.' },
    { icon: <ScrollText className="size-4" />, label: 'Build timeline', prompt: 'Build a timeline of events.' },
    { icon: <FileSearch className="size-4" />, label: 'Missing documents', prompt: 'What documents or information are missing?' },
    { icon: <Scale className="size-4" />, label: 'Research authorities', prompt: 'Research authorities relevant to the main legal issue.' },
    { icon: <Search className="size-4" />, label: 'Brief for senior counsel', prompt: 'Summarize the case for senior counsel.' },
  ],
  contract: [
    { icon: <ListChecks className="size-4" />, label: 'Analyze contract', prompt: 'Review this contract for risks.' },
    { icon: <AlertTriangle className="size-4" />, label: 'Conflicting clauses', prompt: 'Find conflicting or inconsistent clauses.' },
    { icon: <FileSearch className="size-4" />, label: 'Missing provisions', prompt: 'What provisions or annexures are missing?' },
    { icon: <GitCompareArrows className="size-4" />, label: 'Obligations & deadlines', prompt: 'List each party’s obligations and deadlines.' },
  ],
}

interface Pending { runId: string; text: string }

export function ChatWindow({ kase, threadId, onThread, initialPrompt, onResult, onAttach }: {
  kase: Case; threadId?: string; onThread: (id: string) => void; initialPrompt?: string | null
  onResult?: (r: RunResult | null) => void; onAttach: () => void
}) {
  const { data: messages, refetch } = useMessages(threadId)
  const qc = useQueryClient()
  const invalidate = useInvalidateCase()
  const [pending, setPending] = useState<Pending | null>(null)
  const [error, setError] = useState('')
  const bottom = useRef<HTMLDivElement>(null)
  const sentInitial = useRef(false)
  const ownThread = useRef<string | null>(null)

  const prevThread = useRef(threadId)

  // Switching to another conversation drops any run that belongs to the previous one. Compared against the previous
  // value (not just "effect ran") so React StrictMode's double effect invocation cannot re-send the initial prompt.
  useEffect(() => {
    if (prevThread.current === threadId) return
    prevThread.current = threadId
    if (threadId !== ownThread.current) setPending(null)
    ownThread.current = threadId ?? null
    sentInitial.current = false
  }, [threadId])

  // Reattach to a run that is still executing (e.g. after a page refresh).
  useEffect(() => {
    if (pending || !messages?.length) return
    const last = messages[messages.length - 1]
    if (last.role === 'user' && last.runId && (last.runStatus === 'running' || last.runStatus === 'queued')) setPending({ runId: last.runId, text: last.content })
  }, [messages, pending])

  const live = useRunStream(pending?.runId ?? null, async () => {
    await refetch()
    invalidate(kase.id)
    setPending(null)
  })

  const send = async (text: string) => {
    setError('')
    try {
      const r = await api.post<{ runId: string; threadId: string }>(`/cases/${kase.id}/chat`, { message: text, ...(threadId ? { threadId } : {}) })
      setPending({ runId: r.runId, text })
      if (!threadId) {
        ownThread.current = r.threadId
        onThread(r.threadId)
        qc.invalidateQueries({ queryKey: ['threads', kase.id] })
      }
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  useEffect(() => {
    if (initialPrompt && !sentInitial.current && !threadId) {
      sentInitial.current = true
      send(initialPrompt)
    }
  }, [initialPrompt, threadId])

  const parsed = useMemo(() => (messages ?? []).map((m) => ({ ...m, parsed: m.role === 'assistant' ? parseRunResult(m.result) : null })), [messages])
  const lastResult = [...parsed].reverse().find((m) => m.parsed)?.parsed ?? null
  useEffect(() => { onResult?.(lastResult) }, [lastResult, onResult])
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [parsed.length, pending, live.steps.length])

  const showPendingUser = pending && !parsed.some((m) => m.role === 'user' && m.runId === pending.runId)
  const empty = !parsed.length && !pending
  const quick = QUICK[kase.matterType] ?? QUICK.default

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6">
          {empty && (
            <div className="pt-[8vh]">
              <p className="font-serif text-2xl">What should FormLaw work on in <span className="italic">{kase.title}</span>?</p>
              <p className="mt-1 text-sm text-muted">Answers come only from this case's {kase.documentCount} document(s) and FormLaw's verified legal corpus. Every statement is cited and verified.</p>
              {kase.documentCount === 0 && (
                <button type="button" onClick={onAttach} className="mt-4 w-full rounded-xl border border-dashed border-accent/50 bg-accent-soft px-4 py-4 text-left text-sm">
                  <span className="font-medium text-accent">Add the case documents first →</span>
                  <span className="block text-muted">FIR, remand report, contracts, statements… PDF, DOCX or text.</span>
                </button>
              )}
              <div className="mt-5 grid gap-2 sm:grid-cols-2">
                {quick.map((q) => (
                  <button key={q.label} type="button" onClick={() => send(q.prompt)} disabled={!kase.documentCount}
                    className="flex items-center gap-2.5 rounded-xl border border-line bg-surface px-3.5 py-3 text-left text-sm hover:border-line-strong disabled:opacity-50">
                    <span className="text-muted">{q.icon}</span><span className="font-medium">{q.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="space-y-8">
            {parsed.map((m) => m.role === 'user' ? (
              <div key={m.id} className="flex justify-end">
                <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-surface-3 px-4 py-2.5 text-[15px]">{m.content}</p>
              </div>
            ) : (
              <div key={m.id} className="flex gap-3">
                <Logo />
                <div className="min-w-0 flex-1">
                  {m.parsed ? <AssistantMessage result={m.parsed} caseId={kase.id} messageId={m.id} onAsk={send} />
                    : m.result == null ? <ErrorNote>{m.content || 'This request could not be completed. Please ask again.'}</ErrorNote>
                    : <ErrorNote>This answer could not be displayed safely (unexpected format).</ErrorNote>}
                </div>
              </div>
            ))}
            {pending && (
              <>
                {showPendingUser && (
                  <div className="flex justify-end"><p className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-surface-3 px-4 py-2.5 text-[15px]">{pending.text}</p></div>
                )}
                <div className="flex gap-3">
                  <Logo pulsing />
                  <div className="min-w-0 flex-1 space-y-2">
                    {live.rationale && <p className="text-[13px] text-muted">{live.rationale}</p>}
                    <AgentPlan steps={live.steps} notes={live.notes} live />
                  </div>
                </div>
              </>
            )}
          </div>
          <div ref={bottom} />
        </div>
      </div>
      <div className="mx-auto w-full max-w-3xl px-4 pb-4 sm:px-6">
        <ErrorNote>{error}</ErrorNote>
        <Composer onSend={send} onAttach={onAttach} disabled={!!pending} autoFocus />
        <p className="mt-1.5 text-center text-[11.5px] text-faint">FormLaw assists your judgement; it does not give legal advice. Check every citation before relying on it.</p>
      </div>
    </div>
  )
}

export function Logo({ pulsing }: { pulsing?: boolean }) {
  return (
    <div className={`mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-[#1f2a44] font-serif text-[15px] font-semibold text-[#f5f1e8] ${pulsing ? 'animate-pulse-dot' : ''}`} aria-hidden>F</div>
  )
}
