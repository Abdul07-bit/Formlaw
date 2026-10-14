import { ArrowRight, BadgeCheck, Briefcase, CheckCircle2, ChevronDown, FileSearch, GitBranch, Scale, ShieldCheck, Sparkles, Upload, Users } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Brand } from '../components/layout/AppShell'
import { CountUp, Hero3D, Reveal, Tilt } from '../components/motion'
import { cx } from '../lib/util'
import { Button, ErrorNote, Field, Input } from '../components/ui'
import { LegalChat } from '../components/workbench/LegalChat'
import { errorMessage } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useApi } from '../lib/queries'
import type { User } from '../lib/types'

const HOME: Record<User['role'], [string, string]> = {
  client: ['/portal', 'Open my matters'], admin: ['/admin', 'Open admin'], compliance: ['/compliance', 'Open compliance review'], lawyer: ['/', 'Open workbench'],
}
export const homeFor = (u: User) => HOME[u.role][0]
const homeLabel = (u: User) => HOME[u.role][1]

function Shell({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  return (
    <div className="flex min-h-full flex-col">
      <header className="glass sticky top-0 z-40 !border-x-0 !border-t-0">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-2 px-5 py-3">
        <Brand />
        <nav className="flex items-center gap-1 text-sm sm:gap-2">
          <a href="/#clients" className="hidden rounded-lg px-3 py-1.5 text-muted hover:text-fg md:inline">For clients</a>
          <a href="/#advocates" className="hidden rounded-lg px-3 py-1.5 text-muted hover:text-fg md:inline">For advocates</a>
          <Link to="/#ask" className="hidden rounded-lg px-3 py-1.5 text-muted hover:text-fg sm:inline">Ask the law</Link>
          {user ? (
            <Link to={homeFor(user)} className="inline-flex items-center gap-1 rounded-lg bg-accent px-3 py-1.5 font-medium text-on-accent">{homeLabel(user)}<ArrowRight className="size-3.5" /></Link>
          ) : (
            <>
              <Link to="/login" className="rounded-lg px-3 py-1.5 text-muted hover:text-fg">Sign in</Link>
              <Link to="/register" className="rounded-lg bg-accent px-3 py-1.5 font-medium text-on-accent">Get started</Link>
            </>
          )}
        </nav>
        </div>
      </header>
      <div className="flex-1">{children}</div>
      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-5 gap-y-2 px-5 py-6 text-[13px] text-muted">
          <Brand />
          <Link to="/" className="hover:text-fg">Home</Link>
          <Link to="/#ask" className="hover:text-fg">Ask the law</Link>
          <Link to="/login" className="hover:text-fg">Sign in</Link>
          <Link to="/register" className="hover:text-fg">For lawyers</Link>
          <Link to="/register?role=client" className="hover:text-fg">Find a lawyer</Link>
          <span className="w-full text-[12px] text-faint sm:ml-auto sm:w-auto">Not legal advice · no outcome predictions</span>
        </div>
      </footer>
    </div>
  )
}

/** After sign-in, return to the page that asked for it when it belongs to this role; otherwise the role's home. */
function destination(u: User, from: unknown): string {
  if (typeof from !== 'string' || !from.startsWith('/') || from.startsWith('//')) return homeFor(u)
  const area = from.startsWith('/portal') ? 'client' : from.startsWith('/admin') ? 'admin' : from.startsWith('/compliance') ? 'compliance' : 'lawyer'
  return area === u.role ? from : homeFor(u)
}

/** Signed-in users go on to their destination instead of seeing the sign-in and registration forms again. */
function SignedOutOnly({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth()
  const { state } = useLocation()
  if (ready && user) return <Navigate to={destination(user, (state as { from?: string } | null)?.from)} replace />
  return <>{children}</>
}

const ASK_SUGGESTIONS = [
  'Can prolonged custody and delay in trial justify bail?',
  'When is a dying declaration reliable without corroboration?',
  'What are the twin conditions for bail under the PMLA?',
]

function AskTheLaw() {
  const { data } = useApi<{ judgments: number; coverage: string }>(['public-corpus'], '/public/corpus')
  const scope = data?.judgments ? `${data.judgments} verified Supreme Court judgments${data.coverage ? ` (${data.coverage})` : ''}` : 'verified Supreme Court judgments'
  return (
    <section id="ask" className="mx-auto max-w-3xl scroll-mt-24 px-5 py-20">
      <Reveal className="mb-8 text-center">
        <p className="text-[13px] font-medium uppercase tracking-widest text-gold">Free · no account</p>
        <h2 className="mt-2 font-serif text-3xl sm:text-4xl">Ask the law</h2>
      </Reveal>
      <Reveal delay={120} className="glass rounded-3xl p-4 shadow-card sm:p-6">
        <div className="mb-4 flex items-start gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent"><Scale className="size-5" /></span>
          <div>
            <h2 className="font-serif text-xl">Ask the law</h2>
            <p className="text-[13.5px] text-muted">A research assistant for lawyers that answers only from {scope}. Every answer is a cited passage you can check. No account needed.</p>
          </div>
        </div>
        <LegalChat endpoint="/public/ask" suggestions={ASK_SUGGESTIONS} placeholder="Ask a legal question, e.g. when does delay in trial justify bail?" />
        <p className="mt-3 text-[12px] text-faint">
          Public questions see only the published legal corpus, never case files. For model-phrased answers, case documents and drafting,{' '}
          <Link to="/register" className="text-accent hover:underline">open the lawyer workbench</Link>.
        </p>
      </Reveal>
    </section>
  )
}

const CLIENT_STEPS = [
  { icon: <Upload className="size-6" />, t: 'Upload your case files', d: 'FIR, notices, agreements, letters, photos. Checked for safety and encrypted. Nobody sees them unless you choose.' },
  { icon: <FileSearch className="size-6" />, t: 'See what your files say', d: 'A dated timeline with the page each date comes from, conflicting dates side by side, and the documents still missing.' },
  { icon: <Users className="size-6" />, t: 'Meet verified advocates', d: 'Where introductions are available: advocates checked against the Bar Council roll, with practice areas, languages and declared fees beside your budget. You decide.' },
]
const WORKBENCH = [
  { id: 'review', t: 'Case review', d: 'Parties, facts, allegations and issues — every one quoted from a page of the record and verified before you see it.',
    lines: ['Retrieve evidence across 3 documents', 'Extract dated events and parties', 'Verify each statement against its quote'] },
  { id: 'contradictions', t: 'Contradictions', d: 'Conflicting dates, amounts and statements, with both sources cited. FormLaw never picks a side.',
    lines: ['FIR p.2 — arrested on 12 March 2026', 'Remand report p.1 — arrested on 14 March 2026', 'Arrest memo referenced but not on file'] },
  { id: 'research', t: 'Research', d: 'Answers only from approved, licence-checked judgments — with the passage, court, date and source link.',
    lines: ['Search the verified corpus', 'Re-read and hash-check each authority', 'Unknown citations are refused, never invented'] },
  { id: 'drafting', t: 'Drafting', d: 'Drafts built from verified facts and authorities, with placeholders where evidence is missing. You approve before anything is shared.',
    lines: ['Facts → authorities → inferences', '[PLACEHOLDER] where proof is missing', 'Human approval before sharing'] },
] as const

function Showcase() {
  const [tab, setTab] = useState<(typeof WORKBENCH)[number]['id']>('contradictions')
  const cur = WORKBENCH.find((w) => w.id === tab)!
  return (
    <div className="grid items-center gap-8 lg:grid-cols-[1fr_1.2fr]">
      <div role="tablist" aria-label="Workbench capabilities" className="space-y-2">
        {WORKBENCH.map((w) => (
          <button key={w.id} role="tab" aria-selected={tab === w.id} onClick={() => setTab(w.id)}
            className={cx('w-full rounded-2xl border p-4 text-left transition-all duration-300', tab === w.id ? 'glass border-accent/50 shadow-card' : 'border-transparent opacity-70 hover:opacity-100')}>
            <p className="font-semibold">{w.t}</p>
            {tab === w.id && <p className="mt-1 text-sm text-muted">{w.d}</p>}
          </button>
        ))}
      </div>
      <Tilt className="glass rounded-3xl p-6 shadow-card" max={6}>
        <div key={tab} className="animate-[vt-in_.45s_both]">
          <div className="mb-4 flex items-center gap-2 text-[12px] text-faint"><span className="size-2.5 rounded-full bg-bad/70" /><span className="size-2.5 rounded-full bg-warn/70" /><span className="size-2.5 rounded-full bg-ok/70" /><span className="ml-2">State v. Arjun Kumar · illustration with synthetic data</span></div>
          <p className="font-serif text-xl">{cur.t}</p>
          <ul className="mt-4 space-y-2">
            {cur.lines.map((l, i) => (
              <li key={l} className="flex items-center gap-3 rounded-xl bg-surface-2/70 px-3 py-2.5 text-[14px]" style={{ animation: `vt-in .5s ${i * 120}ms both` }}>
                <CheckCircle2 className="size-4 shrink-0 text-ok" />{l}
              </li>
            ))}
          </ul>
        </div>
      </Tilt>
    </div>
  )
}

export function Landing() {
  const { demo } = useAuth()
  const nav = useNavigate()
  const { hash } = useLocation()
  const [err, setErr] = useState('')
  const { data: corpus } = useApi<{ judgments: number }>(['public-corpus'], '/public/corpus')
  useEffect(() => { if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth' }) }, [hash])
  const tryDemo = async (p: 'lawyer' | 'client') => {
    try { nav(homeFor(await demo(p)), { viewTransition: true }) } catch (e) { setErr(errorMessage(e)) }
  }
  const marquee = ['Evidence-cited answers', 'Contradiction detection', 'Missing-record checks', 'Bar Council roll verification', 'Conflict checks before disclosure',
    'Consent recorded verbatim', 'Human approval for every share', 'Encrypted documents', 'No ratings, no paid ranking']
  return (
    <Shell>
      {/* 1 · Hero — full screen, 3D */}
      <section className="relative isolate flex min-h-[calc(100dvh-57px)] items-center overflow-hidden">
        <Hero3D />
        <div className="relative z-10 mx-auto w-full max-w-7xl px-5 py-16">
          <div className="max-w-2xl">
            <Reveal><p className="inline-flex items-center gap-2 rounded-full border border-line bg-surface/60 px-3 py-1 text-[12.5px] text-muted backdrop-blur">
              <Sparkles className="size-3.5 text-gold" />Legal help, organised — for clients and advocates in India</p></Reveal>
            <Reveal delay={80}><h1 className="mt-5 font-serif text-5xl leading-[1.05] tracking-tight sm:text-6xl lg:text-7xl">
              <span className="text-gradient">Your case,</span><br />clearly understood.</h1></Reveal>
            <Reveal delay={160}><p className="mt-6 max-w-xl text-lg text-muted sm:text-xl">
              Upload your case files and see what they say. Find a verified advocate who fits your matter and your budget. Advocates get a workspace where every answer cites its source.</p></Reveal>
            <Reveal delay={240} className="mt-9 flex flex-wrap gap-3">
              <Button variant="primary" className="h-12 rounded-xl px-6 text-base" onClick={() => tryDemo('client')}>I need legal help <ArrowRight className="size-4" /></Button>
              <Button className="h-12 rounded-xl px-6 text-base" onClick={() => tryDemo('lawyer')}><Briefcase className="size-4" />I'm an advocate</Button>
            </Reveal>
            <ErrorNote>{err}</ErrorNote>
            <Reveal delay={320}><p className="mt-4 text-[12.5px] text-faint">Live demo with synthetic data · no sign-up needed</p></Reveal>
          </div>
        </div>
        <a href="#clients" aria-label="Scroll to learn more" className="float-y absolute bottom-8 left-1/2 z-10 -translate-x-1/2 text-muted hover:text-fg"><ChevronDown className="size-6" /></a>
      </section>

      {/* 2 · Capability strip */}
      <div className="overflow-hidden border-y border-line bg-surface/50 py-4" aria-hidden>
        <div className="marquee flex w-max gap-10 whitespace-nowrap text-[14px] text-muted">
          {[...marquee, ...marquee].map((m, i) => <span key={i} className="flex items-center gap-10">{m}<span className="text-gold">✦</span></span>)}
        </div>
      </div>

      {/* 3 · For clients */}
      <section id="clients" className="mx-auto flex min-h-dvh max-w-7xl scroll-mt-16 flex-col justify-center px-5 py-24">
        <Reveal className="max-w-2xl">
          <p className="text-[13px] font-medium uppercase tracking-widest text-gold">For clients</p>
          <h2 className="mt-3 font-serif text-4xl sm:text-5xl">From a pile of papers to a clear picture.</h2>
          <p className="mt-4 text-lg text-muted">Three steps, at your own pace. Nothing is shared with anyone until you say so.</p>
        </Reveal>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {CLIENT_STEPS.map((s, i) => (
            <Reveal key={s.t} delay={i * 120}>
              <Tilt className="glass h-full rounded-3xl p-7 shadow-card">
                <div className="flex items-center justify-between"><span className="flex size-12 items-center justify-center rounded-2xl bg-accent-soft text-accent">{s.icon}</span><span className="font-serif text-4xl text-faint/60">0{i + 1}</span></div>
                <p className="mt-6 text-xl font-semibold">{s.t}</p>
                <p className="mt-2 text-muted">{s.d}</p>
              </Tilt>
            </Reveal>
          ))}
        </div>
        <Reveal delay={360} className="mt-10"><Button variant="primary" className="h-11 rounded-xl px-5" onClick={() => tryDemo('client')}>Open the client portal <ArrowRight className="size-4" /></Button></Reveal>
      </section>

      {/* 4 · Proof in numbers (only what is true and measured) */}
      <section className="border-y border-line bg-surface/40">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-16 text-center sm:grid-cols-3">
          {[[corpus?.judgments ?? 0, '', 'Supreme Court judgments in the verified corpus'], [12, '', 'specialist agents, each with its own permissions'], [0, '', 'fabricated citations in our evaluation set']].map(([n, s, l]) => (
            <Reveal key={l as string}><p className="font-serif text-5xl text-gradient sm:text-6xl"><CountUp to={n as number} suffix={s as string} /></p><p className="mt-2 text-muted">{l}</p></Reveal>
          ))}
        </div>
      </section>

      {/* 5 · For advocates */}
      <section id="advocates" className="mx-auto flex min-h-dvh max-w-7xl scroll-mt-16 flex-col justify-center px-5 py-24">
        <Reveal className="mb-12 max-w-2xl">
          <p className="text-[13px] font-medium uppercase tracking-widest text-gold">For advocates</p>
          <h2 className="mt-3 font-serif text-4xl sm:text-5xl">A workbench that shows its working.</h2>
          <p className="mt-4 text-lg text-muted">Ask in plain language. Watch the plan. Click any sentence to see the page it came from.</p>
        </Reveal>
        <Reveal delay={120}><Showcase /></Reveal>
      </section>

      <AskTheLaw />

      {/* 6 · Trust + closing call to action */}
      <section className="relative isolate overflow-hidden">
        <div className="aurora absolute inset-0 -z-10 opacity-70" />
        <div className="mx-auto grid max-w-7xl gap-5 px-5 py-24 md:grid-cols-3">
          {[[<ShieldCheck key="a" className="size-5" />, 'You stay in control', 'Nothing is shared, sent or deleted without your explicit approval. Every action is audited.'],
            [<BadgeCheck key="b" className="size-5" />, 'Verified, not ranked', 'Advocates are checked against the Bar Council roll. No ratings, win rates or paid placement — ever.'],
            [<GitBranch key="c" className="size-5" />, 'Evidence over guesswork', 'Unsupported claims are labelled, never hidden. Conflicting records are shown side by side.']].map(([icon, t, d], i) => (
            <Reveal key={t as string} delay={i * 100} className="glass rounded-3xl p-6"><span className="text-accent">{icon}</span><p className="mt-3 font-semibold">{t}</p><p className="mt-1 text-sm text-muted">{d}</p></Reveal>
          ))}
        </div>
        <Reveal className="mx-auto max-w-3xl px-5 pb-24 text-center">
          <h2 className="font-serif text-4xl sm:text-5xl">Start with what you have.</h2>
          <p className="mt-4 text-lg text-muted">Describe your problem in your own words. FormLaw organises the rest.</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Button variant="primary" className="h-12 rounded-xl px-6 text-base" onClick={() => tryDemo('client')}>Get legal help <ArrowRight className="size-4" /></Button>
            <Link to="/register" viewTransition><Button className="h-12 rounded-xl px-6 text-base">Create an account</Button></Link>
          </div>
          <p className="mt-8 text-[12px] text-faint">FormLaw is a technology platform, not a law firm. It does not provide legal advice, rank advocates or predict case outcomes.</p>
        </Reveal>
      </section>
    </Shell>
  )
}

export function Login() {
  const { login, demo } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const from = (useLocation().state as { from?: string } | null)?.from
  const go = async (fn: () => Promise<User>) => {
    setBusy(true); setErr('')
    try { nav(destination(await fn(), from), { replace: true }) } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
  }
  return (
    <SignedOutOnly><Shell>
      <div className="mx-auto max-w-sm px-5 pt-16 pb-12">
        <h1 className="font-serif text-2xl">Sign in</h1>
        <form className="mt-6 space-y-3" onSubmit={(e) => { e.preventDefault(); go(() => login(email, password)) }}>
          <Field label="Email"><Input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          <Field label="Password"><Input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
          <ErrorNote>{err}</ErrorNote>
          <Button type="submit" variant="primary" className="w-full" loading={busy}>Sign in</Button>
        </form>
        <div className="mt-8 border-t border-line pt-4">
          <p className="text-[12px] text-muted">Demo personas (synthetic data)</p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {(['lawyer', 'client', 'admin', 'compliance'] as const).map((p) => <Button key={p} size="sm" onClick={() => go(() => demo(p))}>{p}</Button>)}
          </div>
        </div>
        <p className="mt-6 text-center text-sm text-muted">New here? <Link to="/register" className="text-accent hover:underline">Create an account</Link></p>
      </div>
    </Shell></SignedOutOnly>
  )
}

export function Register() {
  const { register } = useAuth()
  const nav = useNavigate()
  const { search } = useLocation()
  const [role, setRole] = useState<'lawyer' | 'client'>(new URLSearchParams(search).get('role') === 'client' ? 'client' : 'lawyer')
  const [f, setF] = useState({ name: '', email: '', password: '', city: '', firmName: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true); setErr('')
    try {
      const u = await register({ role, name: f.name, email: f.email, password: f.password, city: f.city || undefined, ...(role === 'lawyer' && f.firmName ? { firmName: f.firmName } : {}) })
      nav(u.role === 'lawyer' ? '/profile' : '/portal/new')
    } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
  }
  return (
    <SignedOutOnly><Shell>
      <div className="mx-auto max-w-sm px-5 pt-12 pb-12">
        <h1 className="font-serif text-2xl">Create your account</h1>
        <div className="mt-5 grid grid-cols-2 gap-2">
          {([['lawyer', 'I am a lawyer', 'Case workspace & AI agents'], ['client', 'I need a lawyer', 'Submit a matter, get matched']] as const).map(([r, t, d]) => (
            <button key={r} type="button" onClick={() => setRole(r)} className={`rounded-xl border p-3 text-left ${role === r ? 'border-accent bg-accent-soft' : 'border-line bg-surface'}`}>
              <p className="text-sm font-medium">{t}</p><p className="text-[12px] text-muted">{d}</p>
            </button>
          ))}
        </div>
        <form className="mt-5 space-y-3" onSubmit={(e) => { e.preventDefault(); submit() }}>
          <Field label="Full name"><Input required minLength={2} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
          {role === 'lawyer' && <Field label="Firm or chambers" hint="Leave blank for a solo practice"><Input value={f.firmName} onChange={(e) => setF({ ...f, firmName: e.target.value })} /></Field>}
          <Field label="Email"><Input type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
          <Field label="Password" hint="At least 10 characters"><Input type="password" required minLength={10} autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
          <Field label="City"><Input value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} /></Field>
          <ErrorNote>{err}</ErrorNote>
          <Button type="submit" variant="primary" className="w-full" loading={busy}>Create account</Button>
        </form>
        <p className="mt-6 text-center text-sm text-muted">Have an account? <Link to="/login" className="text-accent hover:underline">Sign in</Link></p>
      </div>
    </Shell></SignedOutOnly>
  )
}
