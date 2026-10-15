import { lazy, Suspense, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { DeskLayout } from './components/Layout'
import { Spinner, ToastProvider } from './components/ui'
import Login, { homeOf } from './pages/Login'
import { AppProvider, useApp } from './store'

const Cockpit = lazy(() => import('./pages/principal/Cockpit'))
const PInspect = lazy(() => import('./pages/principal/Inspect'))
const Council = lazy(() => import('./pages/principal/Council'))
const Arena = lazy(() => import('./pages/principal/Arena'))
const Knowledge = lazy(() => import('./pages/Knowledge'))
const ParentChat = lazy(() => import('./pages/parent/Parent'))
const S = () => import('./pages/staff/Staff')
const StaffShell = lazy(() => S().then((m) => ({ default: m.StaffShell })))
const NewInspection = lazy(() => S().then((m) => ({ default: m.NewInspection })))
const InspectionResult = lazy(() => S().then((m) => ({ default: m.InspectionResult })))
const MyInspections = lazy(() => S().then((m) => ({ default: m.MyInspections })))
const MyRect = lazy(() => S().then((m) => ({ default: m.MyRect })))
const ParentQueue = lazy(() => S().then((m) => ({ default: m.ParentQueue })))
const StaffAssistant = lazy(() => S().then((m) => ({ default: m.StaffAssistant })))
const A = () => import('./pages/admin/Admin')
const Wizard = lazy(() => A().then((m) => ({ default: m.Wizard })))
const ImportCenter = lazy(() => A().then((m) => ({ default: m.ImportCenter })))
const Org = lazy(() => A().then((m) => ({ default: m.Org })))
const SemesterPage = lazy(() => A().then((m) => ({ default: m.SemesterPage })))
const SchedulePage = lazy(() => A().then((m) => ({ default: m.SchedulePage })))
const Settings = lazy(() => A().then((m) => ({ default: m.Settings })))
const Logs = lazy(() => A().then((m) => ({ default: m.Logs })))
const Sla = lazy(() => A().then((m) => ({ default: m.Sla })))
const BrandPage = lazy(() => A().then((m) => ({ default: m.BrandPage })))

function Guard({ roles, children }: { roles: string[]; children: ReactNode }) {
  const { me, loading } = useApp()
  if (loading) return <Loading />
  if (!me) return <Navigate to="/login" replace />
  if (!roles.includes(me.role)) return <Navigate to={homeOf(me.role)} replace />
  return <>{children}</>
}

const Loading = () => <div className="flex h-screen items-center justify-center gap-2 text-ink-3"><Spinner />加载中…</div>

function Home() {
  const { me, loading } = useApp()
  if (loading) return <Loading />
  return <Navigate to={me ? homeOf(me.role) : '/login'} replace />
}

export default function App() {
  return (
    <AppProvider>
      <ToastProvider>
        <BrowserRouter>
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/login" element={<Login />} />
              <Route path="/principal" element={<Guard roles={['principal']}><DeskLayout kind="principal" /></Guard>}>
                <Route index element={<Cockpit />} />
                <Route path="inspect" element={<PInspect />} />
                <Route path="council" element={<Council />} />
                <Route path="arena" element={<Arena />} />
                <Route path="knowledge" element={<Knowledge />} />
                <Route path="semester" element={<SemesterPage />} />
              </Route>
              <Route path="/staff" element={<Guard roles={['staff', 'principal']}><StaffShell /></Guard>}>
                <Route index element={<NewInspection />} />
                <Route path="result/:id" element={<InspectionResult />} />
                <Route path="mine" element={<MyInspections />} />
                <Route path="rect" element={<MyRect />} />
                <Route path="parents" element={<ParentQueue />} />
                <Route path="ask" element={<StaffAssistant />} />
              </Route>
              <Route path="/parent" element={<Guard roles={['parent', 'principal', 'admin']}><ParentChat /></Guard>} />
              <Route path="/admin" element={<Guard roles={['admin']}><DeskLayout kind="admin" /></Guard>}>
                <Route index element={<Wizard />} />
                <Route path="import" element={<ImportCenter />} />
                <Route path="kb" element={<Knowledge admin />} />
                <Route path="org" element={<Org />} />
                <Route path="semester" element={<SemesterPage />} />
                <Route path="schedule" element={<SchedulePage />} />
                <Route path="settings" element={<Settings />} />
                <Route path="logs" element={<Logs />} />
                <Route path="sla" element={<Sla />} />
                <Route path="brand" element={<BrandPage />} />
              </Route>
              <Route path="*" element={<Home />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </ToastProvider>
    </AppProvider>
  )
}
