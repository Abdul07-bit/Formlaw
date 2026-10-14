import { PanelRightClose, ShieldAlert } from 'lucide-react'
import { useState } from 'react'
import type { Case, RunResult } from '../../lib/types'
import { Badge, EmptyState, IconButton, SectionTitle, Tabs } from '../ui'
import { Citation } from './Citation'
import { ActivityView, ClaimsView, ContradictionsView, MissingView, TimelineView } from './views'

type Tab = 'evidence' | 'timeline' | 'claims' | 'risks' | 'activity'

export function RightPanel({ kase, result, onClose }: { kase: Case; result: RunResult | null; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>('evidence')
  return (
    <aside aria-label="Case context" className="flex h-full w-full flex-col border-l border-line bg-surface">
      <div className="flex items-center gap-1 border-b border-line px-2 py-2">
        <Tabs<Tab> value={tab} onChange={setTab} items={[
          { id: 'evidence', label: 'Evidence', count: result?.evidence.length },
          { id: 'timeline', label: 'Timeline' }, { id: 'claims', label: 'Claims' },
          { id: 'risks', label: 'Risks', count: (result?.security.length ?? 0) || undefined }, { id: 'activity', label: 'Activity' },
        ]} />
        <IconButton label="Close panel" className="ml-auto" onClick={onClose}><PanelRightClose className="size-4" /></IconButton>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {tab === 'evidence' && (!result?.evidence.length ? <EmptyState title="No evidence yet">Evidence behind the latest answer appears here.</EmptyState> : (
          <div className="space-y-2">
            <p className="text-[12px] text-muted">Passages behind the latest answer.</p>
            {result.evidence.map((e) => (
              <div key={e.chunkId} className={`rounded-lg border p-2.5 ${e.securityFlags.length ? 'border-bad/40 bg-bad-soft/40' : 'border-line bg-bg'}`}>
                <Citation c={{ chunkId: e.chunkId, documentId: e.documentId, documentName: e.documentName, page: e.page, paragraph: e.paragraph, quote: e.text.slice(0, 200) }} />
                {e.securityFlags.length > 0 && <Badge tone="bad" className="ml-1.5"><ShieldAlert className="size-3" />excluded from AI</Badge>}
                <p className="mt-1.5 line-clamp-6 font-serif text-[13.5px] leading-relaxed text-muted">{e.text}</p>
              </div>
            ))}
          </div>
        ))}
        {tab === 'timeline' && <TimelineView kase={kase} compact />}
        {tab === 'claims' && <ClaimsView kase={kase} compact />}
        {tab === 'risks' && (
          <div className="space-y-5">
            {!!result?.security.length && (
              <div><SectionTitle>Security</SectionTitle>
                {result.security.map((s, i) => <p key={i} className="mb-1 rounded-lg bg-bad-soft/50 px-2.5 py-1.5 text-[12.5px] text-bad">{s.source}: instructions blocked from AI context</p>)}
              </div>
            )}
            <div><SectionTitle>Contradictions</SectionTitle><ContradictionsView kase={kase} compact /></div>
            <div><SectionTitle>Missing information</SectionTitle><MissingView kase={kase} compact /></div>
          </div>
        )}
        {tab === 'activity' && <ActivityView kase={kase} compact />}
      </div>
    </aside>
  )
}
