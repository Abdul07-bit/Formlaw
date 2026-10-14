import { lazy, Suspense, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { Skeleton } from './components/ui'
import { ViewerProvider } from './components/workbench/viewer'
import { useAuth } from './lib/auth'
import { homeFor, Landing, Login, Register } from './pages/Public'

const Home = lazy(() => import('./pages/lawyer/Home'))
const CaseWorkspace = lazy(() => import('./pages/lawyer/CaseWorkspace'))
const Research = lazy(() => import('./pages/lawyer/Research'))
const Profile = lazy(() => import('./pages/lawyer/Profile'))
const Settings = lazy(() => import('./pages/lawyer/Settings'))
const Admin = lazy(() => import('./pages/admin/Admin'))
const Compliance = lazy(() => import('./pages/admin/Admin').then((m) => ({ default: m.CompliancePage })))
const Workspace = () => import('./pages/lawyer/Workspace')
const DraftsPage = lazy(() => Workspace().then((m) => ({ default: m.DraftsPage })))
const SavedPage = lazy(() => Workspace().then((m) => ({ default: m.SavedPage })))
const RequestsPage = lazy(() => Workspace().then((m) => ({ default: m.RequestsPage })))
const NotificationsPage = lazy(() => Workspace().then((m) => ({ default: m.NotificationsPage })))
const Portal = () => import('./pages/client/Portal')
const ClientShell = lazy(() => Portal().then((m) => ({ default: m.ClientShell })))
const PortalHome = lazy(() => Portal().then((m) => ({ default: m.PortalHome })))
const SubmitMatter = lazy(() => Portal().then((m) => ({ default: m.SubmitMatter })))
const IntakeView = lazy(() => Portal().then((m) => ({ default: m.IntakeView })))
const MatterView = lazy(() => Portal().then((m) => ({ default: m.MatterView })))

function Loading() {
  return <div className="space-y-3 p-8"><Skeleton className="h-8 w-1/3" /><Skeleton className="h-40" /></div>
}

/** Client-side routing is convenience only; the API enforces every permission. */
function Gate({ role, children }: { role: 'lawyer' | 'client' | 'admin' | 'compliance'; children: ReactNode }) {
  const { user, ready } = useAuth()
  const location = useLocation()
  if (!ready) return <Loading />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  if (user.role !== role) return <Navigate to={homeFor(user)} replace />
  return <>{children}</>
}

/** "/" is the public landing page for visitors and the workbench home for lawyers. */
function Root() {
  const { user, ready } = useAuth()
  if (!ready) return <Loading />
  if (!user) return <Landing />
  if (user.role !== 'lawyer') return <Navigate to={homeFor(user)} replace />
  return <AppShell />
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<Root />}>
            <Route index element={<Home />} />
          </Route>
          <Route element={<Gate role="lawyer"><AppShell /></Gate>}>
            <Route path="/cases/:caseId" element={<CaseWorkspace />} />
            <Route path="/cases/:caseId/t/:threadId" element={<CaseWorkspace />} />
            <Route path="/cases/:caseId/drafts" element={<CaseDraftsRedirect />} />
            <Route path="/research" element={<Research />} />
            <Route path="/drafts" element={<DraftsPage />} />
            <Route path="/saved" element={<SavedPage />} />
            <Route path="/requests" element={<RequestsPage />} />
            <Route path="/notifications" element={<NotificationsPage />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
          <Route element={<Gate role="client"><ViewerProvider><ClientShell /></ViewerProvider></Gate>}>
            <Route path="/portal" element={<PortalHome />} />
            <Route path="/portal/new" element={<SubmitMatter />} />
            <Route path="/portal/requests/:id" element={<IntakeView />} />
            <Route path="/portal/matters/:id" element={<MatterView />} />
            <Route path="/portal/notifications" element={<NotificationsPage />} />
          </Route>
          <Route path="/admin" element={<Gate role="admin"><Admin /></Gate>} />
          <Route path="/compliance" element={<Gate role="compliance"><Compliance /></Gate>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

function CaseDraftsRedirect() {
  const id = location.pathname.split('/')[2]
  return <Navigate to={`/cases/${id}?view=drafts${location.search.replace('?', '&')}`} replace />
}
