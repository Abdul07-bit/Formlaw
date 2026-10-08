import { motion } from 'framer-motion'
import { CalendarCheck, Search, SlidersHorizontal, Star } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { LawyerCard, LawyerMeta, RelatedCaseCard } from '../components/case/Lawyers'
import { Avatar, Badge, Button, cx, EmptyState, Modal, PageHeader } from '../components/ui'
import { useDB, useSession } from '../hooks/useStore'
import { ALL_AREAS, inr, requestLawyer } from '../services/api'
import type { PracticeArea } from '../types'

export function LawyersPage({ inApp }: { inApp?: boolean }) {
  const lawyers = useDB((d) => d.lawyers)
  const [q, setQ] = useState('')
  const [area, setArea] = useState<PracticeArea | 'All'>('All')
  const [maxFee, setMaxFee] = useState(20000)
  const [sort, setSort] = useState<'rating' | 'fee' | 'experience'>('rating')
  const [judges, setJudges] = useState(false)

  const list = useMemo(() => {
    const term = q.toLowerCase()
    return lawyers
      .filter((l) => l.kyc === 'verified')
      .filter((l) => area === 'All' || l.practiceAreas.includes(area))
      .filter((l) => l.consultationFee <= maxFee)
      .filter((l) => !judges || l.role === 'judge')
      .filter((l) => !term || [l.name, l.city, l.state, ...l.courts, ...l.languages].join(' ').toLowerCase().includes(term))
      .sort((a, b) => (sort === 'rating' ? b.rating - a.rating : sort === 'fee' ? a.consultationFee - b.consultationFee : b.experienceYears - a.experienceYears))
  }, [lawyers, q, area, maxFee, sort, judges])

  return (
    <div className={cx(!inApp && 'mx-auto max-w-7xl px-6 pt-32')}>
      <PageHeader eyebrow="Verified network" title="Find the right lawyer" subtitle="Every advocate and judge on FormLaw has passed degree, ID and live facial verification. Fees are shown upfront." />
      <div className="card mb-8 grid gap-4 p-4 md:grid-cols-[1fr_auto_auto] md:items-center">
        <div className="relative">
          <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-slate-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, city, court or language" aria-label="Search lawyers" className="h-12 w-full rounded-2xl border border-sky-100 bg-sky-25 pl-12 pr-4 font-semibold outline-none focus:border-sky-400" />
        </div>
        <label className="flex items-center gap-3 text-sm font-bold text-ink-soft">
          <SlidersHorizontal className="size-4" />Consultation ≤ <span className="w-16 font-extrabold text-ink">{inr(maxFee)}</span>
          <input type="range" min={1000} max={20000} step={500} value={maxFee} onChange={(e) => setMaxFee(Number(e.target.value))} className="w-28 accent-sky-500" aria-label="Maximum consultation fee" />
        </label>
        <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)} aria-label="Sort" className="h-12 rounded-2xl border border-sky-100 bg-white px-4 font-bold outline-none focus:border-sky-400">
          <option value="rating">Top rated</option><option value="fee">Lowest fee</option><option value="experience">Most experienced</option>
        </select>
        <div className="flex flex-wrap gap-2 md:col-span-3">
          {(['All', ...ALL_AREAS] as const).map((a) => (
            <button key={a} onClick={() => setArea(a)} className={cx('rounded-full px-4 py-1.5 text-sm font-extrabold transition', area === a ? 'bg-sky-500 text-white' : 'bg-sky-50 text-sky-700 hover:bg-sky-100')}>{a}</button>
          ))}
          <button onClick={() => setJudges(!judges)} className={cx('rounded-full px-4 py-1.5 text-sm font-extrabold transition', judges ? 'bg-ink text-white' : 'bg-slate-100 text-ink-soft hover:bg-slate-200')}>Retd. judges only</button>
        </div>
      </div>
      {list.length ? (
        <motion.div layout className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">{list.map((l, i) => <LawyerCard key={l.id} l={l} i={i} basePath={inApp ? '/app/lawyers' : '/lawyers'} />)}</motion.div>
      ) : <EmptyState icon={<Search className="size-7" />} title="No lawyers match these filters" body="Try widening the fee range or choosing another practice area." />}
    </div>
  )
}

export function LawyerProfilePage({ inApp }: { inApp?: boolean }) {
  const { id } = useParams()
  const nav = useNavigate()
  const user = useSession()
  const l = useDB((d) => d.lawyers.find((x) => x.id === id))
  const completed = useDB((d) => d.completedCases)
  const allCases = useDB((d) => d.cases)
  const myCases = useMemo(() => allCases.filter((c) => c.ownerId === user?.id), [allCases, user?.id])
  const cases = useMemo(() => completed.filter((c) => c.lawyerId === id && c.verified), [completed, id])
  const [book, setBook] = useState(false)
  const [caseId, setCaseId] = useState('')
  const [sent, setSent] = useState(false)

  if (!l) return <div className={cx(!inApp && 'mx-auto max-w-7xl px-6 pt-32')}><EmptyState icon={<Search className="size-7" />} title="Profile not found" body="This advocate may not have completed verification." /></div>

  return (
    <div className={cx(!inApp && 'mx-auto max-w-7xl px-6 pt-32')}>
      <div className="relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-sky-400 to-sky-600 p-8 text-white md:p-10">
        <div className="absolute inset-0 bg-grid opacity-20" />
        <div className="relative flex flex-col gap-6 md:flex-row md:items-center">
          <Avatar initials={l.initials} hue={l.photoHue} size={104} verified={l.kyc === 'verified'} />
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2"><h1 className="text-3xl !text-white md:text-4xl">{l.name}</h1>{l.kyc === 'verified' && <span className="rounded-full bg-white px-3 py-1 text-xs font-extrabold text-emerald-600">✓ KYC Verified</span>}</div>
            <p className="mt-1 font-bold text-sky-50">{l.title} · {l.experienceYears} years · {l.city}, {l.state}</p>
            <p className="mt-1 text-sm font-semibold text-sky-100">{l.courts.join(' · ')}</p>
          </div>
          <div className="flex items-center gap-1 rounded-2xl bg-white/15 px-4 py-3 text-2xl font-extrabold"><Star className="size-6 fill-amber-300 text-amber-300" />{l.rating ? l.rating.toFixed(1) : 'New'}<span className="ml-1 text-sm font-bold text-sky-100">({l.reviews})</span></div>
        </div>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          <div className="card p-6"><h2 className="text-xl">About</h2><p className="mt-2 font-semibold text-ink-soft">{l.bio || 'Profile details coming soon.'}</p>
            <div className="mt-4 flex flex-wrap gap-2">{l.practiceAreas.map((a) => <Badge key={a}>{a}</Badge>)}</div></div>
          <div>
            <h2 className="mb-1 text-xl">Verified completed cases</h2>
            <p className="mb-4 text-sm font-semibold text-ink-soft">Anonymised by the advocate and verified by FormLaw before publication.</p>
            {cases.length ? <div className="grid gap-4 md:grid-cols-2">{cases.map((c) => <RelatedCaseCard key={c.id} r={{ caseId: c.id, similarity: 1, sharedTerms: [] }} c={c} plain />)}</div>
              : <EmptyState icon={<Star className="size-7" />} title="No published cases yet" body="Completed cases appear here once verified." />}
          </div>
        </div>
        <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
          <div className="card p-6">
            <p className="text-xs font-extrabold uppercase tracking-wider text-ink-soft">Transparent fees</p>
            <div className="mt-3 space-y-2">
              <div className="flex justify-between font-bold"><span className="text-ink-soft">Consultation</span><span>{inr(l.consultationFee)}</span></div>
              <div className="flex justify-between font-bold"><span className="text-ink-soft">Per hearing</span><span>{inr(l.hearingFee)}</span></div>
            </div>
            <Button className="mt-5 w-full" size="lg" icon={<CalendarCheck className="size-5" />} onClick={() => (user?.role === 'client' ? setBook(true) : nav('/get-started?role=client'))}>Connect & book consultation</Button>
            <p className="mt-2 text-center text-xs font-semibold text-ink-soft">Payments held in escrow until the consultation happens (backend).</p>
          </div>
          <div className="card p-6"><LawyerMeta l={l} /></div>
        </aside>
      </div>

      <Modal open={book} onClose={() => { setBook(false); setSent(false) }} title={`Connect with ${l.name}`}>
        {sent ? <div className="text-center"><p className="text-lg font-extrabold text-emerald-700">✓ Brief sent</p><p className="mt-1 text-sm font-semibold text-ink-soft">You’ll see the advocate’s reply in Messages.</p><Button className="mt-4" to="/app/messages">Open messages</Button></div>
          : myCases.length ? (
            <>
              <p className="text-sm font-semibold text-ink-soft">Choose which case brief to share:</p>
              <div className="mt-3 space-y-2">
                {myCases.map((c) => (
                  <button key={c.id} onClick={() => setCaseId(c.id)} className={cx('w-full rounded-2xl border-2 p-3 text-left font-bold transition', caseId === c.id ? 'border-sky-500 bg-sky-50' : 'border-sky-100')}>{c.title}<span className="block text-xs text-ink-soft">{c.analysis ? `${c.analysis.area} · reviewed` : 'not reviewed'}</span></button>
                ))}
              </div>
              <Button className="mt-4 w-full" disabled={!caseId} onClick={() => { requestLawyer(caseId, l.id, ''); setSent(true) }}>Send case brief</Button>
            </>
          ) : <div className="text-center"><p className="font-semibold text-ink-soft">Create a case first so FormLaw can prepare an evidence-backed brief.</p><Button className="mt-4" to="/app/cases/new">Create a case</Button></div>}
      </Modal>
    </div>
  )
}
