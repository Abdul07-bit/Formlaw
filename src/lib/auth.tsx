import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, refresh, setToken } from './api'
import { UserSchema, type User } from './types'

interface Session { accessToken: string; user: unknown }
interface AuthState {
  user: User | null
  ready: boolean
  login: (email: string, password: string) => Promise<User>
  register: (body: Record<string, unknown>) => Promise<User>
  demo: (persona: User['role']) => Promise<User>
  logout: () => Promise<void>
  reload: () => Promise<void>
}

const Ctx = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)
  const qc = useQueryClient()

  const accept = useCallback((s: Session): User => {
    setToken(s.accessToken)
    const u = UserSchema.parse(s.user)
    setUser(u)
    return u
  }, [])

  useEffect(() => {
    refresh().then((s) => {
      if (s) setUser(UserSchema.parse(s.user))
      setReady(true)
    })
  }, [])

  const value: AuthState = {
    user,
    ready,
    login: async (email, password) => accept(await api.auth<Session>('/auth/login', { email, password })),
    register: async (body) => accept(await api.auth<Session>('/auth/register', body)),
    demo: async (persona) => accept(await api.auth<Session>('/auth/demo', { persona })),
    logout: async () => {
      try { await api.auth('/auth/logout') } catch { /* already signed out */ }
      setToken(null)
      setUser(null)
      qc.clear()
    },
    reload: async () => setUser(UserSchema.parse(await api.get('/auth/me'))),
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth(): AuthState {
  const c = useContext(Ctx)
  if (!c) throw new Error('useAuth outside AuthProvider')
  return c
}
