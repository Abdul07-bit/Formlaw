import { useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight, Bell, Check, FileSearch, FolderOpen, Home, LogOut, MessageSquare, Moon, PlusCircle, RefreshCw, Send, Sun, Upload, Users } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, NavLink, Outlet, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Brand } from '../../components/layout/AppShell'
import { Hero3D, Reveal, Tilt } from '../../components/motion'
import { AdvocateCard, Dropzone, FileList, inr, ReviewPanel, type ReviewData } from '../../components/portal'
import { Badge, Button, Dialog, EmptyState, ErrorNote, Field, IconButton, Input, Skeleton, Textarea } from '../../components/ui'
import { ApiError, api, errorMessage } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useApi, useNotifications } from '../../lib/queries'
import type { ConnectionPolicyPublic, PublicLawyer } from '../../lib/types'
import { cx, label, timeAgo, useTheme } from '../../lib/util'

interface Intake {
  id: string; title: string; description: string; status: string; matterType: string | null; city: string; urgency: string; createdAt: string
  structured: { problem?: string; legal_domain?: string; timeline?: { date_text: string; event: string }[]; documents_mentioned?: string[]; questions_for_client?: string[]; missing_information?: string[]; urgency?: string; complexity?: string }
  documents: { id: string; filename: string; size: number }[]
  declaredParties: string[]; budgetMax: number | null; review: ReviewData | null; reviewedAt: string | null; reviewStale: boolean
  connections: { id: string; lawyerId: string; lawyerName: string; status: string; caseId: string | null; lawyerNote: string }[]
}
interface PortalCase { id: string; reference: string; title: string; status: string; matterType: string; lawyers: string[]; updatedAt: string }
interface Match { rank: number; reasons: string[]; considerations: string[]; budgetFit: string | null; lawyer: PublicLawyer }

const NAV = [
  { to: '/portal', label: 'Home', icon: <Home className="size-5" />, end: true },
  { to: '/portal/new', label: 'Get legal help', icon: <PlusCircle className="size-5" /> },
  { to: '/portal/notifications', label: 'Updates', icon: <Bell className="size-5" /> },
]

export function ClientShell() {
  const { user, logout } = useAuth()
  const [dark, toggle] = useTheme()
  const nav = useNavigate()
  const { data: notes } = useNotifications()
  const unread = notes?.filter((n) => !n.read).length ?? 0
  return (
    <div className="flex h-full flex-col">
      <header className="glass z-30 !border-x-0 !border-t-0">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-2.5 sm:px-6">
          <Brand to="/portal" />
          <nav className="hidden gap-1 text-sm md:flex">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} viewTransition className={({ isActive }) => cx('relative rounded-lg px-3 py-1.5 transition-colors', isActive ? 'bg-surface-3 font-medium' : 'text-muted hover:text-fg')}>
                {n.label}{n.to.endsWith('notifications') && unread > 0 && <span className="absolute right-1 top-1 size-2 rounded-full bg-accent" />}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-1">
            <span className="hidden text-[13px] text-muted sm:inline">{user?.name}</span>
            <IconButton label="Theme" onClick={toggle}>{dark ? <Sun className="size-4" /> : <Moon className="size-4" />}</IconButton>
            <IconButton label="Sign out" onClick={() => logout().then(() => nav('/'))}><LogOut className="size-4" /></IconButton>
          </div>
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto pb-20 md:pb-0"><Outlet /></main>
      {/* Phone: thumb-reachable tab bar */}
      <nav className="glass fixed inset-x-0 bottom-0 z-30 flex justify-around !border-x-0 !border-b-0 py-1.5 md:hidden" aria-label="Portal">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} viewTransition className={({ isActive }) => cx('flex flex-col items-center gap-0.5 rounded-xl px-4 py-1 text-[11px]', isActive ? 'text-accent' : 'text-muted')}>
            {n.icon}{n.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}

const STAGES = ['Described', 'Documents', 'Reviewed', 'Advocate', 'Accepted']
function stage(i: Intake): number {
  if (i.connections.some((c) => c.status === 'accepted')) return 5
  if (i.connections.length) return 4
  if (i.review) return 3
  if (i.documents.length) return 2
  return 1
}

function Progress({ at }: { at: number }) {
  return (
    <ol className="flex items-center gap-1" aria-label={`Step ${at} of ${STAGES.length}`}>
      {STAGES.map((s, k) => (
        <li key={s} className="flex flex-1 flex-col gap-1">
          <span className={cx('h-1.5 rounded-full transition-colors duration-500', k < at ? 'bg-accent' : 'bg-surface-3')} />
          <span className={cx('hidden text-[11px] sm:block', k < at ? 'text-fg' : 'text-faint')}>{s}</span>
        </li>
      ))}
    </ol>
  )
}

function ActionTile({ to, icon, title, text, delay }: { to: string; icon: ReactNode; title: string; text: string; delay: number }) {
  return (
    <Reveal delay={delay}>
      <Link to={to} viewTransition className="block h-full">
        <Tilt className="glass group h-full rounded-3xl p-5 shadow-card">
          <span className="flex size-11 items-center justify-center rounded-2xl bg-accent-soft text-accent transition-transform duration-300 group-hover:-translate-y-1">{icon}</span>
          <p className="mt-4 font-semibold">{title}</p>
          <p className="mt-1 text-[13.5px] text-muted">{text}</p>
          <ArrowRight className="mt-3 size-4 text-accent transition-transform duration-300 group-hover:translate-x-1" />
        </Tilt>
      </Link>
    </Reveal>
  )
}

export function PortalHome() {
  const { user } = useAuth()
  const { data: cases, isLoading } = useApi<PortalCase[]>(['portalCases'], '/portal/cases')
  const { data: intakes } = useApi<Intake[]>(['intakes'], '/intakes')
  const open = (intakes ?? []).filter((i) => i.status !== 'connected')
  const latest = open[0]
  return (
    <div>
      <section className="relative isolate overflow-hidden">
        <Hero3D variant="portal" />
        <div className="relative z-10 mx-auto max-w-7xl px-4 pb-14 pt-12 sm:px-6 sm:pt-16">
          <Reveal><p className="text-[13px] font-medium uppercase tracking-widest text-gold">Your legal workspace</p></Reveal>
          <Reveal delay={80}><h1 className="mt-2 font-serif text-4xl sm:text-5xl">Hello, {user?.name.split(' ')[0]}.</h1></Reveal>
          <Reveal delay={160}><p className="mt-3 max-w-xl text-lg text-muted">Upload your case files, see what they say, and find the right advocate — at your pace. Nothing is shared until you choose.</p></Reveal>
        </div>
      </section>
      <div className="mx-auto max-w-7xl space-y-12 px-4 pb-16 sm:px-6">
        <div className="-mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <ActionTile delay={0} to="/portal/new" icon={<PlusCircle className="size-5" />} title="Start a new matter" text="Describe what happened in your own words." />
          <ActionTile delay={80} to={latest ? `/portal/requests/${latest.id}?tab=documents` : '/portal/new'} icon={<Upload className="size-5" />} title="Upload case files" text="FIR, notices, agreements, letters, photos." />
          <ActionTile delay={160} to={latest ? `/portal/requests/${latest.id}?tab=documents` : '/portal/new'} icon={<FileSearch className="size-5" />} title="Review my documents" text="Timeline, conflicting dates, missing papers." />
          <ActionTile delay={240} to={latest ? `/portal/requests/${latest.id}?tab=advocates` : '/portal/new'} icon={<Users className="size-5" />} title="Find an advocate" text="Verified advocates, with fees beside your budget." />
        </div>

        {open.length > 0 && (
          <section>
            <h2 className="mb-3 font-serif text-2xl">In progress</h2>
            <ul className="grid gap-3 lg:grid-cols-2">
              {open.map((i, k) => (
                <Reveal as="li" key={i.id} delay={k * 60}>
                  <Link to={`/portal/requests/${i.id}`} viewTransition className="glass block rounded-3xl p-5 transition-shadow hover:shadow-card">
                    <div className="flex items-center gap-2">
                      <p className="flex-1 truncate text-lg font-semibold">{i.title}</p>
                      {i.urgency === 'urgent' && <Badge tone="bad">urgent</Badge>}
                      <Badge tone="accent">{label(i.matterType ?? 'other')}</Badge>
                    </div>
                    <p className="mb-3 mt-1 text-[13px] text-muted">{i.documents.length} file(s){i.budgetMax ? ` · budget ${inr(i.budgetMax)}` : ''} · started {timeAgo(i.createdAt)}</p>
                    <Progress at={stage(i)} />
                  </Link>
                </Reveal>
              ))}
            </ul>
          </section>
        )}

        <section>
          <h2 className="mb-3 font-serif text-2xl">Your matters</h2>
          {isLoading ? <Skeleton className="h-32" /> : !cases?.length ? (
            <EmptyState title="No active matters yet" action={<Link to="/portal/new" viewTransition><Button variant="primary">Get legal help</Button></Link>}>When an advocate accepts your request, your matter appears here with updates and messages.</EmptyState>
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {cases.map((c) => (
                <li key={c.id}>
                  <Link to={`/portal/matters/${c.id}`} viewTransition className="glass block rounded-3xl p-5 transition-shadow hover:shadow-card">
                    <div className="flex items-center gap-2"><p className="flex-1 truncate font-semibold">{c.title}</p><Badge tone={c.status === 'active' ? 'ok' : 'neutral'}>{c.status}</Badge></div>
                    <p className="mt-1 text-[13px] text-muted">{c.lawyers.join(', ') || 'Your advocate'} · {label(c.matterType)} · updated {timeAgo(c.updatedAt)}</p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}

const QUESTIONS = [
  ['when', 'When did this start? Any important dates?'],
  ['where', 'Where did it happen (city / court / police station)?'],
  ['urgent', 'Is anyone in custody, or is there a hearing or deadline coming up?'],
  ['goal', 'What outcome are you hoping for?'],
] as const
const BUDGETS = [10_000, 25_000, 50_000, 1_00_000, 2_50_000]
const WIZARD = ['Describe', 'A few questions', 'Budget', 'Documents', 'Review']

export function SubmitMatter() {
  const [step, setStep] = useState(0)
  const [f, setF] = useState({ title: '', description: '', city: '', language: '' })
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [parties, setParties] = useState('')
  const [budget, setBudget] = useState<number | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()
  const qc = useQueryClient()

  const create = async () => {
    setBusy(true); setErr('')
    try {
      const otherParties = [...new Set(parties.split(/[\n,;]/).map((x) => x.trim()).filter((x) => x.length >= 2))].slice(0, 10)
      const i = await api.post<Intake>('/intakes', { ...f, otherParties, budgetMax: budget, answers: Object.fromEntries(Object.entries(answers).filter(([, v]) => v.trim())) })
      if (files.length) {
        const fd = new FormData()
        files.slice(0, 10).forEach((x) => fd.append('files', x))
        await api.post<Intake>(`/intakes/${i.id}/documents`, fd)
        await api.post<Intake>(`/intakes/${i.id}/review`)
      }
      qc.invalidateQueries({ queryKey: ['intakes'] })
      nav(`/portal/requests/${i.id}?tab=${files.length ? 'documents' : 'overview'}`, { viewTransition: true })
    } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
  }
  const next = () => setStep((s) => Math.min(s + 1, WIZARD.length - 1))
  const back = () => setStep((s) => Math.max(s - 1, 0))
  return (
    <div className="mx-auto grid max-w-6xl gap-10 px-4 py-10 sm:px-6 lg:grid-cols-[220px_1fr]">
      <ol className="flex gap-2 lg:flex-col" aria-label="Steps">
        {WIZARD.map((s, i) => (
          <li key={s} className={cx('flex flex-1 items-center gap-3 rounded-2xl px-2 py-2 text-[13.5px] transition-colors lg:flex-none', i === step ? 'glass font-medium' : i < step ? 'text-fg' : 'text-faint')}>
            <span className={cx('flex size-7 shrink-0 items-center justify-center rounded-full border text-[12px] transition-all', i < step ? 'border-accent bg-accent text-on-accent' : i === step ? 'border-accent text-accent' : 'border-line')}>
              {i < step ? <Check className="size-3.5" /> : i + 1}
            </span>
            <span className="hidden sm:inline">{s}</span>
          </li>
        ))}
      </ol>
      <div key={step} className="max-w-2xl animate-[vt-in_.4s_both] space-y-4">
        {step === 0 && <>
          <h1 className="font-serif text-3xl sm:text-4xl">Tell us what happened</h1>
          <p className="text-muted">In your own words. FormLaw organises it into a structured summary. Nothing is shared with anyone unless you later choose to and confirm.</p>
          <Field label="Short title"><Input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="e.g. My employer has not paid my salary" /></Field>
          <Field label="What happened?" hint="At least a few sentences. Include dates, places and who was involved."><Textarea rows={8} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Your city"><Input value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} /></Field>
            <Field label="Preferred language"><Input value={f.language} onChange={(e) => setF({ ...f, language: e.target.value })} placeholder="English, Hindi…" /></Field>
          </div>
          <Button variant="primary" className="h-11 rounded-xl px-5" disabled={f.title.trim().length < 3 || f.description.trim().length < 20} onClick={next}>Continue <ArrowRight className="size-4" /></Button>
        </>}
        {step === 1 && <>
          <h1 className="font-serif text-3xl sm:text-4xl">A few questions</h1>
          {QUESTIONS.map(([k, q]) => <Field key={k} label={q}><Input value={answers[k] ?? ''} onChange={(e) => setAnswers({ ...answers, [k]: e.target.value })} /></Field>)}
          <Field label="Who else is involved? (optional)" hint="Names of the other side, e.g. your employer, landlord or the other spouse. Separate with commas. An advocate uses these only to check they are not already acting for someone involved.">
            <Input value={parties} onChange={(e) => setParties(e.target.value)} placeholder="e.g. Acme Logistics Pvt Ltd, Rakesh Verma" />
          </Field>
          <div className="flex gap-2"><Button variant="ghost" onClick={back}>Back</Button><Button variant="primary" className="h-11 rounded-xl px-5" onClick={next}>Continue <ArrowRight className="size-4" /></Button></div>
        </>}
        {step === 2 && <>
          <h1 className="font-serif text-3xl sm:text-4xl">What's your budget?</h1>
          <p className="text-muted">Roughly how much you can spend on an advocate for this matter. It's used to show which advocates' declared fees fit — and you can change it any time.</p>
          <div className="flex flex-wrap gap-2">
            {BUDGETS.map((b) => (
              <button key={b} type="button" aria-pressed={budget === b} onClick={() => setBudget(b)}
                className={cx('flex items-center gap-2 rounded-2xl border px-4 py-3 text-left transition-all', budget === b ? 'border-accent bg-accent-soft text-accent shadow-card ring-2 ring-accent' : 'border-line hover:border-accent')}>
                {budget === b && <Check className="size-4" />}<span className="block font-serif text-lg">up to {inr(b)}</span>
              </button>
            ))}
          </div>
          <Field label="Or enter an amount (₹)"><Input type="number" min={0} inputMode="numeric" value={budget ?? ''} onChange={(e) => setBudget(e.target.value ? Number(e.target.value) : null)} /></Field>
          <div className="flex gap-2"><Button variant="ghost" onClick={back}>Back</Button>
            <Button variant="ghost" onClick={() => { setBudget(null); next() }}>I'm not sure yet</Button>
            <Button variant="primary" className="h-11 rounded-xl px-5" onClick={next}>Continue <ArrowRight className="size-4" /></Button></div>
        </>}
        {step === 3 && <>
          <h1 className="font-serif text-3xl sm:text-4xl">Upload your case files</h1>
          <p className="text-muted">Optional, but it lets FormLaw show you a timeline, dates that don't match and documents that are missing.</p>
          <Dropzone onFiles={(x) => setFiles([...files, ...x].slice(0, 10))} />
          <FileList files={files.map((x, i) => ({ id: String(i), filename: x.name, size: x.size }))} onDelete={(id) => setFiles(files.filter((_, i) => String(i) !== id))} />
          <div className="flex gap-2"><Button variant="ghost" onClick={back}>Back</Button><Button variant="primary" className="h-11 rounded-xl px-5" onClick={next}>Continue <ArrowRight className="size-4" /></Button></div>
        </>}
        {step === 4 && <>
          <h1 className="font-serif text-3xl sm:text-4xl">Check and submit</h1>
          <div className="glass space-y-2 rounded-3xl p-5 text-[14.5px]">
            <p className="text-lg font-semibold">{f.title}</p>
            <p className="whitespace-pre-line text-muted">{f.description}</p>
            <p className="text-[13px] text-faint">{[f.city, f.language, budget ? `budget up to ${inr(budget)}` : 'no budget set', `${files.length} file(s)`, parties && `other parties: ${parties}`].filter(Boolean).join(' · ')}</p>
          </div>
          <p className="text-[13px] text-muted">FormLaw organises what you wrote and your files. It is not legal advice and does not assess who is right.</p>
          <ErrorNote>{err}</ErrorNote>
          <div className="flex gap-2"><Button variant="ghost" onClick={back}>Back</Button><Button variant="primary" className="h-11 rounded-xl px-5" loading={busy} onClick={create}>Submit and review my files</Button></div>
        </>}
      </div>
    </div>
  )
}

function IntakeSummary({ i }: { i: Intake }) {
  const s = i.structured
  return (
    <div className="glass space-y-3 rounded-3xl p-5 text-[14.5px]">
      <p>{s.problem}</p>
      <div className="flex flex-wrap gap-1.5">
        <Badge tone="accent">{label(s.legal_domain ?? 'other')}</Badge>
        {i.urgency === 'urgent' && <Badge tone="bad">urgent</Badge>}
        {s.complexity && <Badge>{s.complexity} complexity</Badge>}
      </div>
      {!!s.timeline?.length && <div><p className="font-medium">Dates you mentioned</p><ul className="text-muted">{s.timeline.map((t, k) => <li key={k}>• {t.date_text}</li>)}</ul></div>}
      {!!s.questions_for_client?.length && <div><p className="font-medium">An advocate will likely ask</p><ul className="text-muted">{s.questions_for_client.map((q) => <li key={q}>• {q}</li>)}</ul></div>}
      <p className="text-[12px] text-faint">This summary organises what you wrote. It is not legal advice and does not assess who is right.</p>
    </div>
  )
}

type Tab = 'overview' | 'documents' | 'advocates'

export function IntakeView() {
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as Tab) || 'overview'
  const setTab = (t: Tab) => setParams({ tab: t }, { replace: true })
  const { data: intake, refetch } = useApi<Intake>(['intake', id], `/intakes/${id}`)
  const { data: policy, refetch: refetchPolicy } = useApi<ConnectionPolicyPublic>(['connectionPolicy'], '/connection-policy')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState('')
  const qc = useQueryClient()
  if (!intake || !policy) return <div className="mx-auto max-w-6xl p-6"><Skeleton className="h-48" /></div>
  const run = async (what: string, fn: () => Promise<unknown>) => {
    setBusy(what); setErr('')
    try { await fn(); await refetch(); qc.invalidateQueries({ queryKey: ['intakes'] }) } catch (e) { setErr(errorMessage(e)) } finally { setBusy('') }
  }
  const upload = (files: File[]) => run('upload', async () => {
    const fd = new FormData()
    files.slice(0, 10).forEach((x) => fd.append('files', x))
    await api.post(`/intakes/${intake.id}/documents`, fd)
  })
  const tabs: { id: Tab; label: string; badge?: ReactNode }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'documents', label: 'Documents & review', badge: intake.reviewStale ? <span className="size-2 rounded-full bg-warn" /> : intake.documents.length || undefined },
    { id: 'advocates', label: 'Advocates', badge: intake.connections.length || undefined },
  ]
  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6">
      <Link to="/portal" viewTransition className="inline-flex items-center gap-1 text-sm text-muted hover:text-fg"><ArrowLeft className="size-4" />Home</Link>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="flex-1 font-serif text-3xl sm:text-4xl">{intake.title}</h1>
          <Badge tone="accent">{label(intake.matterType ?? 'other')}</Badge>
          {intake.urgency === 'urgent' && <Badge tone="bad">urgent</Badge>}
        </div>
        <Progress at={stage(intake)} />
      </div>
      <div role="tablist" className="glass sticky top-0 z-20 flex gap-1 overflow-x-auto rounded-2xl p-1">
        {tabs.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
            className={cx('flex items-center gap-2 whitespace-nowrap rounded-xl px-4 py-2 text-[14px] font-medium transition-all', tab === t.id ? 'bg-surface shadow-card' : 'text-muted hover:text-fg')}>
            {t.label}{typeof t.badge === 'number' ? <span className="rounded-full bg-surface-3 px-1.5 text-[11px]">{t.badge}</span> : t.badge}
          </button>
        ))}
      </div>
      <ErrorNote>{err}</ErrorNote>
      <div key={tab} className="animate-[vt-in_.35s_both]">
        {tab === 'overview' && <Overview intake={intake} onSaved={refetch} />}
        {tab === 'documents' && (
          <div className="space-y-6">
            <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
              <Dropzone compact busy={busy === 'upload'} onFiles={upload} />
              <div className="space-y-3">
                <FileList files={intake.documents} onDelete={(docId) => run('delete', () => api.del(`/intakes/${intake.id}/documents/${docId}`))} />
                {!intake.documents.length && <p className="text-[13.5px] text-muted">No files yet. Upload what you have — even photos of papers help.</p>}
                {intake.documents.length > 0 && (
                  <Button variant="primary" className="h-11 w-full rounded-xl" loading={busy === 'review'} onClick={() => run('review', () => api.post(`/intakes/${intake.id}/review`))}>
                    <RefreshCw className="size-4" />{!intake.review ? 'Review my documents' : intake.reviewStale ? 'Update the review (files changed)' : 'Run the review again'}
                  </Button>
                )}
              </div>
            </div>
            {intake.review ? <ReviewPanel r={intake.review} /> : intake.documents.length > 0 && (
              <EmptyState title="Ready when you are">Run the review to see a timeline, conflicting dates and the documents still missing.</EmptyState>
            )}
          </div>
        )}
        {tab === 'advocates' && <Advocates intake={intake} policy={policy} refetch={refetch} refetchPolicy={refetchPolicy} setErr={setErr} />}
      </div>
    </div>
  )
}

function Overview({ intake, onSaved }: { intake: Intake; onSaved: () => void }) {
  const [budget, setBudget] = useState(intake.budgetMax ?? '')
  const [msg, setMsg] = useState('')
  const save = async () => {
    await api.patch(`/intakes/${intake.id}`, { budgetMax: budget === '' ? null : Number(budget) })
    setMsg('Saved'); onSaved()
  }
  return (
    <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
      <IntakeSummary i={intake} />
      <div className="space-y-4">
        <div className="glass rounded-3xl p-5">
          <p className="font-semibold">Your budget</p>
          <p className="text-[13px] text-muted">Used to show which advocates' declared fees fit.</p>
          <div className="mt-3 flex gap-2">
            <Input type="number" min={0} inputMode="numeric" aria-label="Budget in rupees" value={budget} onChange={(e) => { setBudget(e.target.value); setMsg('') }} placeholder="₹ amount" />
            <Button onClick={save}>Save</Button>
          </div>
          {msg && <p className="mt-1 text-[12px] text-ok">{msg}</p>}
        </div>
        {intake.declaredParties.length > 0 && (
          <div className="glass rounded-3xl p-5 text-[14px]"><p className="font-semibold">Other parties you named</p><p className="text-muted">{intake.declaredParties.join(', ')}</p></div>
        )}
        {intake.connections.length > 0 && (
          <div className="glass space-y-2 rounded-3xl p-5">
            <p className="font-semibold">Advocates you contacted</p>
            {intake.connections.map((c) => (
              <div key={c.id} className="flex items-center gap-2 text-sm">
                <span className="flex-1">{c.lawyerName}</span>
                <Badge tone={c.status === 'accepted' ? 'ok' : c.status === 'declined' ? 'bad' : 'info'}>{c.status === 'requested' ? 'waiting for reply' : c.status}</Badge>
                {c.caseId && <Link to={`/portal/matters/${c.caseId}`} viewTransition className="text-accent hover:underline">Open</Link>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function Advocates({ intake, policy, refetch, refetchPolicy, setErr }: {
  intake: Intake; policy: ConnectionPolicyPublic; refetch: () => void; refetchPolicy: () => void; setErr: (s: string) => void
}) {
  const [matches, setMatches] = useState<{ disclaimer: string; matches: Match[]; note: string | null } | null>(null)
  const [confirm, setConfirm] = useState<{ approvalId: string; summary: string; lawyer: string; disclosures: string[] } | null>(null)
  const [read, setRead] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [onlyBudget, setOnlyBudget] = useState(false)
  const qc = useQueryClient()
  const onError = (e: unknown) => {
    setErr(errorMessage(e))
    if (e instanceof ApiError && ['policy_changed', 'connection_feature_disabled'].includes(e.code)) { refetchPolicy(); setMatches(null) }
  }
  const find = async () => {
    setBusy(true); setErr('')
    try { setMatches(await api.post('/matching', { intakeId: intake.id })) } catch (e) { onError(e) } finally { setBusy(false) }
  }
  const findRef = useRef(find)
  findRef.current = find
  useEffect(() => { if (policy.features.matching) void findRef.current() }, [policy.features.matching, intake.budgetMax])
  const request = async (m: Match) => {
    setErr('')
    try {
      const a = await api.post<{ approvalId: string; summary: string }>(`/intakes/${intake.id}/connect`,
        { lawyerId: m.lawyer.id, note, policyVersion: policy.version, disclosureHash: policy.disclosureHash })
      setRead(false); setConfirm({ ...a, lawyer: m.lawyer.name, disclosures: policy.disclosures })
    } catch (e) { onError(e) }
  }
  const decide = async (approve: boolean) => {
    if (!confirm) return
    try { await api.post(`/approvals/${confirm.approvalId}/decision`, { approve }) } catch (e) { onError(e) }
    setConfirm(null); refetch(); qc.invalidateQueries({ queryKey: ['intakes'] })
  }
  if (!policy.features.matching) {
    return (
      <div className="glass rounded-3xl p-6 text-[14px]">
        <p className="text-lg font-semibold">Advocate suggestions are not available yet</p>
        <p className="mt-1 text-muted">{policy.label} Rules for how advocates may be introduced to clients in India are under review, so FormLaw does not suggest or list advocates until that review is complete.</p>
        <p className="mt-2 text-muted">Your summary and files are saved and private. Nothing has been shared with anyone.</p>
      </div>
    )
  }
  const contacted = new Set(intake.connections.map((c) => c.lawyerId))
  const shown = (matches?.matches ?? []).filter((m) => !onlyBudget || m.budgetFit === 'within' || m.budgetFit === 'partly')
  return (
    <div className="space-y-5">
      {policy.source === 'demo' && <p className="rounded-2xl border border-warn/40 bg-warn-soft/40 px-4 py-2.5 text-[13px] text-warn">{policy.label}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <p className="flex-1 text-[13.5px] text-muted">{matches?.disclaimer ?? 'Finding verified advocates for your matter…'}</p>
        {intake.budgetMax && policy.showFees && (
          <label className="flex items-center gap-2 text-[13.5px]"><input type="checkbox" checked={onlyBudget} onChange={(e) => setOnlyBudget(e.target.checked)} />Only within my budget ({inr(intake.budgetMax)})</label>
        )}
        <Button size="sm" loading={busy} onClick={find}><RefreshCw className="size-3.5" />Refresh</Button>
      </div>
      {!intake.budgetMax && policy.showFees && <p className="text-[13px] text-muted">Tip: add your budget in <span className="font-medium">Overview</span> to see which advocates' fees fit.</p>}
      {matches?.note && <p className="text-sm">{matches.note}</p>}
      {busy && !matches && <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{[0, 1, 2].map((k) => <Skeleton key={k} className="h-72 rounded-3xl" />)}</div>}
      {matches && policy.features.clientRequests && (
        <Field label="Message to the advocate (optional)"><Input value={note} onChange={(e) => setNote(e.target.value)} /></Field>
      )}
      <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {shown.map((m, k) => (
          <Reveal as="li" key={m.lawyer.id} delay={k * 70}>
            <AdvocateCard lawyer={m.lawyer} reasons={m.reasons} considerations={m.considerations} fit={m.budgetFit}
              action={policy.features.clientRequests && (
                <Button variant={contacted.has(m.lawyer.id) ? 'secondary' : 'primary'} className="w-full rounded-xl" disabled={contacted.has(m.lawyer.id)} onClick={() => request(m)}>
                  {contacted.has(m.lawyer.id) ? <><Check className="size-4" />Requested</> : <><MessageSquare className="size-4" />Request this lawyer</>}
                </Button>
              )} />
          </Reveal>
        ))}
      </ul>
      {matches && onlyBudget && !shown.length && <EmptyState title="No advocate's declared fees fit this budget">Try a different budget, or show everyone.</EmptyState>}
      <Dialog open={!!confirm} onClose={() => decide(false)} title="Share your matter?">
        <p className="text-[14.5px]">{confirm?.summary}</p>
        <p className="mt-3 text-[13px] font-medium">Before you send, please read:</p>
        <ul className="mt-1 space-y-1 text-[13px] text-muted">{confirm?.disclosures.map((d) => <li key={d}>• {d}</li>)}</ul>
        <label className="mt-3 flex items-start gap-2 text-[13px]">
          <input type="checkbox" className="mt-0.5" checked={read} onChange={(e) => setRead(e.target.checked)} />
          I have read this and agree to share the information described above with {confirm?.lawyer}.
        </label>
        <p className="mt-2 text-[12px] text-faint">Nothing is shared until you confirm. Your agreement is recorded with the text shown above.</p>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => decide(false)}>Cancel</Button><Button variant="primary" disabled={!read} onClick={() => decide(true)}>Confirm & send</Button></div>
      </Dialog>
    </div>
  )
}

interface PortalDetail extends PortalCase {
  updates: { id: string; title: string; body: string; createdAt: string }[]
  documents: { id: string; filename: string; status: string; uploadedAt: string }[]
  messages: { id: string; senderName: string; senderRole: string; body: string; createdAt: string }[]
}

export function MatterView() {
  const { id } = useParams()
  const { data, refetch } = useApi<PortalDetail>(['portalCase', id], `/portal/cases/${id}`, { refetchInterval: 20_000 })
  const { user } = useAuth()
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  if (!data) return <div className="mx-auto max-w-6xl p-6"><Skeleton className="h-48" /></div>
  const send = async () => {
    if (!msg.trim()) return
    try { await api.post(`/portal/cases/${id}/messages`, { body: msg }); setMsg(''); refetch() } catch (e) { setErr(errorMessage(e)) }
  }
  const upload = async (files: File[]) => {
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f))
    setBusy(true)
    try { await api.post(`/portal/cases/${id}/documents`, fd); refetch() } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
  }
  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6">
      <Link to="/portal" viewTransition className="inline-flex items-center gap-1 text-sm text-muted hover:text-fg"><ArrowLeft className="size-4" />Home</Link>
      <div>
        <h1 className="font-serif text-3xl sm:text-4xl">{data.title}</h1>
        <p className="mt-1 text-sm text-muted">{data.reference} · {label(data.matterType)} · <Badge tone={data.status === 'active' ? 'ok' : 'neutral'}>{data.status}</Badge> · {data.lawyers.join(', ')}</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-6">
          <PanelTitle icon={<Bell className="size-4" />} title="Updates from your advocate" />
          {!data.updates.length ? <p className="text-sm text-muted">No updates yet.</p> : (
            <ul className="space-y-3">{data.updates.map((u) => (
              <li key={u.id} className="glass rounded-3xl p-5"><p className="font-semibold">{u.title}</p><p className="mt-1 whitespace-pre-line text-[14px] text-muted">{u.body}</p><p className="mt-2 text-[12px] text-faint">Reviewed and sent by your advocate · {timeAgo(u.createdAt)}</p></li>
            ))}</ul>
          )}
          <PanelTitle icon={<MessageSquare className="size-4" />} title="Messages" />
          <div className="glass rounded-3xl p-4">
            <ul className="max-h-96 space-y-2 overflow-y-auto">
              {!data.messages.length && <li className="text-sm text-muted">No messages yet. Say hello to your advocate.</li>}
              {data.messages.map((m) => (
                <li key={m.id} className={cx('max-w-[85%] rounded-2xl px-3.5 py-2 text-[14px]', m.senderName === user?.name ? 'ml-auto bg-accent-soft' : 'bg-surface-2')}>
                  <p className="text-[11px] text-faint">{m.senderName} · {timeAgo(m.createdAt)}</p>{m.body}
                </li>
              ))}
            </ul>
            <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); send() }}>
              <Input value={msg} onChange={(e) => setMsg(e.target.value)} placeholder="Write to your advocate" aria-label="Message" /><Button type="submit" variant="primary" aria-label="Send"><Send className="size-4" /></Button>
            </form>
          </div>
        </div>
        <div className="space-y-4">
          <PanelTitle icon={<FolderOpen className="size-4" />} title="Your documents" />
          <Dropzone compact busy={busy} onFiles={upload} />
          <FileList files={data.documents.map((d) => ({ id: d.id, filename: d.filename, size: 0 }))} />
        </div>
      </div>
      <ErrorNote>{err}</ErrorNote>
    </div>
  )
}

function PanelTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return <h2 className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-wider text-muted">{icon}{title}</h2>
}
