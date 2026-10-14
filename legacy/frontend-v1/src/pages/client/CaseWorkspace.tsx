import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertTriangle, BookOpenCheck, CheckCircle2, FilePlus2, FileText, Gavel, Handshake, Lock, MessageSquareText,
  PenLine, RefreshCw, ScrollText, ShieldAlert, Terminal, XCircle,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { AgentPipeline, AgentTrace } from '../../components/agents'
import { CompareView, ContradictionCard, EvidencePanel, FactCard, MissingCard, SecurityEventCard, VerificationPanel } from '../../components/case/Evidence'
import { AgentDraft } from '../../components/case/AgentDraft'
import { GroundedChat } from '../../components/case/GroundedChat'
import { ConnectModal, LawyerCard, RelatedCaseCard } from '../../components/case/Lawyers'
import { DocumentUpload, processingNote, toItems, type UploadItem } from '../../components/case/Upload'
import { Badge, Button, cx, DemoTag, EmptyState, Modal } from '../../components/ui'
import { useDB } from '../../hooks/useStore'
import { errorMessage } from '../../services/api/client'
import { loadCase, runReview, uploadDocuments } from '../../services/cases'
import { decideAction, prepareAction } from '../../services/connections'
import type { Analysis, Approval, Contradiction, Evidence } from '../../types'

type Tab = 'review' | 'ask' | 'lawyers' | 'related' | 'draft' | 'trace'
const TABS: { id: Tab; label: string; icon: ReactNode }[] = [
  { id: 'review', label: 'AI Review', icon: <BookOpenCheck className="size-4" /> },
  { id: 'ask', label: 'Ask AI', icon: <MessageSquareText className="size-4" /> },
  { id: 'lawyers', label: 'Matched Lawyers', icon: <Handshake className="size-4" /> },
  { id: 'related', label: 'Related Cases', icon: <Gavel className="size-4" /> },
  { id: 'draft', label: 'Draft', icon: <PenLine className="size-4" /> },
  { id: 'trace', label: 'Agent Trace', icon: <Terminal className="size-4" /> },
]

export default function CaseWorkspace() {
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const c = useDB((d) => d.cases.find((x) => x.id === id))
  const lawyers = useDB((d) => d.lawyers)
  const completed = useDB((d) => d.completedCases)
  const [running, setRunning] = useState<Analysis | 'waiting' | null>(null)
  const [runError, setRunError] = useState('')
  const [chatEvidence, setChatEvidence] = useState<Evidence[]>([])
  const [uploads, setUploads] = useState<UploadItem[]>([])
  const [loadError, setLoadError] = useState('')
  const [tab, setTab] = useState<Tab>('review')
  const [selected, setSelected] = useState<string | null>(null)
  const [compare, setCompare] = useState<Contradiction | null>(null)
  const [connectId, setConnectId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [addOpen, setAddOpen] = useState(false)
  const started = useRef(false)

  const owner = c?.access === 'owner'

  const start = async () => {
    if (!c || !owner) return
    setRunError(''); setRunning('waiting'); setTab('review')
    try { setRunning(await runReview(c.id)) } catch (e) { setRunning(null); setRunError(errorMessage(e)) }
  }

  // Direct links: fetch the case if it is not cached yet (the server decides whether you may see it).
  useEffect(() => { if (id && !c) loadCase(id).catch((e) => setLoadError(errorMessage(e))) }, [id, c])

  useEffect(() => {
    if (!c || started.current || !owner) return
    if (params.get('run') === '1' || (!c.analysis && c.documents.length)) {
      started.current = true
      void start()
      setParams({}, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [c?.id])

  const addFiles = useCallback(async (files: File[]) => {
    if (!c) return
    const items = toItems(files)
    setUploads((p) => [...items, ...p])
    for (const it of items) {
      setUploads((p) => p.map((x) => (x.key === it.key ? { ...x, status: 'uploading' } : x)))
      try {
        const [doc] = await uploadDocuments(c.id, [it.file])
        setUploads((p) => p.map((x) => (x.key === it.key ? { ...x, status: 'done', note: processingNote(doc.processingStatus) } : x)))
      } catch (e) {
        setUploads((p) => p.map((x) => (x.key === it.key ? { ...x, status: 'error', error: errorMessage(e) } : x)))
      }
    }
    setToast('Documents added — re-run the review to include them')
  }, [c])

  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(null), 3500); return () => clearTimeout(t) } }, [toast])

  const a = c?.analysis
  const selEv = useMemo(() => a?.evidence.find((e) => e.id === selected) ?? chatEvidence.find((e) => e.id === selected), [a, selected, chatEvidence])
  const openEvidence = (eid: string) => { setSelected(eid); if (window.innerWidth < 1024) setTimeout(() => document.getElementById('evidence-panel')?.scrollIntoView({ behavior: 'smooth' }), 50) }

  if (!c) return loadError
    ? <EmptyState icon={<FileText className="size-7" />} title="Case not found" body="It may have been removed or belongs to another account." action={<Button to="/app" size="sm">Back</Button>} />
    : <div className="space-y-4"><div className="skeleton h-10 w-1/3" /><div className="skeleton h-40" /></div>

  return (
    <>
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <Link to="/app/client" className="text-sm font-bold text-sky-600 hover:underline">← My cases</Link>
          <h1 className="mt-1 text-3xl md:text-4xl">Case: {c.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge tone="slate"><span className="font-mono">{c.id}</span></Badge>
            {a && <Badge>{a.area}</Badge>}
            <Badge tone="slate">{c.documents.length} documents</Badge>
            {a && (a.contradictions.length ? <Badge tone="red">{a.contradictions.length} contradiction</Badge> : <Badge tone="green">No contradictions</Badge>)}
            {a && a.security.length > 0 && <Badge tone="red" icon={<ShieldAlert className="size-3" />}>Threat blocked</Badge>}
            {c.isDemo && <DemoTag />}
          </div>
        </div>
        {owner ? (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setAddOpen(true)} icon={<FilePlus2 className="size-4" />}>Add documents</Button>
            <Button onClick={start} disabled={!!running || !c.documents.length} icon={<RefreshCw className="size-4" />}>Run review</Button>
          </div>
        ) : <Badge tone="violet">Counsel view · evidence brief only</Badge>}
      </div>

      {runError && <p className="mb-6 flex items-center gap-2 rounded-2xl bg-rose-50 p-4 text-sm font-bold text-rose-700" role="alert"><AlertTriangle className="size-4 shrink-0" />{runError}</p>}
      {/* Enter-only transitions: results must never wait on an exit animation. */}
      <>
        {running === 'waiting' ? (
          <motion.div key="wait" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card mx-auto max-w-3xl p-8 text-center" role="status">
            <RefreshCw className="mx-auto size-8 animate-spin text-sky-500" />
            <p className="mt-4 text-lg font-extrabold">Agents are reviewing your documents…</p>
            <p className="mt-1 text-sm font-semibold text-ink-soft">Security scan → case review → verification → research → matching. Nothing is shown until it has been checked against evidence.</p>
          </motion.div>
        ) : running ? (
          <motion.div key="run" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mx-auto max-w-3xl">
            <AgentPipeline steps={running.trace} title="Analyzing request…" onDone={() => setRunning(null)} />
            <p className="mt-4 text-center text-sm font-semibold text-ink-soft">Agents are working on your documents. Nothing is shown until it has been checked against evidence.</p>
          </motion.div>
        ) : !a ? (
          <EmptyState key="none" icon={<BookOpenCheck className="size-7" />} title="Not reviewed yet"
            body={c.documents.length ? 'Run the agentic review to extract evidence-backed facts.' : 'Add documents to this case, then run the review.'}
            action={owner ? (c.documents.length ? <Button onClick={start}>Run review</Button> : <Button onClick={() => setAddOpen(true)}>Add documents</Button>) : undefined} />
        ) : (
          <motion.div key="res" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
            <div className="-mx-4 mb-6 overflow-x-auto px-4 scrollbar-thin md:mx-0 md:px-0">
              <div className="flex w-max gap-1 rounded-2xl bg-white p-1.5 shadow-[var(--shadow-soft)] ring-1 ring-sky-100" role="tablist">
                {TABS.filter((t) => owner || (t.id !== 'ask' && t.id !== 'lawyers')).map((t) => (
                  <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)} className="relative flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-extrabold">
                    {tab === t.id && <motion.span layoutId="ws-tab" className="absolute inset-0 rounded-xl bg-sky-500" transition={{ type: 'spring', damping: 26, stiffness: 320 }} />}
                    <span className={cx('relative flex items-center gap-2', tab === t.id ? 'text-white' : 'text-ink-soft')}>{t.icon}{t.label}
                      {t.id === 'lawyers' && <span className={cx('rounded-full px-1.5 text-[11px]', tab === t.id ? 'bg-white/25' : 'bg-sky-100 text-sky-700')}>{a.matches.length}</span>}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <motion.div key={tab} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
                {tab === 'review' && (
                  <div className="grid gap-6 lg:grid-cols-[200px_1fr_320px]">
                    {/* Documents */}
                    <aside className="space-y-2">
                      <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-ink-soft">Documents</p>
                      {c.documents.map((d) => {
                        const flagged = d.processingStatus === 'quarantined' || a.security.some((s) => s.docName === d.name)
                        return (
                          <div key={d.id} className={cx('flex items-center gap-2 rounded-2xl bg-white px-3 py-2.5 text-sm font-bold ring-1', flagged ? 'ring-rose-200' : 'ring-sky-100')}>
                            {flagged ? <ShieldAlert className="size-4 shrink-0 text-rose-500" /> : <FileText className="size-4 shrink-0 text-sky-500" />}
                            <span className="truncate" title={d.name}>{d.name}</span>
                          </div>
                        )
                      })}
                      <div className="flex items-start gap-1.5 rounded-2xl bg-amber-50 p-3 text-xs font-bold text-amber-800"><Lock className="mt-0.5 size-3.5 shrink-0" />All documents are treated as untrusted content.</div>
                    </aside>

                    {/* AI review */}
                    <div className="min-w-0 space-y-6">
                      <div className="card p-6">
                        <div className="flex items-center justify-between"><h2 className="text-xl">Executive summary</h2><Badge tone="sky">{Math.round(a.areaConfidence * 100)}% {a.area}</Badge></div>
                        <p className="mt-3 text-[15px] font-semibold leading-relaxed text-ink-soft">{a.summary}</p>
                      </div>
                      {a.security.map((e) => <SecurityEventCard key={e.id} e={e} />)}
                      {a.contradictions.length > 0 ? a.contradictions.map((x) => <ContradictionCard key={x.id} c={x} evidence={a.evidence} onCompare={setCompare} />)
                        : <div className="card flex items-center gap-3 p-5 text-sm font-bold text-ink-soft"><CheckCircle2 className="size-5 text-emerald-500" />No contradictions detected. FormLaw will surface conflicting evidence here.</div>}
                      <div>
                        <h2 className="mb-3 text-xl">Key facts</h2>
                        {a.facts.length ? <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">{a.facts.map((f, i) => <FactCard key={f.id} fact={f} evidence={a.evidence} onOpen={openEvidence} i={i} />)}</div>
                          : <div className="card p-6 text-sm font-semibold text-ink-soft"><p className="font-extrabold text-ink">We couldn’t verify any claims.</p>The available evidence is insufficient. Recommended: upload text-based documents (TXT/CSV) or wait for server-side extraction of PDFs and images.</div>}
                      </div>
                      <div>
                        <h2 className="mb-3 text-xl">Missing information</h2>
                        <div className="grid gap-3">{a.missing.length ? a.missing.map((m, i) => <MissingCard key={m.id} m={m} i={i} />) : <p className="text-sm font-semibold text-ink-soft">No critical gaps against the {a.area.toLowerCase()} checklist.</p>}</div>
                      </div>
                    </div>

                    {/* Evidence */}
                    <aside id="evidence-panel" className="space-y-4 lg:sticky lg:top-24 lg:self-start">
                      <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-ink-soft">Evidence</p>
                      <AnimatePresence mode="wait">
                        {selEv ? (
                          <motion.div key={selEv.id} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                            <EvidencePanel ev={selEv} doc={c.documents.find((d) => d.id === selEv.docId)} />
                          </motion.div>
                        ) : <div className="rounded-3xl border-2 border-dashed border-sky-200 p-5 text-center text-sm font-semibold text-ink-soft">Click any evidence reference to view the source text.</div>}
                      </AnimatePresence>
                      <ul className="max-h-72 space-y-1.5 overflow-auto pr-1 scrollbar-thin">
                        {a.evidence.map((e) => (
                          <li key={e.id}>
                            <button onClick={() => setSelected(e.id)} className={cx('w-full rounded-2xl px-3 py-2 text-left transition', selected === e.id ? 'bg-sky-500 text-white' : 'bg-white ring-1 ring-sky-100 hover:ring-sky-300')}>
                              <span className="font-mono text-xs font-extrabold">{e.id}</span>
                              <span className={cx('block truncate text-xs font-bold', selected === e.id ? 'text-sky-50' : 'text-ink-soft')}>{e.docName} · p.{e.page}</span>
                            </button>
                          </li>
                        ))}
                      </ul>
                      <VerificationPanel v={a.verification} />
                    </aside>
                  </div>
                )}

                {tab === 'ask' && (
                  <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
                    <GroundedChat caseId={c.id} analysis={a} onOpenEvidence={openEvidence}
                      onEvidence={(evs) => setChatEvidence((p) => [...evs, ...p.filter((x) => !evs.some((e) => e.id === x.id))])} />
                    <aside id="evidence-panel" className="space-y-3 lg:sticky lg:top-24 lg:self-start">
                      <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-ink-soft">Source viewer</p>
                      {selEv ? <EvidencePanel ev={selEv} doc={c.documents.find((d) => d.id === selEv.docId)} /> : <div className="rounded-3xl border-2 border-dashed border-sky-200 p-6 text-center text-sm font-semibold text-ink-soft">Evidence you click in an answer opens here.</div>}
                    </aside>
                  </div>
                )}

                {tab === 'lawyers' && (
                  <>
                    <div className="mb-6 flex flex-col justify-between gap-2 md:flex-row md:items-end">
                      <div><h2 className="text-2xl">Recommended advocates</h2><p className="font-semibold text-ink-soft">Ranked by verified practice area, jurisdiction, related verified cases, availability and your budget. All KYC-verified.</p><p className="mt-1 text-xs font-bold text-ink-soft">{a.feeDisclaimer}</p></div>
                      <Button variant="secondary" to="/app/lawyers">Browse all</Button>
                    </div>
                    {a.matches.length ? (
                      <div className="grid gap-6 pt-3 md:grid-cols-2 xl:grid-cols-4">
                        {a.matches.map((m, i) => { const l = lawyers.find((x) => x.id === m.lawyerId); return l ? <LawyerCard key={l.id} l={l} match={m} i={i} basePath="/app/lawyers" onConnect={c.connectedLawyerIds.includes(l.id) ? undefined : () => setConnectId(l.id)} /> : null })}
                      </div>
                    ) : <EmptyState icon={<Handshake className="size-7" />} title="No verified advocates match yet" body="As more advocates complete KYC in this practice area, matches will appear here." />}
                    {c.connectedLawyerIds.length > 0 && <p className="mt-5 text-sm font-bold text-emerald-700">✓ Brief shared with {c.connectedLawyerIds.length} advocate(s). <Link to="/app/messages" className="underline">Open messages</Link></p>}
                  </>
                )}

                {tab === 'related' && (
                  <>
                    <h2 className="text-2xl">Related cases from the FormLaw database</h2>
                    <p className="mb-6 font-semibold text-ink-soft">Anonymised outcomes uploaded by advocates and verified by FormLaw. Not judicial precedent — do not cite as authority.</p>
                    {a.related.length ? <div className="grid gap-5 md:grid-cols-2">{a.related.map((r) => { const cc = completed.find((x) => x.id === r.caseId); return cc ? <RelatedCaseCard key={r.caseId} r={r} c={cc} lawyer={lawyers.find((l) => l.id === cc.lawyerId)} /> : null })}</div>
                      : <EmptyState icon={<Gavel className="size-7" />} title="No related cases yet" body="The database grows as advocates publish completed cases." />}
                  </>
                )}

                {tab === 'draft' && <div className="space-y-8"><AgentDraft caseId={c.id} a={a} readOnly={!owner} /><DraftTab a={a} caseId={c.id} owner={owner} /></div>}
                {tab === 'trace' && <AgentTrace taskId={a.taskId} steps={a.trace} />}
            </motion.div>
          </motion.div>
        )}
      </>

      <Modal open={!!compare} onClose={() => setCompare(null)} title={`Conflicting evidence — ${compare?.topic ?? ''}`} wide>
        {compare && a && <CompareView c={compare} evidence={a.evidence} docs={c.documents} />}
      </Modal>
      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Add evidence" wide>
        <DocumentUpload compact onFiles={addFiles} items={uploads} />
      </Modal>
      <ConnectModal open={!!connectId} onClose={() => setConnectId(null)} lawyer={lawyers.find((l) => l.id === connectId)} caseId={c.id} onSent={() => { setConnectId(null); setToast('Case brief sent. The advocate will respond in Messages.') }} />
      <AnimatePresence>
        {toast && <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }} className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-2xl bg-ink px-5 py-3 text-sm font-bold text-white shadow-2xl" role="status">{toast}</motion.div>}
      </AnimatePresence>
    </>
  )
}

function DraftTab({ a, caseId, owner }: { a: Analysis; caseId: string; owner: boolean }) {
  const [approval, setApproval] = useState<'idle' | 'pending' | 'approved' | 'rejected'>('idle')
  const [req, setReq] = useState<Approval | null>(null)
  const [err, setErr] = useState('')
  const conversations = useDB((d) => d.conversations)
  const accepted = useMemo(() => conversations.filter((x) => x.caseId === caseId && x.status === 'accepted'), [conversations, caseId])
  const prepare = async () => {
    setErr('')
    try { setReq(await prepareAction('draft.share', caseId, { connectionId: accepted[0].id })); setApproval('pending') } catch (e) { setErr(errorMessage(e)) }
  }
  const decide = async (ok: boolean) => {
    if (!req) return
    try { await decideAction(req.id, ok); setApproval(ok ? 'approved' : 'rejected') } catch (e) { setErr(errorMessage(e)) }
  }
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between border-b border-sky-100 bg-sky-25 px-6 py-4">
          <h2 className="flex items-center gap-2 text-lg"><ScrollText className="size-5 text-sky-500" />{a.draft.title}</h2>
          <Badge tone="amber">Human review required</Badge>
        </div>
        <pre className="max-h-[640px] overflow-auto whitespace-pre-wrap p-6 font-mono text-[13px] leading-7 text-ink scrollbar-thin">{a.draft.body}</pre>
      </div>
      <aside className="space-y-4">
        <div className="card p-5">
          <p className="text-xs font-extrabold uppercase tracking-wider text-ink-soft">Drafting pipeline</p>
          <ol className="mt-3 space-y-2 text-sm font-bold">
            {['Drafting Agent', 'Evidence retrieval', 'Draft generation', 'Citation verification', 'Human review'].map((s, i) => (
              <li key={s} className="flex items-center gap-2">{i < 4 ? <CheckCircle2 className="size-4 text-emerald-500" /> : <AlertTriangle className="size-4 text-amber-500" />}{s}</li>
            ))}
          </ol>
        </div>
        <div className={cx('overflow-hidden rounded-3xl border-2 bg-white', approval === 'approved' ? 'border-emerald-200' : approval === 'rejected' ? 'border-slate-200' : 'border-amber-200')}>
          <div className="bg-amber-50 px-5 py-3"><p className="flex items-center gap-2 font-extrabold text-amber-800"><Lock className="size-4" />Human approval required</p></div>
          <div className="space-y-2 p-5 text-sm">
            <p><span className="font-extrabold">Action:</span> {req?.summary ?? 'Send this draft to your connected advocate'}</p>
            <p><span className="font-extrabold">Risk:</span> <Badge tone="red">HIGH</Badge></p>
            <p className="font-semibold text-ink-soft">External communication. The action is prepared but cannot run without your explicit approval.</p>
            {!owner ? <p className="font-semibold text-ink-soft">Only the client can share this draft.</p>
              : !accepted.length ? <p className="rounded-xl bg-slate-100 p-3 font-semibold text-ink-soft">Available once an advocate accepts your brief.</p>
                : approval === 'idle' && <Button className="mt-2 w-full" variant="secondary" onClick={prepare}>Review action</Button>}
            {approval === 'pending' && (
              <div className="mt-2 grid grid-cols-2 gap-2">
                <Button onClick={() => decide(true)} icon={<CheckCircle2 className="size-4" />}>Approve</Button>
                <Button variant="secondary" onClick={() => decide(false)} icon={<XCircle className="size-4" />}>Reject</Button>
              </div>
            )}
            {err && <p className="mt-2 text-sm font-bold text-rose-600" role="alert">{err}</p>}
            {approval === 'approved' && <p className="mt-2 rounded-xl bg-emerald-50 p-3 font-bold text-emerald-800">Approved · draft sent in Messages and recorded in the audit log.</p>}
            {approval === 'rejected' && <p className="mt-2 rounded-xl bg-slate-100 p-3 font-bold text-ink-soft">Rejected · nothing was sent.</p>}
          </div>
        </div>
      </aside>
    </div>
  )
}
