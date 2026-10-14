import type { Approval, ApprovalAction, Conversation } from '../../types'
import { request } from '../api/client'
import { store, upsert } from '../store'
import { loadCase } from '../cases'

export async function loadConnections() {
  const list = await request<Conversation[]>('/connections')
  store.update((d) => ({ ...d, conversations: list }))
  return list
}

const putConv = (c: Conversation) => store.update((d) => ({ ...d, conversations: upsert(d.conversations, c, true) }))

/** Step 1 of a HIGH-risk action: the server validates it and describes exactly what will happen. Nothing runs yet. */
export const prepareAction = (action: ApprovalAction, resourceId: string, params: Record<string, string> = {}) =>
  request<Approval>('/approvals', { body: { action, resourceId, params } })

/** Step 2: the responsible person approves (executes) or rejects. */
export async function decideAction(id: string, approve: boolean) {
  const a = await request<Approval>(`/approvals/${encodeURIComponent(id)}/decision`, { body: { approve } })
  if (a.status === 'executed') {
    if (a.action === 'connection.request' || a.action === 'draft.share') await loadConnections()
    if (a.action === 'connection.request') await loadCase(a.resourceId)
    if (a.action === 'case.delete') store.update((d) => ({ ...d, cases: d.cases.filter((c) => c.id !== a.resourceId) }))
  }
  return a
}

export async function respondToRequest(convId: string, accept: boolean, quote?: number) {
  putConv(await request<Conversation>(`/connections/${encodeURIComponent(convId)}/respond`, { body: { accept, quote: quote ?? null } }))
}

export async function sendMessage(convId: string, text: string) {
  const clean = text.trim().slice(0, 4000)
  if (!clean) return
  putConv(await request<Conversation>(`/connections/${encodeURIComponent(convId)}/messages`, { body: { text: clean } }))
}
