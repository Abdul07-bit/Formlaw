import type { ClientCase, CompletedCase, Conversation, Lawyer, SecurityEvent, User } from '../types'

// In-memory client cache of server data. The backend is the source of truth; nothing here is persisted
// to localStorage (legal documents must not sit in browser storage). Pages read via useDB selectors;
// only the service modules write, always with data returned by the API.

export interface DB {
  authReady: boolean // session restore finished (avoids redirect flicker)
  session: User | null
  lawyers: Lawyer[]
  completedCases: CompletedCase[]
  cases: ClientCase[]
  conversations: Conversation[]
  securityLog: SecurityEvent[]
}

const empty = (): DB => ({ authReady: false, session: null, lawyers: [], completedCases: [], cases: [], conversations: [], securityLog: [] })

let db: DB = empty()
const listeners = new Set<() => void>()

export const store = {
  get: () => db,
  subscribe(fn: () => void) {
    listeners.add(fn)
    return () => { listeners.delete(fn) }
  },
  update(mutator: (draft: DB) => DB) {
    db = mutator(db)
    listeners.forEach((l) => l())
  },
  /** Drop everything tied to the signed-in user (keeps the public directory). */
  clearPrivate() {
    store.update((d) => ({ ...empty(), authReady: true, lawyers: d.lawyers.map(({ kycSubmission: _k, ...l }) => l as Lawyer), completedCases: d.completedCases.filter((c) => c.verified) }))
  },
}

/** Insert or replace by id. */
export function upsert<T extends { id: string }>(list: T[], item: T, prepend = false): T[] {
  return list.some((x) => x.id === item.id) ? list.map((x) => (x.id === item.id ? item : x)) : prepend ? [item, ...list] : [...list, item]
}
