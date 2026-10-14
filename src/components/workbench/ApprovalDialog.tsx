import { ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { api, errorMessage } from '../../lib/api'
import { Badge, Button, Dialog, ErrorNote, Field, Input, Textarea } from '../ui'

interface Approval { id: string; summary: string; risk: string; status: string }

/**
 * HIGH-risk action flow: REQUEST → server describes exactly what will happen → the lawyer approves that exact record
 * → the server re-validates and executes → audit. Nothing is sent before approval.
 */
export function ApprovalDialog({ open, onClose, action, resourceId, title = 'Confirm a high-risk action', withMessage }: {
  open: boolean; onClose: () => void; action: string; resourceId: string; title?: string; withMessage?: boolean
}) {
  const [req, setReq] = useState<Approval | null>(null)
  const [msgTitle, setMsgTitle] = useState('')
  const [msgBody, setMsgBody] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<string | null>(null)

  const close = () => { setReq(null); setErr(''); setDone(null); setMsgTitle(''); setMsgBody(''); onClose() }
  const request = async () => {
    setBusy(true); setErr('')
    try {
      setReq(await api.post<Approval>('/approvals', { action, resourceId, params: withMessage ? { title: msgTitle, body: msgBody } : {} }))
    } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
  }
  const decide = async (approve: boolean) => {
    if (!req) return
    setBusy(true)
    try {
      const r = await api.post<Approval>(`/approvals/${req.id}/decision`, { approve })
      setDone(r.status === 'executed' ? 'Done. The action was executed and recorded in the audit log.' : 'Cancelled. Nothing was sent.')
    } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
  }

  return (
    <Dialog open={open} onClose={close} title={title}>
      {done ? (
        <div className="space-y-4"><p className="text-sm">{done}</p><Button onClick={close}>Close</Button></div>
      ) : !req ? (
        <div className="space-y-3">
          {withMessage && (
            <>
              <Field label="Title"><Input value={msgTitle} onChange={(e) => setMsgTitle(e.target.value)} placeholder="e.g. Bail hearing moved to Friday" /></Field>
              <Field label="Message to the client" hint="Clients only ever see updates you approve here — never research, notes or AI traces.">
                <Textarea rows={5} value={msgBody} onChange={(e) => setMsgBody(e.target.value)} />
              </Field>
            </>
          )}
          <ErrorNote>{err}</ErrorNote>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={close}>Cancel</Button>
            <Button variant="primary" loading={busy} onClick={request} disabled={withMessage && (!msgTitle.trim() || !msgBody.trim())}>Review action</Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex gap-3 rounded-xl border border-line bg-surface-2 p-3">
            <ShieldCheck className="mt-0.5 size-5 shrink-0 text-accent" />
            <div>
              <Badge tone="bad">{req.risk} risk</Badge>
              <p className="mt-1.5 text-[14.5px]">{req.summary}</p>
              <p className="mt-1 text-[12px] text-muted">FormLaw will re-check this action at execution time and record it in the audit log.</p>
            </div>
          </div>
          <ErrorNote>{err}</ErrorNote>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" loading={busy} onClick={() => decide(false)}>Reject</Button>
            <Button variant="primary" loading={busy} onClick={() => decide(true)}>Approve &amp; execute</Button>
          </div>
        </div>
      )}
    </Dialog>
  )
}
