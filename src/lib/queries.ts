import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import type { Case, CaseDocument, ChatMessage, Lawyer, Thread } from './types'

export function useApi<T>(key: unknown[], path: string | null, opts: { refetchInterval?: number; retry?: boolean | number } = {}) {
  return useQuery<T>({ queryKey: key, queryFn: () => api.get<T>(path!), enabled: !!path, ...opts })
}

export const useCases = () => useApi<Case[]>(['cases'], '/cases')
export const useCase = (id?: string) => useApi<Case>(['case', id], id ? `/cases/${id}` : null)
export const useDocuments = (id?: string) => useApi<CaseDocument[]>(['documents', id], id ? `/cases/${id}/documents` : null)
export const useThreads = (id?: string) => useApi<Thread[]>(['threads', id], id ? `/cases/${id}/threads` : null)
export const useMessages = (threadId?: string) => useApi<ChatMessage[]>(['messages', threadId], threadId ? `/threads/${threadId}/messages` : null)

export interface Overview { documents: number; claims: number; unverified: number; contradictions: number; missing: number; timeline: number; authorities: number; drafts: number; openTasks: number; securityEvents: number; runs: number }
export const useOverview = (id?: string) => useApi<Overview>(['overview', id], id ? `/cases/${id}/overview` : null)
export const useCaseView = <T,>(id: string | undefined, view: string) => useApi<T>([view, id], id ? `/cases/${id}/${view}` : null)

export interface DocPages {
  document: CaseDocument
  pages: { page: number; chunks: { chunkId: string; paragraph: number; section: string | null; text: string; securityFlags: string[] }[] }[]
}
export const useDocPages = (docId?: string | null) => useApi<DocPages>(['docPages', docId], docId ? `/documents/${docId}/pages` : null)
export const useMyProfile = (enabled = true) => useApi<Lawyer>(['lawyerProfile'], enabled ? '/lawyers/profile' : null)

export interface Notification { id: string; kind: string; title: string; body: string; link: string | null; read: boolean; createdAt: string }
export const useNotifications = () => useApi<Notification[]>(['notifications'], '/notifications', { refetchInterval: 30_000 })

/** After a run finishes, everything derived from the case may have changed. */
export function useInvalidateCase() {
  const qc = useQueryClient()
  return (caseId: string) => {
    for (const k of ['case', 'overview', 'claims', 'contradictions', 'missing-information', 'timeline', 'evidence', 'authorities',
      'drafts', 'tasks', 'findings', 'activity', 'audit', 'threads', 'documents']) {
      qc.invalidateQueries({ queryKey: [k, caseId] })
    }
    qc.invalidateQueries({ queryKey: ['cases'] })
  }
}
