import type { ClientCase, CompletedCase, Conversation, Lawyer, SecurityEvent, User } from '../types'
import { seedLawyers } from '../data/lawyers'
import { seedCompletedCases } from '../data/completedCases'

// Local persistence for the prototype. Every read/write goes through this module so it can be
// replaced 1:1 by HTTP calls to the FastAPI backend (PostgreSQL + pgvector + object storage).

export interface DB {
  version: 2
  sessionUserId: string | null
  users: User[]
  lawyers: Lawyer[]
  completedCases: CompletedCase[]
  cases: ClientCase[]
  conversations: Conversation[]
  securityLog: SecurityEvent[]
}

const KEY = 'formlaw.db.v2'

function seed(): DB {
  return {
    version: 2,
    sessionUserId: null,
    users: [
      { id: 'USR-ADMIN', name: 'Verification Desk', email: 'admin@formlaw.in', role: 'admin' },
      ...seedLawyers.map((l) => ({
        id: `USR-${l.id}`, name: l.name, email: `${l.initials.toLowerCase()}@formlaw.in`,
        role: l.role, city: l.city, lawyerId: l.id,
      } satisfies User)),
    ],
    lawyers: seedLawyers,
    completedCases: seedCompletedCases,
    cases: [],
    conversations: [],
    securityLog: [],
  }
}

function load(): DB {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as DB
      if (parsed.version === 2) return parsed
    }
  } catch {
    /* storage unavailable or corrupt — fall back to seed */
  }
  return seed()
}

let db: DB = load()
const listeners = new Set<() => void>()

function persist() {
  try {
    localStorage.setItem(KEY, JSON.stringify(db))
  } catch {
    /* quota or private mode — keep in memory */
  }
}

export const store = {
  get: () => db,
  subscribe(fn: () => void) {
    listeners.add(fn)
    return () => listeners.delete(fn)
  },
  update(mutator: (draft: DB) => DB) {
    db = mutator(db)
    persist()
    listeners.forEach((l) => l())
  },
  reset() {
    db = seed()
    persist()
    listeners.forEach((l) => l())
  },
}

export const uid = (prefix: string) =>
  `${prefix}-${Date.now().toString(36).toUpperCase()}${Math.random().toString(36).slice(2, 5).toUpperCase()}`
