import { lazy, Suspense, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell, PublicLayout } from './components/layout'
import { useSession } from './hooks/useStore'
import Landing from './pages/Landing'
import { createDemoCase, demoLogin } from './services/api'

const GetStarted = lazy(() => import('./pages/GetStarted'))
const HowItWorks = lazy(() => import('./pages/HowItWorks'))
const LawyersMod = () => import('./pages/Lawyers')
const LawyersPage = lazy(() => LawyersMod().then((m) => ({ default: m.LawyersPage })))
const LawyerProfilePage = lazy(() => LawyersMod().then((m) => ({ default: m.LawyerProfilePage })))
const ClientDashboard = lazy(() => import('./pages/client/ClientDashboard'))
const NewCase = lazy(() => import('./pages/client/NewCase'))
const CaseWorkspace = lazy(() => import('./pages/client/CaseWorkspace'))
const LawyerDashboard = lazy(() => import('./pages/lawyer/LawyerDashboard'))
const LawyerKyc = lazy(() => import('./pages/lawyer/LawyerKyc'))
const LawyerCases = lazy(() => import('./pages/lawyer/LawyerCases'))
const Messages = lazy(() => import('./pages/Messages'))
const AdminMod = () => import('./pages/admin/Admin')
const AdminKyc = lazy(() => AdminMod().then((m) => ({ default: m.AdminKyc })))
const AdminCases = lazy(() => AdminMod().then((m) => ({ default: m.AdminCases })))
const SecurityCenter = lazy(() => AdminMod().then((m) => ({ default: m.SecurityCenter })))
const Observability = lazy(() => AdminMod().then((m) => ({ default: m.Observability })))

// One-click judge demo: /demo (hero scenario) and /demo/attack (prompt-injection scenario).
let lastDemo: { attack: boolean; at: number; to: string } | null = null
function DemoLauncher({ attack = false }: { attack?: boolean }) {
  const [to] = useState(() => {
    // StrictMode invokes initialisers twice in dev — reuse the case created moments ago.
    if (lastDemo && lastDemo.attack === attack && Date.now() - lastDemo.at < 2000) return lastDemo.to
    demoLogin('client')
    lastDemo = { attack, at: Date.now(), to: `/app/cases/${createDemoCase(attack).id}?run=1` }
    return lastDemo.to
  })
  return <Navigate to={to} replace />
}

function Loading() {
  return <div className="mx-auto max-w-5xl space-y-4 px-6 pt-32"><div className="skeleton h-10 w-1/3" /><div className="skeleton h-40" /><div className="skeleton h-40" /></div>
}

function AppHome() {
  const u = useSession()
  if (!u) return <Navigate to="/get-started" replace />
  return <Navigate to={u.role === 'client' ? '/app/client' : u.role === 'admin' ? '/app/admin' : '/app/lawyer'} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route element={<PublicLayout />}>
            <Route path="/" element={<Landing />} />
            <Route path="/get-started" element={<GetStarted />} />
            <Route path="/how-it-works" element={<HowItWorks />} />
            <Route path="/lawyers" element={<LawyersPage />} />
            <Route path="/lawyers/:id" element={<LawyerProfilePage />} />
          </Route>
          <Route path="/app" element={<AppShell />}>
            <Route index element={<AppHome />} />
            <Route path="client" element={<ClientDashboard />} />
            <Route path="cases/new" element={<NewCase />} />
            <Route path="cases/:id" element={<CaseWorkspace />} />
            <Route path="lawyers" element={<LawyersPage inApp />} />
            <Route path="lawyers/:id" element={<LawyerProfilePage inApp />} />
            <Route path="messages" element={<Messages />} />
            <Route path="lawyer" element={<LawyerDashboard />} />
            <Route path="lawyer/kyc" element={<LawyerKyc />} />
            <Route path="lawyer/cases" element={<LawyerCases />} />
            <Route path="admin" element={<AdminKyc />} />
            <Route path="admin/cases" element={<AdminCases />} />
            <Route path="admin/ops" element={<Observability />} />
            <Route path="security" element={<SecurityCenter />} />
          </Route>
          <Route path="/demo" element={<DemoLauncher />} />
          <Route path="/demo/attack" element={<DemoLauncher attack />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
