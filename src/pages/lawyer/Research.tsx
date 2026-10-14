import { BookOpen } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { Badge, EmptyState } from '../../components/ui'
import { LegalChat } from '../../components/workbench/LegalChat'
import { useApi } from '../../lib/queries'
import { cx } from '../../lib/util'

interface Corpus { totals: Record<string, string | number>; sources: { source: string; name: string; status: string; documents: number; coverage: string }[] }

const SUGGESTIONS = [
  'Can prolonged custody and delay in trial justify bail?',
  'When is a dying declaration reliable without corroboration?',
  'What are the twin conditions for bail under the PMLA?',
]

export default function Research() {
  const { data: corpus } = useApi<Corpus>(['corpus'], '/research/corpus')
  const initial = (useLocation().state as { prompt?: string } | null)?.prompt ?? null
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <h1 className="font-serif text-2xl">Legal research</h1>
        <p className="mt-1 text-sm text-muted">Chat with FormLaw's verified legal corpus. Answers come only from passages FormLaw can show you; unknown citations are refused and every sentence is checked against the passage it cites. FormLaw never writes an authority from memory.</p>
        <LegalChat endpoint="/research/answer" className="mt-5" suggestions={SUGGESTIONS} initial={initial} autoFocus
          placeholder="e.g. Can prolonged custody and delay in trial justify bail?" />

        <div className="mt-10">
          <p className="mb-2 text-[12px] font-semibold uppercase tracking-wider text-muted">What the corpus contains</p>
          {corpus ? (
            <ul className="space-y-1.5">
              {corpus.sources.map((s) => (
                <li key={s.source} className={cx('flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-[13px]', !s.documents && 'opacity-60')}>
                  <BookOpen className="size-4 text-muted" /><span className="flex-1">{s.name}</span>
                  <span className="text-muted">{s.documents} documents{s.coverage ? ` · ${s.coverage}` : ''}</span>
                  <Badge tone={s.status === 'APPROVED' ? 'ok' : s.status === 'REJECTED' ? 'bad' : 'warn'}>{s.status.replace('_', ' ').toLowerCase()}</Badge>
                </li>
              ))}
            </ul>
          ) : <EmptyState title="Loading corpus status…" />}
          <p className="mt-2 text-[12px] text-faint">Statutes and the Constitution are not loaded: their official publisher requires permission for reuse. FormLaw shows only what it can cite.</p>
        </div>
      </div>
    </div>
  )
}
