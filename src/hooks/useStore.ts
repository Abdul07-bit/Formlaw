import { useSyncExternalStore } from 'react'
import { store, type DB } from '../services/store'

export function useDB<T>(selector: (db: DB) => T): T {
  return useSyncExternalStore(store.subscribe, () => selector(store.get()))
}

export function useSession() {
  return useDB((db) => db.users.find((u) => u.id === db.sessionUserId))
}

export function useLawyer(id: string | undefined) {
  return useDB((db) => db.lawyers.find((l) => l.id === id))
}
