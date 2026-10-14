import { ArrowRight, BriefcaseBusiness, IndianRupee, Inbox, ScanFace, Star } from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Avatar, Badge, Button, EmptyState, KycBadge, PageHeader, Stat } from '../../components/ui'
import { useDB, useLawyer, useSession } from '../../hooks/useStore'
import { inr } from '../../utils/format'

export default function LawyerDashboard() {
  const user = useSession()!
  const l = useLawyer(user.lawyerId)
  const conversations = useDB((d) => d.conversations)
  const completed = useDB((d) => d.completedCases)
  const mine = useMemo(() => conversations.filter((c) => c.lawyerId === user.lawyerId), [conversations, user.lawyerId])
  const myCases = useMemo(() => completed.filter((c) => c.lawyerId === user.lawyerId), [completed, user.lawyerId])
  if (!l) return null
  const requests = mine.filter((c) => c.status === 'requested')
  const accepted = mine.filter((c) => c.status === 'accepted')
  const pipeline = accepted.reduce((n, c) => n + (c.quote ?? l.consultationFee), 0)

  return (
    <>
      <PageHeader eyebrow={l.role === 'judge' ? 'Judge workspace' : 'Advocate workspace'} title={l.name}
        subtitle={l.kyc === 'verified' ? 'Your profile is live. Prepared, evidence-mapped briefs arrive here.' : 'Complete KYC to appear in the marketplace and receive client briefs.'}
        actions={<><KycBadge status={l.kyc} />{l.kyc !== 'verified' && <Button to="/app/lawyer/kyc" icon={<ScanFace className="size-4" />}>Complete KYC</Button>}</>} />

      {l.kyc !== 'verified' && (
        <div className="mb-6 flex flex-col items-start justify-between gap-3 rounded-3xl border-2 border-amber-200 bg-amber-50 p-5 md:flex-row md:items-center">
          <p className="font-bold text-amber-900">{l.kyc === 'pending' ? 'Your documents are with the verification desk.' : 'Verification required: law degree, ID card and live face check.'}</p>
          <Button size="sm" variant="secondary" to="/app/lawyer/kyc">View status</Button>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="New requests" value={requests.length} icon={<Inbox className="size-4" />} tone="amber" />
        <Stat label="Active clients" value={accepted.length} icon={<BriefcaseBusiness className="size-4" />} />
        <Stat label="Fee pipeline" value={inr(pipeline)} icon={<IndianRupee className="size-4" />} tone="green" hint="Accepted quotes" />
        <Stat label="Rating" value={l.rating ? l.rating.toFixed(1) : 'New'} icon={<Star className="size-4" />} tone="violet" hint={`${l.reviews} reviews`} />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <div>
          <h2 className="mb-4 text-xl">Incoming client briefs</h2>
          {mine.length === 0 ? <EmptyState icon={<Inbox className="size-7" />} title="No briefs yet" body="When a client connects with you, their evidence-backed case brief appears here. Tip: switch to the Client persona, run the demo case and connect with Adv. Meera Iyer." />
            : (
              <div className="space-y-3">
                {mine.map((c) => (
                  <Link key={c.id} to="/app/messages" className="card card-hover flex items-center gap-4 p-4">
                    <Avatar initials={c.clientName.split(' ').map((p) => p[0]).join('').slice(0, 2)} hue={180} size={44} />
                    <div className="min-w-0 flex-1"><p className="truncate font-extrabold">{c.caseTitle}</p><p className="text-sm font-semibold text-ink-soft">{c.clientName} · {new Date(c.updatedAt).toLocaleString('en-IN')}</p></div>
                    <Badge tone={c.status === 'accepted' ? 'green' : c.status === 'declined' ? 'red' : 'amber'}>{c.status}</Badge>
                    <ArrowRight className="size-4 text-sky-500" />
                  </Link>
                ))}
              </div>
            )}
        </div>
        <div className="card p-6">
          <h3 className="text-lg">Your case record</h3>
          <p className="mt-1 text-sm font-semibold text-ink-soft">{myCases.filter((c) => c.verified).length} verified · {myCases.filter((c) => !c.verified).length} pending</p>
          <ul className="mt-4 space-y-2">
            {myCases.slice(0, 4).map((c) => <li key={c.id} className="flex items-center justify-between gap-2 rounded-2xl bg-sky-25 px-3 py-2 text-sm font-bold"><span className="truncate">{c.title}</span><Badge tone={c.verified ? 'green' : 'amber'}>{c.verified ? c.outcome : 'Pending'}</Badge></li>)}
          </ul>
          <Button className="mt-5 w-full" variant="secondary" to="/app/lawyer/cases">Publish a completed case</Button>
        </div>
      </div>
    </>
  )
}
