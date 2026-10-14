import { Bell, BookOpen, Bookmark, FilePen, FolderPlus, Inbox, LogOut, Menu, MessageSquarePlus, Moon, Settings, Sun, UserRound } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, NavLink, Outlet, useMatch, useNavigate } from 'react-router-dom'
import { useAuth } from '../../lib/auth'
import { useApi, useCases, useNotifications, useThreads } from '../../lib/queries'
import { cx, timeAgo, useTheme } from '../../lib/util'
import { Badge, IconButton } from '../ui'
import { NewCaseDialog } from '../workbench/NewCaseDialog'
import { ViewerProvider } from '../workbench/viewer'

function NavItem({ to, icon, children, badge }: { to: string; icon: ReactNode; children: ReactNode; badge?: number }) {
  return (
    <NavLink to={to} className={({ isActive }) => cx('flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13.5px]', isActive ? 'bg-surface-3 text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg')}>
      <span className="text-faint">{icon}</span><span className="flex-1 truncate">{children}</span>
      {badge ? <span className="rounded-full bg-accent px-1.5 text-[11px] font-semibold text-on-accent">{badge}</span> : null}
    </NavLink>
  )
}

export function Brand({ to = '/' }: { to?: string }) {
  return (
    <Link to={to} viewTransition className="flex items-center gap-2">
      <span className="flex size-7 items-center justify-center rounded-lg bg-[#1f2a44] font-serif text-[15px] font-semibold text-[#f5f1e8]">F</span>
      <span className="font-serif text-[17px] font-semibold tracking-tight">FormLaw</span>
    </Link>
  )
}

function Sidebar({ onNavigate }: { onNavigate: () => void }) {
  const { user, logout } = useAuth()
  const [dark, toggle] = useTheme()
  const [newCase, setNewCase] = useState(false)
  const nav = useNavigate()
  const match = useMatch('/cases/:caseId/*')
  const activeCase = match?.params.caseId
  const threadMatch = useMatch('/cases/:caseId/t/:threadId')
  const { data: cases } = useCases()
  const { data: threads } = useThreads(activeCase)
  const { data: requests } = useApi<{ status: string }[]>(['requests'], '/requests')
  const { data: notes } = useNotifications()
  const pending = requests?.filter((r) => r.status === 'requested').length ?? 0
  const unread = notes?.filter((n) => !n.read).length ?? 0

  return (
    <div className="flex h-full flex-col gap-3 p-3" onClick={(e) => (e.target as HTMLElement).closest('a') && onNavigate()}>
      <div className="flex items-center justify-between px-1"><Brand /></div>
      <div className="space-y-1">
        <button type="button" onClick={() => setNewCase(true)} className="flex w-full items-center gap-2.5 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[13.5px] font-medium hover:bg-surface-2">
          <FolderPlus className="size-4 text-muted" />New case
        </button>
        <button type="button" onClick={() => { nav(activeCase ? `/cases/${activeCase}` : '/'); onNavigate() }} className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13.5px] text-muted hover:bg-surface-2 hover:text-fg">
          <MessageSquarePlus className="size-4 text-faint" />New chat
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <p className="px-2.5 pb-1 text-[11px] font-semibold uppercase tracking-wider text-faint">Cases</p>
        <ul className="space-y-0.5">
          {(cases ?? []).slice(0, 12).map((c) => (
            <li key={c.id}>
              <NavLink to={`/cases/${c.id}`} end={false} className={({ isActive }) => cx('block truncate rounded-lg px-2.5 py-1.5 text-[13.5px]', isActive ? 'bg-surface-3 font-medium text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg')}>
                {c.title}
              </NavLink>
              {c.id === activeCase && !!threads?.length && (
                <ul className="my-0.5 ml-3 space-y-0.5 border-l border-line pl-2">
                  {threads.slice(0, 8).map((t) => (
                    <li key={t.id}>
                      <Link to={`/cases/${c.id}/t/${t.id}`} title={t.title} className={cx('block truncate rounded-md px-2 py-1 text-[12.5px]', threadMatch?.params.threadId === t.id ? 'bg-surface-2 text-fg' : 'text-muted hover:text-fg')}>
                        {t.title}<span className="ml-1 text-faint">· {timeAgo(t.updatedAt ?? t.createdAt)}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
          {!cases?.length && <li className="px-2.5 py-1 text-[12.5px] text-faint">No cases yet</li>}
        </ul>

        <p className="mt-4 px-2.5 pb-1 text-[11px] font-semibold uppercase tracking-wider text-faint">Workspace</p>
        <NavItem to="/research" icon={<BookOpen className="size-4" />}>Legal research</NavItem>
        <NavItem to="/drafts" icon={<FilePen className="size-4" />}>Drafts</NavItem>
        <NavItem to="/saved" icon={<Bookmark className="size-4" />}>Saved</NavItem>
        <NavItem to="/requests" icon={<Inbox className="size-4" />} badge={pending}>Client requests</NavItem>
      </div>

      <div className="space-y-0.5 border-t border-line pt-2">
        <NavItem to="/notifications" icon={<Bell className="size-4" />} badge={unread}>Notifications</NavItem>
        <NavItem to="/profile" icon={<UserRound className="size-4" />}>Profile & KYC</NavItem>
        <NavItem to="/settings" icon={<Settings className="size-4" />}>Settings</NavItem>
        <div className="flex items-center gap-2 px-2.5 pt-2">
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium">{user?.name}</p>
            <p className="truncate text-[11.5px] text-faint">{user?.organizationName}</p>
          </div>
          {user?.verificationStatus === 'VERIFIED' && <Badge tone="ok">verified</Badge>}
          <IconButton label={dark ? 'Light theme' : 'Dark theme'} onClick={toggle}>{dark ? <Sun className="size-4" /> : <Moon className="size-4" />}</IconButton>
          <IconButton label="Sign out" onClick={() => logout().then(() => nav('/'))}><LogOut className="size-4" /></IconButton>
        </div>
      </div>
      <NewCaseDialog open={newCase} onClose={() => setNewCase(false)} />
    </div>
  )
}

export function AppShell() {
  const [mobile, setMobile] = useState(false)
  return (
    <ViewerProvider>
      <div className="flex h-full">
        <aside className="hidden w-64 shrink-0 border-r border-line bg-surface-2/50 lg:block"><Sidebar onNavigate={() => {}} /></aside>
        {mobile && (
          <div className="fixed inset-0 z-40 bg-black/30 lg:hidden" onClick={() => setMobile(false)}>
            <aside className="h-full w-72 border-r border-line bg-surface" onClick={(e) => e.stopPropagation()}><Sidebar onNavigate={() => setMobile(false)} /></aside>
          </div>
        )}
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-2 border-b border-line px-3 py-2 lg:hidden">
            <IconButton label="Open menu" onClick={() => setMobile(true)}><Menu className="size-5" /></IconButton>
            <Brand />
          </div>
          <div className="min-h-0 flex-1"><Outlet /></div>
        </main>
      </div>
    </ViewerProvider>
  )
}
