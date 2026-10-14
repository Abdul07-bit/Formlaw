import { useQueryClient } from '@tanstack/react-query'
import { Lock, PanelRightOpen, Send, ShieldAlert, Upload } from 'lucide-react'
import { useCallback, useState } from 'react'
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ApprovalDialog } from '../../components/workbench/ApprovalDialog'
import { ChatWindow } from '../../components/workbench/ChatWindow'
import { RightPanel } from '../../components/workbench/RightPanel'
import { UploadDialog } from '../../components/workbench/UploadDialog'
import { useViewer } from '../../components/workbench/viewer'
import {
  ActivityView, AuditView, AuthoritiesView, ClaimsView, ContradictionsView, DocumentsView, DraftsView, EvidenceView, MissingView,
  OverviewView, SavedView, TasksView, TimelineView,
} from '../../components/workbench/views'
import { Badge, Button, EmptyState, IconButton, Select, Skeleton } from '../../components/ui'
import { useAuth } from '../../lib/auth'
import { useCase, useInvalidateCase } from '../../lib/queries'
import type { RunResult } from '../../lib/types'
import { cx, label, usePref } from '../../lib/util'

const PRIMARY = [['chat', 'Chat'], ['documents', 'Documents'], ['overview', 'Overview']] as const
const MORE = [['evidence', 'Evidence'], ['timeline', 'Timeline'], ['claims', 'Claims'], ['contradictions', 'Contradictions'], ['missing', 'Missing information'],
  ['research', 'Legal research'], ['drafts', 'Drafts'], ['tasks', 'Tasks'], ['saved', 'Saved findings'], ['activity', 'Agent activity'], ['audit', 'Audit log']] as const

export default function CaseWorkspace() {
  const { caseId, threadId } = useParams()
  const { data: kase, isLoading, error } = useCase(caseId)
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const view = params.get('view') ?? 'chat'
  const nav = useNavigate()
  const location = useLocation()
  const qc = useQueryClient()
  const invalidate = useInvalidateCase()
  const openDoc = useViewer()
  const [panel, setPanel] = usePref('rightPanel', true)
  const [upload, setUpload] = useState(params.get('upload') === '1')
  const [updateClient, setUpdateClient] = useState(false)
  const [lastResult, setLastResult] = useState<RunResult | null>(null)
  const [prompt, setPrompt] = useState<string | null>((location.state as { prompt?: string } | null)?.prompt ?? null)
  const onResult = useCallback((r: RunResult | null) => setLastResult(r), [])

  if (isLoading) return <div className="space-y-3 p-6"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-64" /></div>
  if (error || !kase) return <div className="p-6"><EmptyState title="Case not found">You may not have access to this case.</EmptyState></div>

  const ask = (p: string) => { setPrompt(p); setParams({}); nav(`/cases/${kase.id}`, { state: { prompt: p } }) }
  const setView = (v: string) => setParams(v === 'chat' ? {} : { view: v })

  return (
    <div className="flex h-full min-h-0">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line px-4 py-2.5">
          <div className="min-w-0">
            <h1 className="truncate font-serif text-[18px] font-semibold leading-tight">{kase.title}</h1>
            <p className="flex flex-wrap items-center gap-1.5 text-[12px] text-muted">
              <span className="font-mono">{kase.reference}</span>·<span>{label(kase.matterType)}</span>·
              <Badge tone={kase.status === 'active' ? 'ok' : 'neutral'}>{kase.status}</Badge>
              <span className="inline-flex items-center gap-1" title="Only members of this case in your organization can open it. Every access is audited."><Lock className="size-3" />Private · {user?.organizationName}</span>
              {kase.flaggedDocuments > 0 && <span className="inline-flex items-center gap-1 text-bad"><ShieldAlert className="size-3" />{kase.flaggedDocuments} document(s) contain AI instructions</span>}
              {kase.isDemo && <Badge>synthetic demo</Badge>}
            </p>
          </div>
          <nav className="ml-auto flex max-w-full flex-wrap items-center gap-1" aria-label="Case views">
            {PRIMARY.map(([id, l]) => (
              <button key={id} type="button" onClick={() => setView(id)} className={cx('rounded-md px-2.5 py-1 text-[13px]', view === id ? 'bg-surface-3 font-medium' : 'text-muted hover:text-fg')}>{l}</button>
            ))}
            <Select aria-label="More views" value={MORE.some(([id]) => id === view) ? view : ''} onChange={(e) => setView(e.target.value)} className="h-7 w-32 px-2 text-[13px]">
              <option value="" disabled>More…</option>
              {MORE.map(([id, l]) => <option key={id} value={id}>{l}</option>)}
            </Select>
            <Button size="sm" onClick={() => setUpload(true)}><Upload className="size-3.5" />Add</Button>
            <Button size="sm" onClick={() => setUpdateClient(true)} title="Send a lawyer-approved update to the client portal"><Send className="size-3.5" />Update client</Button>
            {view === 'chat' && !panel && <IconButton label="Open context panel" onClick={() => setPanel(true)}><PanelRightOpen className="size-4" /></IconButton>}
          </nav>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {view === 'chat' && (
            <ChatWindow key={kase.id} kase={kase} threadId={threadId} initialPrompt={threadId ? null : prompt}
              onThread={(t) => { setPrompt(null); nav(`/cases/${kase.id}/t/${t}`, { replace: true }) }} onResult={onResult} onAttach={() => setUpload(true)} />
          )}
          {view === 'overview' && <OverviewView kase={kase} onAsk={ask} />}
          {view === 'documents' && <DocumentsView kase={kase} onUpload={() => setUpload(true)} onOpen={(id) => openDoc({ documentId: id })} />}
          {view === 'evidence' && <EvidenceView kase={kase} />}
          {view === 'timeline' && <TimelineView kase={kase} />}
          {view === 'claims' && <ClaimsView kase={kase} />}
          {view === 'contradictions' && <ContradictionsView kase={kase} />}
          {view === 'missing' && <MissingView kase={kase} />}
          {view === 'research' && <AuthoritiesView kase={kase} onAsk={ask} />}
          {view === 'drafts' && <DraftsView kase={kase} onAsk={ask} />}
          {view === 'tasks' && <TasksView kase={kase} />}
          {view === 'saved' && <SavedView kase={kase} />}
          {view === 'activity' && <ActivityView kase={kase} />}
          {view === 'audit' && <AuditView kase={kase} />}
        </div>
      </div>
      {view === 'chat' && panel && (
        <div className="hidden w-[380px] shrink-0 xl:block"><RightPanel kase={kase} result={lastResult} onClose={() => setPanel(false)} /></div>
      )}
      <UploadDialog open={upload} onClose={() => { setUpload(false); if (params.get('upload')) setParams({}) }} caseId={kase.id}
        onUploaded={() => { invalidate(kase.id); qc.invalidateQueries({ queryKey: ['documents', kase.id] }) }} />
      <ApprovalDialog open={updateClient} onClose={() => setUpdateClient(false)} action="client_update.send" resourceId={kase.id}
        title="Send an update to the client" withMessage />
    </div>
  )
}
