import { FileLock2, LogOut, ShieldCheck, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApprovalBox } from '../components/case/Lawyers'
import { Badge, Button, PageHeader } from '../components/ui'
import { useDB, useSession } from '../hooks/useStore'
import { errorMessage } from '../services/api/client'
import { signOut } from '../services/auth'
import { decideAction, prepareAction } from '../services/connections'
import type { Approval } from '../types'

export default function Profile() {
  const user = useSession()!
  const nav = useNavigate()
  const all = useDB((d) => d.cases)
  const cases = useMemo(() => all.filter((c) => c.access === 'owner'), [all])
  const [req, setReq] = useState<Approval | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const askDelete = async (caseId: string) => {
    setErr('')
    try { setReq(await prepareAction('case.delete', caseId)) } catch (e) { setErr(errorMessage(e)) }
  }
  const decide = async (ok: boolean) => {
    if (!req) return
    setBusy(true)
    try { await decideAction(req.id, ok); setReq(null) } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
  }

  return (
    <>
      <PageHeader eyebrow="Account" title="Profile & privacy" />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card p-6">
          <h2 className="text-xl">{user.name}</h2>
          <p className="mt-1 font-semibold text-ink-soft">{user.email}</p>
          <div className="mt-3 flex gap-2"><Badge className="capitalize">{user.role}</Badge>{user.city && <Badge tone="slate">{user.city}</Badge>}{user.isDemo && <Badge tone="violet">Demo account</Badge>}</div>
          <Button className="mt-6" variant="secondary" icon={<LogOut className="size-4" />} onClick={() => { void signOut().then(() => nav('/')) }}>Sign out</Button>
        </div>
        <div className="card p-6">
          <h2 className="flex items-center gap-2 text-xl"><ShieldCheck className="size-5 text-emerald-500" />How your data is handled</h2>
          <ul className="mt-3 space-y-2 text-sm font-semibold text-ink-soft">
            <li>Documents are stored encrypted, isolated to your case, and never used to train models.</li>
            <li>Advocates see an evidence brief only after you approve sharing it, never your raw document text.</li>
            <li>Sharing, drafting for others and deletion are high-risk actions that need your explicit approval.</li>
            <li>Every access and decision is recorded in an audit log without copying document content.</li>
          </ul>
        </div>
      </div>
      {user.role === 'client' && (
        <div className="card mt-6 p-6">
          <h2 className="flex items-center gap-2 text-xl"><FileLock2 className="size-5 text-sky-500" />Delete a case</h2>
          <p className="mt-1 text-sm font-semibold text-ink-soft">Permanently removes the case and its stored files. This cannot be undone.</p>
          {req ? <div className="mt-4"><ApprovalBox req={req} busy={busy} onDecide={decide} /></div> : (
            <ul className="mt-4 divide-y divide-sky-100">
              {cases.map((c) => (
                <li key={c.id} className="flex items-center justify-between gap-3 py-3">
                  <span className="truncate font-bold">{c.title}</span>
                  <Button size="sm" variant="ghost" onClick={() => askDelete(c.id)} icon={<Trash2 className="size-4" />}>Delete</Button>
                </li>
              ))}
              {!cases.length && <li className="py-3 text-sm font-semibold text-ink-soft">No cases.</li>}
            </ul>
          )}
          {err && <p className="mt-3 text-sm font-bold text-rose-600" role="alert">{err}</p>}
        </div>
      )}
    </>
  )
}
