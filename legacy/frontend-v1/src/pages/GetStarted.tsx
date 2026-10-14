import { motion } from 'framer-motion'
import { Gavel, Scale, ShieldCheck, User } from 'lucide-react'
import { useState, type FormEvent , type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ScalesArt } from '../components/art'
import { Button, cx, Field, inputCls } from '../components/ui'
import { errorMessage } from '../services/api/client'
import { demoLogin, login, register } from '../services/auth'
import type { Role } from '../types'

const ROLES: { id: Role; title: string; desc: string; icon: ReactNode }[] = [
  { id: 'client', title: 'I need legal help', desc: 'Upload a case, get an evidence-backed review, connect with counsel.', icon: <User className="size-6" /> },
  { id: 'lawyer', title: 'Advocate', desc: 'Verify with KYC, publish completed cases, receive prepared briefs.', icon: <Scale className="size-6" /> },
  { id: 'judge', title: 'Retd. Judge / Arbitrator', desc: 'Offer arbitration, mediation and legal opinions.', icon: <Gavel className="size-6" /> },
]

export default function GetStarted() {
  const [params] = useSearchParams()
  const nav = useNavigate()
  const initial = (params.get('role') as Role) || 'client'
  const [role, setRole] = useState<Role>(['client', 'lawyer', 'judge'].includes(initial) ? initial : 'client')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [city, setCity] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'register' | 'login'>(params.get('mode') === 'login' ? 'login' : 'register')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const home = (r: Role) => (r === 'client' ? '/app/client' : r === 'admin' ? '/app/admin' : '/app/lawyer')

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (mode === 'register' && name.trim().length < 2) return setErr('Please enter your full name.')
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return setErr('Please enter a valid email address.')
    if (mode === 'register' && password.length < 10) return setErr('Use at least 10 characters for your password.')
    setErr(''); setBusy(true)
    try {
      const u = mode === 'login' ? await login(email, password)
        : await register({ name: name.trim(), email, password, role: role as 'client' | 'lawyer' | 'judge', city: city.trim() || undefined })
      nav(mode === 'register' && u.role !== 'client' ? '/app/lawyer/kyc' : home(u.role))
    } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
  }

  const persona = async (r: 'client' | 'lawyer' | 'admin') => {
    setErr('')
    try { nav(home((await demoLogin(r)).role)) } catch (e) { setErr(errorMessage(e)) }
  }

  return (
    <section className="relative min-h-screen overflow-hidden bg-gradient-to-b from-sky-100 to-sky-25 px-6 pb-16 pt-28">
      <div className="bg-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,black_20%,transparent_70%)]" />
      <div className="relative mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1fr_1.1fr]">
        <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} className="hidden lg:block">
          <ScalesArt className="size-56 animate-float" />
          <h1 className="mt-8 text-5xl leading-tight">Welcome to <span className="text-gradient">FormLaw</span></h1>
          <p className="mt-4 text-lg font-semibold text-ink-soft">One secure network for clients, advocates and judges. Choose how you’ll use FormLaw.</p>
          <ul className="mt-8 space-y-3">
            {['Documents encrypted & isolated per case', 'Every professional KYC-verified', 'AI never acts without human approval on high-risk steps'].map((t) => (
              <li key={t} className="flex items-center gap-3 font-bold"><ShieldCheck className="size-5 text-emerald-500" />{t}</li>
            ))}
          </ul>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="card p-6 md:p-8">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-2xl">{mode === 'login' ? 'Sign in' : 'Create your account'}</h2>
            <button type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setErr('') }} className="text-sm font-extrabold text-sky-600 hover:underline">
              {mode === 'login' ? 'New here? Create an account' : 'Have an account? Sign in'}
            </button>
          </div>
          {mode === 'register' && <div className="mt-5 grid gap-3" role="radiogroup" aria-label="Account type">
            {ROLES.map((r) => (
              <button key={r.id} type="button" role="radio" aria-checked={role === r.id} onClick={() => setRole(r.id)}
                className={cx('flex items-center gap-4 rounded-2xl border-2 p-4 text-left transition', role === r.id ? 'border-sky-500 bg-sky-50 shadow-[var(--shadow-glow)]' : 'border-sky-100 hover:border-sky-300')}>
                <span className={cx('grid size-12 shrink-0 place-items-center rounded-2xl transition', role === r.id ? 'bg-sky-500 text-white' : 'bg-sky-50 text-sky-600')}>{r.icon}</span>
                <span><span className="block font-extrabold">{r.title}</span><span className="block text-sm font-semibold text-ink-soft">{r.desc}</span></span>
              </button>
            ))}
          </div>}
          <form onSubmit={submit} className="mt-6 grid gap-4" noValidate>
            {mode === 'register' && <Field label="Full name"><input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder={role === 'client' ? 'e.g. Priya Sharma' : 'As on Bar Council enrolment'} autoComplete="name" /></Field>}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Email"><input className={inputCls} type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.in" autoComplete="email" /></Field>
              <Field label="Password" hint={mode === 'register' ? 'At least 10 characters' : undefined}><input className={inputCls} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} maxLength={128} /></Field>
            </div>
            {mode === 'register' && <Field label="City"><input className={inputCls} value={city} onChange={(e) => setCity(e.target.value)} placeholder="e.g. New Delhi" autoComplete="address-level2" /></Field>}
            {err && <p className="text-sm font-bold text-rose-600" role="alert">{err}</p>}
            <Button size="lg" type="submit" loading={busy}>{mode === 'login' ? 'Sign in' : role === 'client' ? 'Create account' : 'Continue to KYC verification'}</Button>
          </form>
          <div className="mt-6 border-t border-sky-100 pt-5">
            <p className="text-xs font-extrabold uppercase tracking-wider text-ink-soft">Or explore with a DEMO persona (synthetic data)</p>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <Button variant="secondary" size="sm" onClick={() => persona('client')}>Client</Button>
              <Button variant="secondary" size="sm" onClick={() => persona('lawyer')}>Advocate</Button>
              <Button variant="secondary" size="sm" onClick={() => persona('admin')}>Admin</Button>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
