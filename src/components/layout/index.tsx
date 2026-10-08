import { AnimatePresence, motion } from 'framer-motion'
import {
  Bell, BriefcaseBusiness, FilePlus2, Gavel, LayoutDashboard, LogOut, Menu, MessagesSquare, Network,
  ScanFace, Scale, Search, ShieldCheck, Users, X, Database, Activity,
} from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useDB, useSession } from '../../hooks/useStore'
import { demoLogin, signOut } from '../../services/api'
import { Avatar, Button, cx } from '../ui'

export function Logo({ light }: { light?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2.5" aria-label="FormLaw home">
      <span className="grid size-9 place-items-center rounded-xl bg-sky-500 text-white shadow-[var(--shadow-glow)]"><Scale className="size-5" strokeWidth={2.6} /></span>
      <span className={cx('text-xl font-extrabold tracking-tight', light ? 'text-white' : 'text-ink')}>Form<span className="text-sky-500">Law</span></span>
    </Link>
  )
}

export function PageTransition({ children }: { children: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}>
      {children}
    </motion.div>
  )
}

export function PublicNav() {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)
  const user = useSession()
  const loc = useLocation()
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 12)
    on(); window.addEventListener('scroll', on, { passive: true })
    return () => window.removeEventListener('scroll', on)
  }, [])
  useEffect(() => { setOpen(false) }, [loc.pathname])
  const links = [
    { to: '/lawyers', label: 'Find a Lawyer' },
    { to: '/how-it-works', label: 'How it works' },
    { to: '/get-started?role=lawyer', label: 'For Lawyers & Judges' },
  ]
  return (
    <header className={cx('fixed inset-x-0 top-0 z-40 transition-all duration-300', scrolled ? 'py-2' : 'py-4')}>
      <div className={cx('mx-auto flex max-w-7xl items-center justify-between rounded-3xl px-4 py-2.5 transition-all duration-300 md:px-6', scrolled ? 'glass mx-3 shadow-[var(--shadow-soft)] md:mx-auto' : '')}>
        <Logo />
        <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} className={({ isActive }) => cx('rounded-xl px-4 py-2 text-[15px] font-bold transition', isActive ? 'bg-sky-100 text-sky-700' : 'text-ink-soft hover:text-ink hover:bg-white/70')}>{l.label}</NavLink>
          ))}
        </nav>
        <div className="hidden items-center gap-2 md:flex">
          {user ? <Button to="/app" size="sm">Open dashboard</Button> : <>
            <Button to="/get-started" variant="ghost" size="sm">Sign in</Button>
            <Button to="/get-started?role=client" size="sm">Get legal help</Button>
          </>}
        </div>
        <button className="rounded-xl p-2 md:hidden" onClick={() => setOpen(!open)} aria-label="Toggle menu" aria-expanded={open}>{open ? <X /> : <Menu />}</button>
      </div>
      <AnimatePresence>
        {open && (
          <motion.nav initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="card mx-3 mt-2 flex flex-col gap-1 p-3 md:hidden">
            {links.map((l) => <Link key={l.to} to={l.to} className="rounded-xl px-4 py-3 font-bold hover:bg-sky-50">{l.label}</Link>)}
            <Button to={user ? '/app' : '/get-started?role=client'} className="mt-2">{user ? 'Open dashboard' : 'Get legal help'}</Button>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  )
}

export function Footer() {
  return (
    <footer className="mt-24 bg-ink text-sky-100">
      <div className="tricolor-bar h-1.5" />
      <div className="mx-auto grid max-w-7xl gap-10 px-6 py-14 md:grid-cols-4">
        <div className="md:col-span-2">
          <Logo light />
          <p className="mt-4 max-w-sm text-sm text-sky-200/80">India’s evidence-grounded legal network. AI prepares the case; KYC-verified advocates and judges resolve it.</p>
          <p className="mt-6 text-xs text-sky-200/60">FormLaw is a technology platform, not a law firm, and does not provide legal advice. Advocates on FormLaw are independently enrolled with their State Bar Councils.</p>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-extrabold uppercase tracking-wider text-white">Clients</h4>
          <ul className="space-y-2 text-sm font-semibold">
            <li><Link to="/get-started?role=client" className="hover:text-white">Upload a case</Link></li>
            <li><Link to="/lawyers" className="hover:text-white">Find a lawyer</Link></li>
            <li><Link to="/how-it-works" className="hover:text-white">How FormLaw works</Link></li>
          </ul>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-extrabold uppercase tracking-wider text-white">Professionals</h4>
          <ul className="space-y-2 text-sm font-semibold">
            <li><Link to="/get-started?role=lawyer" className="hover:text-white">Join as advocate</Link></li>
            <li><Link to="/get-started?role=judge" className="hover:text-white">Join as retd. judge / arbitrator</Link></li>
            <li><Link to="/how-it-works#security" className="hover:text-white">Security & KYC</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10 py-6 text-center text-xs font-bold text-sky-200/70">AI can reason. Evidence decides. · Prototype build — data is synthetic</div>
    </footer>
  )
}

export function PublicLayout() {
  const loc = useLocation()
  useEffect(() => { window.scrollTo({ top: 0 }) }, [loc.pathname])
  return (
    <div className="min-h-screen">
      <PublicNav />
      <AnimatePresence mode="wait">
        <motion.main key={loc.pathname} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
          <Outlet />
        </motion.main>
      </AnimatePresence>
      <Footer />
    </div>
  )
}

// ── Authenticated app shell ─────────────────────────────────────────────────
interface NavItem { to: string; label: string; icon: ReactNode; end?: boolean }

export function AppShell() {
  const user = useSession()
  const nav = useNavigate()
  const loc = useLocation()
  const [open, setOpen] = useState(false)
  const conversations = useDB((d) => d.conversations)
  const lawyers = useDB((d) => d.lawyers)
  useEffect(() => { if (!user) nav('/get-started', { replace: true }) }, [user, nav])
  useEffect(() => { setOpen(false) }, [loc.pathname])

  const pendingKyc = useMemo(() => lawyers.filter((l) => l.kyc === 'pending').length, [lawyers])
  const unread = useMemo(() => {
    if (!user) return 0
    if (user.role === 'client') return conversations.filter((c) => c.clientId === user.id && c.status === 'accepted').length
    return conversations.filter((c) => c.lawyerId === user.lawyerId && c.status === 'requested').length
  }, [conversations, user])

  if (!user) return null
  const items: NavItem[] =
    user.role === 'client'
      ? [
          { to: '/app/client', label: 'My Cases', icon: <LayoutDashboard className="size-5" /> },
          { to: '/app/cases/new', label: 'New Case', icon: <FilePlus2 className="size-5" /> },
          { to: '/app/lawyers', label: 'Find Lawyers', icon: <Users className="size-5" /> },
          { to: '/app/messages', label: 'Messages', icon: <MessagesSquare className="size-5" /> },
          { to: '/app/security', label: 'Security', icon: <ShieldCheck className="size-5" /> },
        ]
      : user.role === 'admin'
        ? [
            { to: '/app/admin', label: 'Verification Desk', icon: <ScanFace className="size-5" />, end: true },
            { to: '/app/admin/cases', label: 'Case Database', icon: <Database className="size-5" /> },
            { to: '/app/security', label: 'Security Center', icon: <ShieldCheck className="size-5" /> },
            { to: '/app/admin/ops', label: 'Observability', icon: <Activity className="size-5" /> },
          ]
        : [
            { to: '/app/lawyer', label: 'Dashboard', icon: <LayoutDashboard className="size-5" />, end: true },
            { to: '/app/lawyer/kyc', label: 'KYC Verification', icon: <ScanFace className="size-5" /> },
            { to: '/app/lawyer/cases', label: 'Completed Cases', icon: <BriefcaseBusiness className="size-5" /> },
            { to: '/app/messages', label: 'Client Requests', icon: <MessagesSquare className="size-5" /> },
            { to: '/app/security', label: 'Security', icon: <ShieldCheck className="size-5" /> },
          ]

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="px-5 pt-6 pb-8"><Logo /></div>
      <p className="px-6 pb-2 text-[11px] font-extrabold uppercase tracking-[0.16em] text-slate-400">{user.role === 'client' ? 'Client' : user.role === 'admin' ? 'Admin' : user.role === 'judge' ? 'Judge' : 'Advocate'} workspace</p>
      <nav className="flex flex-col gap-1 px-3" aria-label="App">
        {items.map((i) => (
          <NavLink key={i.to} to={i.to} end={i.end} className={({ isActive }) => cx('group relative flex items-center gap-3 rounded-2xl px-4 py-3 text-[15px] font-bold transition', isActive ? 'bg-sky-500 text-white shadow-[var(--shadow-glow)]' : 'text-ink-soft hover:bg-sky-50 hover:text-ink')}>
            {i.icon}{i.label}
            {i.to === '/app/messages' && unread > 0 && <span className="ml-auto rounded-full bg-saffron px-2 text-xs text-white">{unread}</span>}
            {i.to === '/app/admin' && pendingKyc > 0 && <span className="ml-auto rounded-full bg-saffron px-2 text-xs text-white">{pendingKyc}</span>}
          </NavLink>
        ))}
      </nav>
      <div className="mx-3 mt-6 border-t border-sky-100 pt-4">
        <p className="px-3 pb-2 text-[11px] font-extrabold uppercase tracking-[0.16em] text-slate-400">Platform</p>
        <NavLink to="/how-it-works" className="flex items-center gap-3 rounded-2xl px-4 py-2.5 text-sm font-bold text-ink-soft hover:bg-sky-50"><Network className="size-4" />Agent architecture</NavLink>
      </div>
      <div className="mt-auto p-4">
        <div className="rounded-2xl bg-gradient-to-br from-sky-500 to-sky-600 p-4 text-white">
          <p className="text-xs font-extrabold uppercase tracking-wider opacity-80">Demo personas</p>
          <div className="mt-2 grid grid-cols-3 gap-1.5">
            {(['client', 'lawyer', 'admin'] as const).map((r) => (
              <button key={r} onClick={() => { const u = demoLogin(r); nav(u.role === 'client' ? '/app/client' : u.role === 'admin' ? '/app/admin' : '/app/lawyer') }}
                className={cx('rounded-lg px-1 py-1.5 text-xs font-extrabold capitalize transition', (user.role === r || (r === 'lawyer' && user.role === 'judge')) ? 'bg-white text-sky-600' : 'bg-white/15 hover:bg-white/25')}>{r}</button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-sky-25">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 border-r border-sky-100 bg-white lg:block">{sidebar}</aside>
      <AnimatePresence>
        {open && (
          <motion.div className="fixed inset-0 z-50 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-ink/40" onClick={() => setOpen(false)} />
            <motion.aside className="absolute inset-y-0 left-0 w-72 bg-white" initial={{ x: -300 }} animate={{ x: 0 }} exit={{ x: -300 }} transition={{ type: 'spring', damping: 30, stiffness: 300 }}>{sidebar}</motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="lg:pl-72">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-sky-100 bg-white/80 px-4 backdrop-blur-xl md:px-8">
          <button className="rounded-xl p-2 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu /></button>
          <div className="relative hidden max-w-md flex-1 md:block">
            <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
            <input aria-label="Search" placeholder="Search cases, evidence, advocates…" className="h-10 w-full rounded-xl border border-sky-100 bg-sky-25 pl-10 pr-3 text-sm font-semibold outline-none focus:border-sky-400" />
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-extrabold text-emerald-700 sm:flex"><ShieldCheck className="size-3.5" />Protected</span>
            <button className="relative rounded-xl p-2 text-ink-soft hover:bg-sky-50" aria-label="Notifications">
              <Bell className="size-5" />{unread + pendingKyc > 0 && <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-saffron" />}
            </button>
            <div className="flex items-center gap-2.5 rounded-2xl py-1 pl-1 pr-3">
              <Avatar initials={user.name.split(' ').map((p) => p[0]).join('').slice(0, 2)} size={36} />
              <div className="hidden leading-tight sm:block"><div className="text-sm font-extrabold">{user.name}</div><div className="text-xs font-semibold capitalize text-ink-soft">{user.role}</div></div>
            </div>
            <button onClick={() => { signOut(); nav('/') }} className="rounded-xl p-2 text-ink-soft hover:bg-rose-50 hover:text-rose-600" aria-label="Sign out"><LogOut className="size-5" /></button>
          </div>
        </header>
        <AnimatePresence mode="wait">
          <motion.main key={loc.pathname} className="mx-auto max-w-7xl px-4 py-8 md:px-8" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}>
            <Outlet />
          </motion.main>
        </AnimatePresence>
      </div>
    </div>
  )
}

export const GavelIcon = Gavel
