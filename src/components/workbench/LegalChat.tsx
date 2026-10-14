import { BookOpen, ChevronDown, ExternalLink, Scale } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { api, errorMessage } from '../../lib/api'
import { cx, label } from '../../lib/util'
import { Badge, ErrorNote, Spinner, StatusBadge } from '../ui'
import { Composer } from './Composer'

/**
 * Chat over FormLaw's verified legal corpus. Every answer shows the passages it comes from; unsupported sentences are
 * listed as removed, never shown as answer text. The public endpoint answers with verbatim passages only.
 */
export interface LegalEvidence {
  evidenceId: string; documentName: string; kind: string; court: string | null; date: string | null; citation: string | null
  neutralCitation: string | null; page: number | null; text: string; source: string; sourceUrl: string | null; license: string | null
}
export interface LegalAnswer {
  status: string; answer: string; claims: { text: string; evidenceIds: string[]; status: string }[]; evidence: LegalEvidence[]; note: string | null; engine: string
}
type Turn = { id: number; question: string; answer?: LegalAnswer; error?: string }

const ok = (s: string) => s === 'SUPPORTED' || s === 'PARTIALLY_SUPPORTED'

function Sources({ evidence }: { evidence: LegalEvidence[] }) {
  const [all, setAll] = useState(false)
  const shown = all ? evidence : evidence.slice(0, 2)
  return (
    <div className="mt-3 space-y-2">
      {shown.map((e) => (
        <div key={e.evidenceId} className="rounded-xl border border-line bg-surface-2/60 p-3">
          <p className="flex items-start gap-2 text-[13.5px] font-medium"><BookOpen className="mt-0.5 size-4 shrink-0 text-gold" /><span>{e.documentName}</span></p>
          <p className="mt-0.5 pl-6 text-[12px] text-muted">{[label(e.kind), e.court, e.date, e.neutralCitation ?? e.citation, e.page ? `p.${e.page}` : null].filter(Boolean).join(' · ')}</p>
          <blockquote className="mt-2 ml-6 border-l-2 border-gold pl-3 font-serif text-[13.5px] leading-relaxed text-fg/90">{e.text.length > 700 ? `${e.text.slice(0, 700)}…` : e.text}</blockquote>
          <p className="mt-1.5 pl-6 text-[11px] text-faint">
            {e.source}{e.license ? ` · ${e.license}` : ''}
            {e.sourceUrl && <> · <a href={e.sourceUrl} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-0.5 text-accent hover:underline">original<ExternalLink className="size-3" /></a></>}
          </p>
        </div>
      ))}
      {evidence.length > 2 && (
        <button type="button" onClick={() => setAll(!all)} className="inline-flex items-center gap-1 text-[12.5px] text-muted hover:text-fg">
          <ChevronDown className={cx('size-3.5 transition-transform', all && 'rotate-180')} />{all ? 'Fewer sources' : `All ${evidence.length} sources`}
        </button>
      )}
    </div>
  )
}

function Answer({ a }: { a: LegalAnswer }) {
  const removed = a.claims.filter((c) => !ok(c.status))
  const found = a.status === 'SUPPORTED'
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Badge tone={found ? 'ok' : a.status === 'NOT_FOUND' ? 'bad' : 'warn'}>{label(a.status.toLowerCase())}</Badge>
        {found && <span className="text-[12px] text-muted">{a.engine === 'llm' ? 'Model-phrased · every sentence verified against its source' : 'Verbatim passages from the verified corpus'}</span>}
      </div>
      <p className="whitespace-pre-line font-serif text-[15.5px] leading-relaxed">{a.answer}</p>
      {a.note && <p className="mt-2 text-[12.5px] text-muted">{a.note}</p>}
      {removed.length > 0 && (
        <div className="mt-3 rounded-lg border border-line p-3 text-[12.5px]">
          <p className="mb-1 font-medium">Removed by verification</p>
          {removed.map((c, i) => <p key={i} className="text-muted"><StatusBadge status={c.status} /> {c.text}</p>)}
        </div>
      )}
      {a.evidence.length > 0 && <Sources evidence={a.evidence} />}
    </div>
  )
}

export function LegalChat({ endpoint, suggestions = [], placeholder, initial, header, className, autoFocus }: {
  endpoint: '/public/ask' | '/research/answer'; suggestions?: string[]; placeholder?: string; initial?: string | null
  header?: ReactNode; className?: string; autoFocus?: boolean
}) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)
  const sent = useRef<string | null>(null)

  const ask = async (question: string) => {
    if (busy) return
    const previous = [...turns].reverse().find((t) => t.answer)?.question
    const id = Date.now()
    setTurns((t) => [...t, { id, question }])
    setBusy(true)
    try {
      const answer = await api.post<LegalAnswer>(endpoint, { question, ...(previous ? { previous } : {}) })
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, answer } : x)))
    } catch (e) {
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error: errorMessage(e) } : x)))
    } finally {
      setBusy(false)
    }
  }

  // A prompt handed over from another page is asked once (StrictMode mounts twice in development).
  useEffect(() => {
    if (initial && sent.current !== initial) { sent.current = initial; ask(initial) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial])
  useEffect(() => { if (turns.length) end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [turns])

  return (
    <div className={cx('flex flex-col', className)}>
      {header}
      {turns.length === 0 && suggestions.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button key={s} type="button" onClick={() => ask(s)} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-left text-[13px] text-muted hover:border-line-strong hover:text-fg">
              <Scale className="size-3.5 shrink-0 text-gold" />{s}
            </button>
          ))}
        </div>
      )}
      {turns.length > 0 && (
        <div className="mb-4 space-y-5">
          {turns.map((t) => (
            <div key={t.id} className="space-y-3">
              <div className="flex justify-end">
                <p className="max-w-[85%] rounded-2xl rounded-br-md bg-accent-soft px-4 py-2.5 text-[14.5px]">{t.question}</p>
              </div>
              <div className="rounded-2xl border border-line bg-surface p-4">
                {t.answer ? <Answer a={t.answer} /> : t.error ? <ErrorNote>{t.error}</ErrorNote> : (
                  <p className="flex items-center gap-2 text-[13px] text-muted"><Spinner />Searching the verified corpus and checking every passage…</p>
                )}
              </div>
            </div>
          ))}
          <div ref={end} />
        </div>
      )}
      <Composer onSend={ask} disabled={busy} autoFocus={autoFocus} placeholder={placeholder ?? 'Ask a legal question…'}
        footer={turns.length > 0 ? <button type="button" onClick={() => setTurns([])} disabled={busy} className="rounded-lg px-2 py-1 text-[12.5px] text-muted hover:bg-surface-2 hover:text-fg">Clear</button> : undefined} />
    </div>
  )
}
