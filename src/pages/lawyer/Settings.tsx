import { Moon, Sun } from 'lucide-react'
import { Badge, Button, Card } from '../../components/ui'
import { useApi } from '../../lib/queries'
import { label, useTheme } from '../../lib/util'
import { Page } from './Workspace'

interface AgentSpec { name: string; purpose: string; tools: string[]; inputs: string; outputs: string; failureModes: string; verification: string; risk: string }

interface RegisterRow { id: string; reference: string; matterType: string; status: string; createdAt: string | null; leads: string[]; teamSize: number; iAmMember: boolean }

/** Firm owners/admins see which matters exist — never titles, clients or content (that needs the matter lead to add them). */
function FirmRegister() {
  const { data, error } = useApi<RegisterRow[]>(['firmRegister'], '/firm/matters', { retry: false })
  if (error || !data) return null
  return (
    <section className="mt-8">
      <h2 className="font-serif text-lg">Firm matter register</h2>
      <p className="mt-1 text-sm text-muted">As a firm owner or administrator you can see which matters exist and who leads them. Opening a matter still requires its lead to add you.</p>
      <div className="mt-3 overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-left text-[13px]">
          <thead className="bg-surface-2 text-[11px] uppercase tracking-wide text-muted"><tr><th className="px-3 py-2">Reference</th><th>Type</th><th>Status</th><th>Lead</th><th>Team</th><th>You</th></tr></thead>
          <tbody>{data.map((m) => (
            <tr key={m.id} className="border-t border-line"><td className="px-3 py-1.5 font-mono">{m.reference}</td><td>{label(m.matterType)}</td><td>{m.status}</td><td>{m.leads.join(', ')}</td><td>{m.teamSize}</td><td>{m.iAmMember ? <Badge tone="ok">member</Badge> : <span className="text-faint">no access</span>}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  )
}

export default function Settings() {
  const [dark, toggle] = useTheme()
  const { data: agents } = useApi<AgentSpec[]>(['agents'], '/agents')
  return (
    <Page title="Settings">
      <Card className="flex items-center justify-between p-4">
        <div><p className="font-medium">Appearance</p><p className="text-[13px] text-muted">{dark ? 'Dark' : 'Light'} theme</p></div>
        <Button onClick={toggle}>{dark ? <Sun className="size-4" /> : <Moon className="size-4" />}Switch to {dark ? 'light' : 'dark'}</Button>
      </Card>
      <FirmRegister />

      <h2 className="mt-8 font-serif text-lg">How FormLaw works</h2>
      <p className="mt-1 text-sm text-muted">
        Every request is planned by the Orchestrator and delegated to specialised agents. Agents communicate only through a shared, cited record,
        reach tools only through a gateway with per-agent allow-lists and budgets, and none can send, share or delete anything — those actions
        need your explicit approval. Every statement is verified against its source before it is shown as a finding.
      </p>
      <ul className="mt-4 grid gap-2 sm:grid-cols-2">
        {(agents ?? []).map((a) => (
          <li key={a.name} className="rounded-xl border border-line bg-surface p-3">
            <p className="font-medium">{a.name}</p>
            <p className="text-[13px] text-muted">{a.purpose}</p>
            <div className="mt-2 flex flex-wrap gap-1">{a.tools.map((t) => <Badge key={t}>{t}</Badge>)}</div>
            <p className="mt-2 text-[12px] text-faint"><span className="font-medium text-muted">Verification:</span> {a.verification}</p>
            <p className="text-[12px] text-faint"><span className="font-medium text-muted">If it fails:</span> {a.failureModes}</p>
          </li>
        ))}
      </ul>
    </Page>
  )
}
