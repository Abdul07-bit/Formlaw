import { AlertTriangle, BookOpen, FileSearch, FolderOpen, ListChecks, Scale, ScrollText } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Composer } from '../../components/workbench/Composer'
import { NewCaseDialog } from '../../components/workbench/NewCaseDialog'
import { Badge, Button, Select, Skeleton } from '../../components/ui'
import { useAuth } from '../../lib/auth'
import { useCases } from '../../lib/queries'
import { cx, greeting, label, timeAgo } from '../../lib/util'

const QUICK = [
  { icon: <ListChecks className="size-4" />, label: 'Review case', prompt: 'Review this case and identify the biggest weaknesses.' },
  { icon: <FileSearch className="size-4" />, label: 'Analyze contract', prompt: 'Review this contract for risks.' },
  { icon: <Scale className="size-4" />, label: 'Authorities for this case', prompt: 'Research authorities relevant to the main legal issue.' },
  { icon: <AlertTriangle className="size-4" />, label: 'Find contradictions', prompt: 'Find contradictions between the documents.' },
  { icon: <ScrollText className="size-4" />, label: 'Build timeline', prompt: 'Build a timeline of events.' },
]

export default function Home() {
  const { user } = useAuth()
  const { data: cases, isLoading } = useCases()
  const [caseId, setCaseId] = useState('')
  const [newCase, setNewCase] = useState(false)
  const [mode, setMode] = useState<'case' | 'law'>('case')
  const nav = useNavigate()
  const selected = caseId || cases?.[0]?.id || ''
  const go = (prompt: string) => selected ? nav(`/cases/${selected}`, { state: { prompt } }) : setNewCase(true)
  const research = (prompt: string) => nav('/research', { state: { prompt } })
  const first = user?.name.replace(/^Adv\.?\s*/, '').split(' ')[0]

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-2xl px-4 pt-[14vh] pb-16 sm:px-6">
        <h1 className="font-serif text-3xl tracking-tight">{greeting()}{first ? `, ${first}` : ''}.</h1>
        <p className="mt-1 text-lg text-muted">What are you working on?</p>
        <div className="mt-6 mb-2 inline-flex rounded-lg border border-line bg-surface p-0.5 text-[13px]" role="tablist" aria-label="Ask about">
          {([['case', 'A case', <FolderOpen key="c" className="size-3.5" />], ['law', 'The law', <BookOpen key="l" className="size-3.5" />]] as const).map(([m, t, icon]) => (
            <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
              className={cx('inline-flex items-center gap-1.5 rounded-md px-3 py-1', mode === m ? 'bg-surface-3 font-medium text-fg' : 'text-muted hover:text-fg')}>{icon}{t}</button>
          ))}
        </div>
        <div>
          {mode === 'law' ? (
            <Composer key="law" onSend={research} placeholder="Ask the verified legal corpus — e.g. when does delay in trial justify bail?" autoFocus
              footer={<span className="text-[12px] text-faint">Supreme Court judgments · cited passages only</span>} />
          ) : <Composer key="case" onSend={go} placeholder="Ask FormLaw anything about a case…" autoFocus footer={
            cases?.length ? (
              <Select aria-label="Case" value={selected} onChange={(e) => setCaseId(e.target.value)} className="h-8 w-56 text-[13px]">
                {cases.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
              </Select>
            ) : <Button size="sm" onClick={() => setNewCase(true)}>Create a case first</Button>
          } />}
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {mode === 'case' && QUICK.map((q) => (
            <button key={q.label} type="button" onClick={() => go(q.prompt)} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-[13px] text-muted hover:border-line-strong hover:text-fg">
              {q.icon}{q.label}
            </button>
          ))}
          {mode === 'law' && ['Can prolonged custody and delay in trial justify bail?', 'When is a dying declaration reliable?'].map((q) => (
            <button key={q} type="button" onClick={() => research(q)} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-[13px] text-muted hover:border-line-strong hover:text-fg">
              <Scale className="size-4" />{q}
            </button>
          ))}
        </div>

        <div className="mt-12">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-[12px] font-semibold uppercase tracking-wider text-muted">Recent cases</p>
            <Button size="sm" variant="ghost" onClick={() => setNewCase(true)}>+ New case</Button>
          </div>
          {isLoading ? <Skeleton className="h-32" /> : (
            <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
              {(cases ?? []).slice(0, 6).map((c) => (
                <li key={c.id}>
                  <button type="button" onClick={() => nav(`/cases/${c.id}`)} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface-2">
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{c.title}</p>
                      <p className="text-[12px] text-muted">{c.reference} · {label(c.matterType)} · {c.documentCount} document(s) · {timeAgo(c.updatedAt)}</p>
                    </div>
                    {c.flaggedDocuments > 0 && <Badge tone="bad">security flag</Badge>}
                    {c.isDemo && <Badge>demo</Badge>}
                  </button>
                </li>
              ))}
              {!cases?.length && <li className="px-4 py-6 text-center text-sm text-muted">No cases yet. Create one to start.</li>}
            </ul>
          )}
        </div>
      </div>
      <NewCaseDialog open={newCase} onClose={() => setNewCase(false)} />
    </div>
  )
}
