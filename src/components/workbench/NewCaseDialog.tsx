import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, errorMessage } from '../../lib/api'
import { MATTER_TYPES, type Case } from '../../lib/types'
import { label } from '../../lib/util'
import { Button, Dialog, ErrorNote, Field, Input, Select } from '../ui'

export function NewCaseDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [f, setF] = useState({ title: '', matterType: 'criminal', clientName: '', court: '', jurisdiction: '', reference: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()
  const qc = useQueryClient()
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })
  const submit = async () => {
    setBusy(true); setErr('')
    try {
      const c = await api.post<Case>('/cases', { ...f, reference: f.reference || undefined })
      qc.invalidateQueries({ queryKey: ['cases'] })
      onClose()
      nav(`/cases/${c.id}?upload=1`)
    } catch (e) { setErr(errorMessage(e)) } finally { setBusy(false) }
  }
  return (
    <Dialog open={open} onClose={onClose} title="New case">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); submit() }}>
        <Field label="Case name"><Input autoFocus required value={f.title} onChange={set('title')} placeholder="State v. Arjun Kumar" /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Matter type">
            <Select value={f.matterType} onChange={set('matterType')}>{MATTER_TYPES.map((m) => <option key={m} value={m}>{label(m)}</option>)}</Select>
          </Field>
          <Field label="Reference" hint="Leave blank to auto-number"><Input value={f.reference} onChange={set('reference')} /></Field>
          <Field label="Client"><Input value={f.clientName} onChange={set('clientName')} /></Field>
          <Field label="Court"><Input value={f.court} onChange={set('court')} /></Field>
        </div>
        <Field label="Jurisdiction"><Input value={f.jurisdiction} onChange={set('jurisdiction')} placeholder="Delhi" /></Field>
        <ErrorNote>{err}</ErrorNote>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" loading={busy} disabled={f.title.trim().length < 2}>Create case</Button>
        </div>
      </form>
    </Dialog>
  )
}
