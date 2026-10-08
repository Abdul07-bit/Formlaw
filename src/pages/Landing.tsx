import { AnimatePresence, motion, useScroll, useTransform } from 'framer-motion'
import {
  ArrowRight, BadgeCheck, Bot, Brain, FileSearch, FileStack, GitCompareArrows, Handshake, IdCard, Network,
  PlayCircle, ScanFace, Scale, Search, ShieldAlert, ShieldCheck, Sparkles, Upload, UserCheck, Users,
} from 'lucide-react'
import { lazy, Suspense, useMemo, useRef, useState , type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { ConstitutionArt, GavelArt, KycArt, ScalesArt, SupremeCourtArt, Chakra } from '../components/art'
import { FlowGraph } from '../components/agents'
import { LawyerCard } from '../components/case/Lawyers'
import { Badge, Button, cx } from '../components/ui'
import { useDB } from '../hooks/useStore'
import { createDemoCase, demoLogin } from '../services/api'

const HeroScene = lazy(() => import('../components/three/HeroScene'))

const reveal = { initial: { opacity: 0, y: 28 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true, margin: '-80px' }, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] as const } }

function FloatingChip({ className, children, delay = 0 }: { className: string; children: ReactNode; delay?: number }) {
  return (
    <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.8 + delay, type: 'spring' }} className={cx('glass absolute z-10 hidden rounded-2xl px-3.5 py-2.5 shadow-[var(--shadow-lift)] lg:block', className)}>
      <div className="animate-float" style={{ animationDelay: `${delay}s` }}>{children}</div>
    </motion.div>
  )
}

export default function Landing() {
  const nav = useNavigate()
  const lawyers = useDB((d) => d.lawyers)
  const featured = useMemo(() => lawyers.filter((l) => l.kyc === 'verified').slice(0, 3), [lawyers])
  const [audience, setAudience] = useState<'client' | 'lawyer'>('client')
  const heroRef = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ['start start', 'end start'] })
  const sceneY = useTransform(scrollYProgress, [0, 1], [0, 140])
  const sceneOpacity = useTransform(scrollYProgress, [0, 0.9], [1, 0.2])

  const runDemo = (malicious = false) => {
    demoLogin('client')
    const c = createDemoCase(malicious)
    nav(`/app/cases/${c.id}?run=1`)
  }

  const steps = audience === 'client'
    ? [
        { icon: <Upload className="size-6" />, t: 'Upload your case', d: 'FIR, notices, agreements, photos — PDF, DOCX, images, spreadsheets. Treated as untrusted and scanned for threats.' },
        { icon: <Brain className="size-6" />, t: 'Agents review it', d: 'Facts extracted with page-level evidence. Contradictions and missing documents flagged. A first draft prepared.' },
        { icon: <FileSearch className="size-6" />, t: 'See related cases', d: 'Matched against verified, anonymised outcomes contributed by advocates on FormLaw.' },
        { icon: <Handshake className="size-6" />, t: 'Connect with the right lawyer', d: 'Ranked by fit, outcomes and transparent fee estimates. Share your brief with one tap.' },
      ]
    : [
        { icon: <IdCard className="size-6" />, t: 'Verify once', d: 'Law degree certificate, Bar Council / government ID and live facial verification.' },
        { icon: <UserCheck className="size-6" />, t: 'Build your profile', d: 'Courts, practice areas, languages and transparent consultation & hearing fees.' },
        { icon: <FileStack className="size-6" />, t: 'Publish completed cases', d: 'Anonymised outcomes become verified credentials and power case matching.' },
        { icon: <Users className="size-6" />, t: 'Receive prepared briefs', d: 'Clients arrive with evidence-mapped facts, contradictions and drafts — not a pile of papers.' },
      ]

  return (
    <>
      {/* ── HERO ─────────────────────────────────────────── */}
      <section ref={heroRef} className="relative overflow-hidden bg-gradient-to-b from-sky-100 via-sky-50 to-sky-25 pt-28 md:pt-32">
        <div className="bg-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_75%)]" />
        <div className="absolute -left-40 top-20 size-[480px] rounded-full bg-sky-300/30 blur-3xl" />
        <div className="absolute -right-20 top-40 size-[420px] rounded-full bg-cyan-200/40 blur-3xl" />
        <div className="relative mx-auto grid max-w-7xl items-center gap-6 px-6 pb-20 lg:grid-cols-[1.05fr_1fr]">
          <div>
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-sm font-extrabold text-sky-700 shadow-[var(--shadow-soft)] ring-1 ring-sky-100">
              <span className="tricolor-bar h-3 w-5 rounded-sm" />Built for India’s courts · BNS · BNSS · BSA ready
            </motion.div>
            <motion.h1 initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1, duration: 0.7, ease: [0.22, 1, 0.36, 1] }} className="mt-6 text-[2.75rem] leading-[1.03] md:text-7xl">
              Your case, prepared by AI.<br /><span className="text-gradient">Resolved by verified lawyers.</span>
            </motion.h1>
            <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }} className="mt-6 max-w-xl text-lg font-semibold text-ink-soft">
              FormLaw is the agentic bridge between clients and KYC-verified advocates & judges. Agents read your documents, ground every fact in evidence, flag contradictions — then match you with the right counsel at a transparent fee.
            </motion.p>
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" to="/get-started?role=client" icon={<Upload className="size-5" />}>Upload my case</Button>
              <Button size="lg" variant="secondary" to="/get-started?role=lawyer" icon={<BadgeCheck className="size-5 text-sky-500" />}>Join as Lawyer / Judge</Button>
            </motion.div>
            <motion.button initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }} onClick={() => runDemo()} className="group mt-6 flex items-center gap-3 rounded-2xl text-left">
              <span className="grid size-11 place-items-center rounded-full bg-ink text-white transition group-hover:scale-110"><PlayCircle className="size-6" /></span>
              <span><span className="block text-sm font-extrabold">Run full agentic review</span><span className="block text-xs font-bold text-ink-soft">Live demo · State v. Arjun Kumar · 6 documents</span></span>
            </motion.button>
          </div>

          <motion.div style={{ y: sceneY, opacity: sceneOpacity }} className="relative h-[380px] md:h-[520px]">
            <Suspense fallback={<div className="grid size-full place-items-center"><ScalesArt className="size-64 animate-float" /></div>}>
              <HeroScene />
            </Suspense>
            <FloatingChip className="left-0 top-10" delay={0}>
              <p className="flex items-center gap-2 text-sm font-extrabold"><ScanFace className="size-4 text-emerald-500" />KYC verified · face match 96%</p>
            </FloatingChip>
            <FloatingChip className="right-0 top-24" delay={0.6}>
              <p className="flex items-center gap-2 text-sm font-extrabold text-rose-600"><GitCompareArrows className="size-4" />12 Mar vs 14 Mar — conflict</p>
            </FloatingChip>
            <FloatingChip className="bottom-12 left-6" delay={1.2}>
              <p className="flex items-center gap-2 text-sm font-extrabold"><Sparkles className="size-4 text-sky-500" />3 advocates matched · from ₹1,500</p>
            </FloatingChip>
          </motion.div>
        </div>
      </section>

      {/* ── TRUST STRIP ─────────────────────────────────── */}
      <section className="mx-auto -mt-8 max-w-6xl px-6">
        <motion.div {...reveal} className="card grid grid-cols-2 gap-6 p-6 md:grid-cols-4 md:p-8">
          {[['Every claim', 'linked to a page'], ['3-step KYC', 'degree · ID · face'], ['8 practice areas', 'criminal to cyber'], ['Human approval', 'for every high-risk action']].map(([a, b]) => (
            <div key={a}><p className="text-xl font-extrabold md:text-2xl">{a}</p><p className="text-sm font-bold text-ink-soft">{b}</p></div>
          ))}
        </motion.div>
      </section>

      {/* ── TWO-SIDED HOW IT WORKS ──────────────────────── */}
      <section className="mx-auto max-w-7xl px-6 pt-28">
        <motion.div {...reveal} className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-extrabold uppercase tracking-[0.2em] text-sky-600">One platform · two sides</p>
          <h2 className="mt-3 text-4xl md:text-5xl">The mediator between clients and counsel</h2>
          <p className="mt-4 text-lg font-semibold text-ink-soft">Clients get clarity before they pay. Lawyers get prepared, evidence-mapped briefs. Every resolved case makes the network smarter.</p>
        </motion.div>
        <div className="mx-auto mt-10 flex w-fit rounded-2xl bg-white p-1.5 shadow-[var(--shadow-soft)] ring-1 ring-sky-100" role="tablist">
          {(['client', 'lawyer'] as const).map((a) => (
            <button key={a} role="tab" aria-selected={audience === a} onClick={() => setAudience(a)} className="relative rounded-xl px-6 py-2.5 text-sm font-extrabold">
              {audience === a && <motion.span layoutId="aud" className="absolute inset-0 rounded-xl bg-sky-500" transition={{ type: 'spring', damping: 25, stiffness: 300 }} />}
              <span className={cx('relative', audience === a ? 'text-white' : 'text-ink-soft')}>{a === 'client' ? 'I need legal help' : 'I am a lawyer / judge'}</span>
            </button>
          ))}
        </div>
        <AnimatePresence mode="wait">
          <motion.div key={audience} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.35 }} className="mt-10 grid gap-5 md:grid-cols-4">
            {steps.map((s, i) => (
              <motion.div key={s.t} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }} className="card card-hover relative p-6">
                <span className="absolute right-5 top-5 font-mono text-4xl font-black text-sky-100">0{i + 1}</span>
                <span className="grid size-12 place-items-center rounded-2xl bg-sky-500 text-white shadow-[var(--shadow-glow)]">{s.icon}</span>
                <h3 className="mt-5 text-lg">{s.t}</h3>
                <p className="mt-2 text-sm font-semibold text-ink-soft">{s.d}</p>
              </motion.div>
            ))}
          </motion.div>
        </AnimatePresence>
      </section>

      {/* ── AGENT PIPELINE ──────────────────────────────── */}
      <section className="relative mt-28 overflow-hidden bg-ink py-24 text-white">
        <div className="absolute -right-24 -top-24 opacity-10"><Chakra size={420} color="#38bdf8" className="animate-spin-slow" /></div>
        <div className="relative mx-auto max-w-7xl px-6">
          <motion.div {...reveal} className="max-w-2xl">
            <p className="text-sm font-extrabold uppercase tracking-[0.2em] text-sky-300">Agentic legal intelligence</p>
            <h2 className="mt-3 text-4xl !text-white md:text-5xl">Not a chatbot. A team of agents that plan, verify and adapt.</h2>
            <p className="mt-4 text-lg font-semibold text-sky-100/80">The LLM is never the source of truth. Evidence is. When sources disagree, FormLaw re-plans, searches again — and tells you it can’t decide rather than guessing.</p>
          </motion.div>
          <div className="mt-12 [&_.card]:border-white/10 [&_.card]:bg-white/5 [&_.card]:text-white [&_p]:!text-white [&_.text-ink-soft]:!text-sky-200/70">
            <FlowGraph nodes={[
              { label: 'Documents', sub: 'untrusted input', icon: <FileStack className="size-5" /> },
              { label: 'Orchestrator', sub: 'understand · plan', icon: <Network className="size-5" /> },
              { label: 'Specialist agents', sub: 'review · retrieve', icon: <Bot className="size-5" /> },
              { label: 'Verification', sub: 'claims vs evidence', icon: <ShieldCheck className="size-5" /> },
              { label: 'Lawyer match', sub: 'fit · fees · outcomes', icon: <Handshake className="size-5" /> },
            ]} />
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {[
              { i: <GitCompareArrows className="size-5" />, t: 'Contradiction detection', d: 'Remand report says 14 March. Case diary says 12 March. Both preserved, flagged for review.' },
              { i: <Search className="size-5" />, t: 'Missing information', d: 'Arrest memo, production record, previous bail order — gaps surfaced with why they matter.' },
              { i: <ShieldAlert className="size-5" />, t: 'Prompt-injection defence', d: '“Ignore previous instructions” inside a document is quarantined, logged and never obeyed.' },
            ].map((x, i) => (
              <motion.div key={x.t} {...reveal} transition={{ ...reveal.transition, delay: i * 0.1 }} className="rounded-3xl border border-white/10 bg-white/5 p-6">
                <span className="grid size-10 place-items-center rounded-xl bg-sky-500/20 text-sky-300">{x.i}</span>
                <h3 className="mt-4 text-lg !text-white">{x.t}</h3>
                <p className="mt-2 text-sm font-semibold text-sky-100/75">{x.d}</p>
              </motion.div>
            ))}
          </div>
          <div className="mt-10 flex flex-wrap gap-3">
            <Button size="lg" onClick={() => runDemo()} icon={<PlayCircle className="size-5" />}>Run full agentic review</Button>
            <Button size="lg" variant="secondary" onClick={() => runDemo(true)} icon={<ShieldAlert className="size-5 text-rose-500" />}>Try the prompt-injection attack</Button>
          </div>
        </div>
      </section>

      {/* ── CONSTITUTIONAL GROUNDING ────────────────────── */}
      <section className="mx-auto max-w-7xl px-6 pt-28">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <motion.div {...reveal} className="relative">
            <SupremeCourtArt className="w-full drop-shadow-xl" />
            <motion.div initial={{ opacity: 0, x: 30, rotate: 4 }} whileInView={{ opacity: 1, x: 0, rotate: -3 }} viewport={{ once: true }} transition={{ delay: 0.3, type: 'spring' }} className="card absolute -bottom-10 -right-2 w-56 p-3 md:w-72">
              <ConstitutionArt className="w-full" />
            </motion.div>
          </motion.div>
          <motion.div {...reveal}>
            <p className="text-sm font-extrabold uppercase tracking-[0.2em] text-sky-600">Grounded in the Constitution</p>
            <h2 className="mt-3 text-4xl md:text-5xl">Equal justice shouldn’t depend on who you know.</h2>
            <blockquote className="mt-6 rounded-3xl border-l-4 border-saffron bg-white p-6 shadow-[var(--shadow-soft)]">
              <p className="font-bold italic text-ink">“The State shall secure that the operation of the legal system promotes justice, on a basis of equal opportunity…”</p>
              <footer className="mt-2 text-sm font-extrabold text-sky-700">— Article 39A, Constitution of India</footer>
            </blockquote>
            <ul className="mt-6 space-y-3">
              {[
                ['Article 21', 'Bail and arrest briefs check custodial safeguards first.'],
                ['Article 22', 'Arrest-date and production-time conflicts are surfaced automatically.'],
                ['New criminal laws', 'Drafts reference BNS, BNSS and BSA (in force from 1 July 2024).'],
              ].map(([a, b]) => (
                <li key={a} className="flex items-start gap-3"><Scale className="mt-0.5 size-5 shrink-0 text-sky-500" /><p className="font-semibold text-ink-soft"><span className="font-extrabold text-ink">{a} — </span>{b}</p></li>
              ))}
            </ul>
          </motion.div>
        </div>
      </section>

      {/* ── FEATURED LAWYERS ────────────────────────────── */}
      <section className="mx-auto max-w-7xl px-6 pt-36">
        <motion.div {...reveal} className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="text-sm font-extrabold uppercase tracking-[0.2em] text-sky-600">Verified counsel</p>
            <h2 className="mt-3 text-4xl md:text-5xl">Every profile is KYC-verified.</h2>
            <p className="mt-3 max-w-xl font-semibold text-ink-soft">Fees are public. Outcomes come from anonymised completed cases the advocate uploaded and FormLaw verified.</p>
          </div>
          <Button variant="secondary" to="/lawyers" icon={<ArrowRight className="size-4" />}>Browse all lawyers</Button>
        </motion.div>
        <div className="mt-10 grid gap-6 md:grid-cols-3">{featured.map((l, i) => <LawyerCard key={l.id} l={l} i={i} />)}</div>
        <p className="mt-3 text-xs font-semibold text-ink-soft">*Favourable-outcome rate is self-reported from verified completed cases and is not a guarantee of results. Demo profiles are synthetic.</p>
      </section>

      {/* ── KYC ─────────────────────────────────────────── */}
      <section className="mx-auto max-w-7xl px-6 pt-28">
        <div className="card grid items-center gap-10 overflow-hidden bg-gradient-to-br from-white to-sky-50 p-8 md:p-12 lg:grid-cols-2">
          <motion.div {...reveal}>
            <Badge tone="sky">For advocates & judges</Badge>
            <h2 className="mt-4 text-4xl">Three checks. Zero impostors.</h2>
            <ol className="mt-6 space-y-4">
              {[
                ['Law degree certificate', 'LL.B / LL.M from a recognised university.'],
                ['Bar Council or government ID', 'Bar Council ID, Aadhaar, PAN or passport — matched to your enrolment number.'],
                ['Live facial verification', 'Liveness check and 1:1 face match against your ID photo.'],
              ].map(([t, d], i) => (
                <li key={t} className="flex gap-4"><span className="grid size-9 shrink-0 place-items-center rounded-xl bg-sky-500 font-extrabold text-white">{i + 1}</span><div><p className="font-extrabold">{t}</p><p className="text-sm font-semibold text-ink-soft">{d}</p></div></li>
              ))}
            </ol>
            <Button className="mt-8" size="lg" to="/get-started?role=lawyer">Start verification</Button>
          </motion.div>
          <motion.div {...reveal} className="relative"><KycArt className="w-full" /><GavelArt className="absolute -bottom-6 -left-4 size-24 animate-float md:size-32" /></motion.div>
        </div>
      </section>

      {/* ── FINAL CTA ───────────────────────────────────── */}
      <section className="mx-auto max-w-7xl px-6 pt-28">
        <motion.div {...reveal} className="relative overflow-hidden rounded-[2.5rem] bg-gradient-to-br from-sky-500 to-sky-700 px-8 py-16 text-center text-white md:py-20">
          <div className="absolute -left-16 -top-16 opacity-20"><Chakra size={260} color="#fff" className="animate-spin-slow" /></div>
          <div className="absolute -bottom-20 -right-10 opacity-20"><Chakra size={300} color="#fff" className="animate-spin-slow" /></div>
          <h2 className="relative text-4xl !text-white md:text-6xl">AI can reason.<br />Evidence decides.</h2>
          <p className="relative mx-auto mt-4 max-w-xl text-lg font-semibold text-sky-50">Upload your first case free — get an evidence-backed review and matched counsel in minutes.</p>
          <div className="relative mt-8 flex flex-wrap justify-center gap-3">
            <Button size="lg" variant="dark" to="/get-started?role=client">Get legal help</Button>
            <Button size="lg" variant="secondary" to="/get-started?role=lawyer">Join as Lawyer</Button>
          </div>
        </motion.div>
      </section>
    </>
  )
}
