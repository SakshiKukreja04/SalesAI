import { useState } from 'react'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'

import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import { useAuth } from './context/AuthContext'
import AnalyticsPage from './pages/analytics'
import DashboardPage from './pages/Dashboard'
import EmailsPage from './pages/emails'
import HomePage from './pages/home'
import IntentView from './pages/intent/IntentView'
import LoginPage from './pages/login'
import SignupPage from './pages/signup'
import TeamManagementPage from './pages/team'

function FullPageLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-300 border-t-slate-900" />
    </div>
  )
}

function ProtectedRoute({ children }) {
  const { isAuthenticated, isInviteValidated, loading } = useAuth()

  if (loading) {
    return <FullPageLoader />
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (!isInviteValidated) {
    return <Navigate to="/signup" replace />
  }

  return children
}

function AdminRoute({ children }) {
  const { isAdmin } = useAuth()
  if (!isAdmin) {
    return <Navigate to="/dashboard" replace />
  }
  return children
}

function AppLayout() {
  const [sidebarExpanded, setSidebarExpanded] = useState(true)
  const { isAdmin, profile } = useAuth()

  return (
    <div className="flex min-h-screen bg-slate-100">
      <Sidebar
        isAdmin={isAdmin}
        assignedIntents={profile.assignedIntents}
        expanded={sidebarExpanded}
        onToggle={() => setSidebarExpanded((prev) => !prev)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="min-h-0 flex-1 overflow-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/emails" element={<EmailsPage />} />
        <Route path="/intent/:intent" element={<IntentView />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route
          path="/team"
          element={
            <AdminRoute>
              <TeamManagementPage />
            </AdminRoute>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
