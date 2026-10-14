import { motion } from 'framer-motion'
import { AlertTriangle, ArrowRight, FilePlus2, FileText, FolderOpen, MessagesSquare, PlayCircle, ShieldAlert, ShieldCheck, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Badge, Button, EmptyState, PageHeader, Stat } from '../../components/ui'
import { useDB, useSession } from '../../hooks/useStore'
import { errorMessage } from '../../services/api/client'
import { createDemoCase } from '../../services/cases'

export default function ClientDashboard() {
  const user = useSession()!
  const nav = useNavigate()
  const allCases = useDB((d) => d.cases)
  const conversations = useDB((d) => d.conversations)
  const cases = useMemo(() => allCases.filter((c) => c.ownerId === user.id), [allCases, user.id])
  const convs = useMemo(() => conversations.filter((c) => c.clientId === user.id), [conversations, user.id])
  const totals = useMemo(() => ({
    docs: cases.reduce((n, c) => n + c.documents.length, 0),
    claims: cases.reduce((n, c) => n + (c.analysis?.verification.analysed ?? 0), 0),
    risks: cases.reduce((n, c) => n + (c.analysis ? c.analysis.contradictions.length + c.analysis.security.length : 0), 0),
  }), [cases])

  const [demoErr, setDemoErr] = useState('')
  const demo = (m = false) => { setDemoErr(''); createDemoCase(m).then((c) => nav(`/app/cases/${c.id}?run=1`)).catch((e) => setDemoErr(errorMessage(e))) }

  return (
    <>
      <PageHeader eyebrow="Client workspace" title={`Namaste, ${user.name.split(' ')[0]} 👋`} subtitle="Upload your documents, let FormLaw agents prepare an evidence-backed brief, then connect with verified counsel."
        actions={<Button to="/app/cases/new" icon={<FilePlus2 className="size-5" />}>New case</Button>} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Active cases" value={cases.length} icon={<FolderOpen className="size-4" />} />
        <Stat label="Documents" value={totals.docs} icon={<FileText className="size-4" />} />
        <Stat label="Verified claims" value={totals.claims} icon={<ShieldCheck className="size-4" />} tone="green" />
        <Stat label="Risk alerts" value={totals.risks} icon={<AlertTriangle className="size-4" />} tone="amber" />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div>
          <h2 className="mb-4 text-xl">Your cases</h2>
          {cases.length === 0 ? (
            <EmptyState icon={<FolderOpen className="size-7" />} title="No cases yet." body="Create your first case to begin evidence-grounded analysis — or load the demo case." action={<div className="mt-2 flex gap-2"><Button to="/app/cases/new" size="sm">Create case</Button><Button variant="secondary" size="sm" onClick={() => demo()}>Load demo</Button></div>} />
          ) : (
            <div className="space-y-4">
              {cases.map((c, i) => (
                <motion.div key={c.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                  <Link to={`/app/cases/${c.id}`} className="card card-hover group flex flex-col gap-4 p-5 md:flex-row md:items-center">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="truncate text-lg">{c.title}</h3>
                        {c.isDemo && <Badge tone="violet">Demo</Badge>}
                        {c.analysis ? <Badge tone="green">Review completed</Badge> : <Badge tone="slate">Not reviewed</Badge>}
                      </div>
                      <p className="mt-1 font-mono text-xs font-bold text-ink-soft">{c.id}</p>
                      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm font-bold text-ink-soft">
                        <span>{c.documents.length} documents</span>
                        {c.analysis && <>
                          <span>{c.analysis.area}</span>
                          <span className={c.analysis.contradictions.length ? 'text-rose-600' : ''}>{c.analysis.contradictions.length} contradictions</span>
                          <span>{c.analysis.verification.analysed} claims</span>
                          <span>{c.analysis.verification.coverage}% evidence coverage</span>
                          {c.analysis.security.length > 0 && <span className="text-rose-600">threat blocked</span>}
                        </>}
                      </div>
                    </div>
                    <span className="flex items-center gap-1 text-sm font-extrabold text-sky-600 transition group-hover:gap-2">Open workspace <ArrowRight className="size-4" /></span>
                  </Link>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-sky-500 to-sky-700 p-6 text-white">
            <Sparkles className="absolute -right-4 -top-4 size-28 opacity-15" />
            <p className="text-xs font-extrabold uppercase tracking-wider opacity-80">Demo · synthetic case</p>
            <h3 className="mt-1 text-xl !text-white">State v. Arjun Kumar</h3>
            <p className="mt-1 text-sm font-semibold text-sky-50">FIR, witness statement, remand report, case diary, attendance record, bail note.</p>
            <div className="mt-4 flex flex-col gap-2">
              <Button variant="dark" onClick={() => demo()} icon={<PlayCircle className="size-5" />}>Run full agentic review</Button>
              <button onClick={() => demo(true)} className="flex items-center justify-center gap-2 rounded-2xl bg-white/15 py-2.5 text-sm font-extrabold transition hover:bg-white/25"><ShieldAlert className="size-4" />Run with malicious document</button>
              {demoErr && <p className="rounded-xl bg-white/90 p-2 text-xs font-bold text-rose-700" role="alert">{demoErr}</p>}
            </div>
          </div>
          <div className="card p-5">
            <h3 className="flex items-center gap-2 text-lg"><MessagesSquare className="size-5 text-sky-500" />Lawyer connections</h3>
            {convs.length === 0 ? <p className="mt-3 text-sm font-semibold text-ink-soft">No connections yet. Run a review to get matched with verified advocates.</p> : (
              <ul className="mt-3 space-y-2">
                {convs.slice(0, 5).map((c) => (
                  <li key={c.id}><Link to="/app/messages" className="flex items-center justify-between rounded-2xl px-3 py-2 hover:bg-sky-50"><span className="truncate text-sm font-bold">{c.caseTitle}</span><Badge tone={c.status === 'accepted' ? 'green' : c.status === 'declined' ? 'red' : 'amber'}>{c.status}</Badge></Link></li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
