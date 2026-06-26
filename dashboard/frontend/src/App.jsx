import { BrowserRouter as Router, Routes, Route, Navigate, useSearchParams } from 'react-router-dom'
import { useMe } from './api/auth'
import WelcomePage from './pages/WelcomePage'
import LoginPage from './pages/LoginPage'
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

function ProtectedRoute({ children }) {
  const { data, isLoading } = useMe()

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

  if (!data?.authenticated) {
    return <Navigate to="/login" replace />
  }

  return children
}

function UserRoute({ children }) {
  const { data, isLoading } = useMe()

  if (isLoading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', fontFamily: 'Google Sans, Roboto, sans-serif', color: 'var(--text-muted)', backgroundColor: 'var(--bg)' }}>Memeriksa autentikasi...</div>
  if (!data?.authenticated) return <Navigate to="/login" replace />

  const role = data?.user?.role
  if (role === 'superadmin' || role === 'admin') {
    return <Navigate to="/admin" replace />
  }

  return children
}

function AdminRoute({ children }) {
  const { data, isLoading } = useMe()

  if (isLoading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', fontFamily: 'Google Sans, Roboto, sans-serif', color: 'var(--text-muted)', backgroundColor: 'var(--bg)' }}>Memeriksa autentikasi...</div>
  if (!data?.authenticated) return <Navigate to="/login" replace />

  const role = data?.user?.role
  if (role !== 'superadmin' && role !== 'admin') {
    return <Navigate to="/inbox" replace />
  }

  return children
}

function RootRoute() {
  const { data, isLoading } = useMe()
  const [searchParams] = useSearchParams()
  if (isLoading) return null
  if (data?.authenticated) {
    const role = data?.user?.role
    const target = (role === 'superadmin' || role === 'admin') ? '/admin' : '/inbox'
    const qs = searchParams.toString()
    return <Navigate to={qs ? `${target}?${qs}` : target} replace />
  }
  return <WelcomePage />
}

function RoleRedirect() {
  const { data, isLoading } = useMe()
  if (isLoading) return null
  if (!data?.authenticated) return <Navigate to="/login" replace />
  const role = data?.user?.role
  if (role === 'superadmin' || role === 'admin') return <Navigate to="/admin" replace />
  return <Navigate to="/inbox" replace />
}

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<RootRoute />} />
        <Route path="/login" element={<LoginPage />} />

        {/* User routes — only for non-admin users */}
        <Route path="/inbox" element={<UserRoute><InboxPage /></UserRoute>} />
        <Route path="/email/:emailId" element={<UserRoute><EmailDetailPage /></UserRoute>} />
        <Route path="/metrics" element={<ProtectedRoute><MetricsPage /></ProtectedRoute>} />
        <Route path="/help" element={<ProtectedRoute><HelpPage /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        <Route path="/audit" element={<AdminRoute><AuditPage /></AdminRoute>} />
        <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
        <Route path="/starred" element={<UserRoute><StarredPage /></UserRoute>} />
        <Route path="/sent" element={<UserRoute><SentPage /></UserRoute>} />
        <Route path="/snoozed" element={<UserRoute><SnoozedPage /></UserRoute>} />
        <Route path="/draft" element={<UserRoute><DraftPage /></UserRoute>} />
        <Route path="/pembelian" element={<UserRoute><PembelianPage /></UserRoute>} />
        <Route path="/analyzer" element={<UserRoute><AnalyzerPage /></UserRoute>} />

        {/* Admin route — only for superadmin/admin */}
        <Route path="/admin" element={<AdminRoute><AdminPage /></AdminRoute>} />

        {/* Fallback — redirect based on role */}
        <Route path="*" element={<RoleRedirect />} />
      </Routes>
    </Router>
  )
}
