import { BrowserRouter as Router, Routes, Route, Navigate, useSearchParams } from 'react-router-dom'
import { useMe } from './api/auth'
import LoginPage from './pages/LoginPage'
import MailboxLoginPage from './pages/MailboxLoginPage'
import InboxPage from './pages/InboxPage'
import EmailDetailPage from './pages/EmailDetailPage'
import MetricsPage from './pages/MetricsPage'
import HelpPage from './pages/HelpPage'
import StarredPage from './pages/StarredPage'
import SentPage from './pages/SentPage'
import SnoozedPage from './pages/SnoozedPage'
import DraftPage from './pages/DraftPage'
import PembelianPage from './pages/PembelianPage'
import AnalyzerPage from './pages/AnalyzerPage'
import SettingsPage from './pages/SettingsPage'
import AuditPage from './pages/AuditPage'
import ProfilePage from './pages/ProfilePage'
import AdminPage from './pages/AdminPage'
import { hasMailboxSessionFromSearch } from './utils/mailbox'

function dashboardPathForRole(role) {
  if (role === 'superadmin') return '/super-admin/dashboard'
  if (role === 'admin') return '/admin/dashboard'
  return '/inbox'
}

function ProtectedRoute({ children }) {
  const { data, isLoading } = useMe()
  const [searchParams] = useSearchParams()

  if (isLoading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        fontFamily: 'Google Sans, Roboto, sans-serif',
        color: 'var(--text-muted)',
        backgroundColor: 'var(--bg)'
      }}>
        Memeriksa autentikasi...
      </div>
    )
  }

  if (!data?.authenticated && !hasMailboxSessionFromSearch(searchParams)) {
    return <Navigate to="/login" replace />
  }

  return children
}

function MailboxRoute({ children }) {
  const { data, isLoading } = useMe()
  const [searchParams] = useSearchParams()

  if (isLoading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        fontFamily: 'Google Sans, Roboto, sans-serif',
        color: 'var(--text-muted)',
        backgroundColor: 'var(--bg)'
      }}>
        Memeriksa autentikasi...
      </div>
    )
  }

  if (hasMailboxSessionFromSearch(searchParams)) return children

  if (data?.authenticated) {
    const role = data?.user?.role
    if (role === 'superadmin' || role === 'admin') {
      return <Navigate to={`${dashboardPathForRole(role)}?tab=email`} replace />
    }
    return children
  }

  return <Navigate to="/login" replace />
}

function UserRoute({ children }) {
  const { data, isLoading } = useMe()
  const [searchParams] = useSearchParams()

  if (isLoading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', fontFamily: 'Google Sans, Roboto, sans-serif', color: 'var(--text-muted)', backgroundColor: 'var(--bg)' }}>Memeriksa autentikasi...</div>
  if (!data?.authenticated && !hasMailboxSessionFromSearch(searchParams)) return <Navigate to="/login" replace />
  if (!data?.authenticated) return children

  const role = data?.user?.role
  if (role === 'superadmin' || role === 'admin') {
    return <Navigate to={dashboardPathForRole(role)} replace />
  }

  return children
}

function AdminRoute({ children, scope }) {
  const { data, isLoading } = useMe()
  const [searchParams] = useSearchParams()

  if (isLoading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', fontFamily: 'Google Sans, Roboto, sans-serif', color: 'var(--text-muted)', backgroundColor: 'var(--bg)' }}>Memeriksa autentikasi...</div>
  if (!data?.authenticated) return <Navigate to="/login" replace />

  const role = data?.user?.role
  if (role !== 'superadmin' && role !== 'admin') {
    return <Navigate to="/inbox" replace />
  }

  const correctPath = dashboardPathForRole(role)
  const qs = searchParams.toString()
  if ((scope === 'superadmin' && role !== 'superadmin') || (scope === 'admin' && role !== 'admin')) {
    return <Navigate to={qs ? `${correctPath}?${qs}` : correctPath} replace />
  }

  return children
}

function RootRoute() {
  const { data, isLoading } = useMe()
  const [searchParams] = useSearchParams()
  if (isLoading) return null
  if (data?.authenticated) {
    const role = data?.user?.role
    const target = dashboardPathForRole(role)
    const qs = searchParams.toString()
    return <Navigate to={qs ? `${target}?${qs}` : target} replace />
  }
  return <Navigate to="/login" replace />
}

function RoleRedirect() {
  const { data, isLoading } = useMe()
  const [searchParams] = useSearchParams()
  if (isLoading) return null
  if (!data?.authenticated) return <Navigate to="/login" replace />
  const role = data?.user?.role
  const target = dashboardPathForRole(role)
  const qs = searchParams.toString()
  return <Navigate to={qs ? `${target}?${qs}` : target} replace />
}

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<RootRoute />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/mailbox-login" element={<MailboxLoginPage />} />

        {/* User routes — only for non-admin users */}
        <Route path="/inbox" element={<MailboxRoute><InboxPage /></MailboxRoute>} />
        <Route path="/email/:emailId" element={<MailboxRoute><EmailDetailPage /></MailboxRoute>} />
        <Route path="/metrics" element={<ProtectedRoute><MetricsPage /></ProtectedRoute>} />
        <Route path="/help" element={<ProtectedRoute><HelpPage /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        <Route path="/audit" element={<AdminRoute><AuditPage /></AdminRoute>} />
        <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
        <Route path="/starred" element={<MailboxRoute><StarredPage /></MailboxRoute>} />
        <Route path="/sent" element={<MailboxRoute><SentPage /></MailboxRoute>} />
        <Route path="/snoozed" element={<MailboxRoute><SnoozedPage /></MailboxRoute>} />
        <Route path="/draft" element={<MailboxRoute><DraftPage /></MailboxRoute>} />
        <Route path="/pembelian" element={<MailboxRoute><PembelianPage /></MailboxRoute>} />
        <Route path="/analyzer" element={<ProtectedRoute><AnalyzerPage /></ProtectedRoute>} />

        {/* User dashboard route no longer used for regular users; redirect to inbox */}
        <Route path="/dashboard" element={<RoleRedirect />} />

        {/* Admin routes — split URL by role */}
        <Route path="/admin" element={<RoleRedirect />} />
        <Route path="/super-admin" element={<RoleRedirect />} />
        <Route path="/super-admin/dashboard" element={<AdminRoute scope="superadmin"><AdminPage /></AdminRoute>} />
        <Route path="/admin/dashboard" element={<AdminRoute scope="admin"><AdminPage /></AdminRoute>} />

        {/* Fallback — redirect based on role */}
        <Route path="*" element={<RoleRedirect />} />
      </Routes>
    </Router>
  )
}
