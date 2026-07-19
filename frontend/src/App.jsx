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
import UserSettingsPage from './pages/UserSettingsPage'
import AuditPage from './pages/AuditPage'
import ProfilePage from './pages/ProfilePage'
import UserDashboardPage from './pages/UserDashboardPage'
import UserDashboardShell from './components/layout/UserDashboardShell'
import RequireMailbox from './components/layout/RequireMailbox'
import { hasMailboxSessionFromSearch } from './utils/mailbox'

import AdminLayout from './components/layout/AdminLayout'

import AdminOverview from './features/admin/pages/Overview'
import AdminUsers from './features/admin/pages/Users'
import AdminMailboxes from './features/admin/pages/Mailboxes'
import AdminDetectionLogs from './features/admin/pages/DetectionLogs'
import AdminQuarantine from './features/admin/pages/QuarantineReview'
import AdminReports from './features/admin/pages/Reports'
import AdminActivity from './features/admin/pages/ActivityLog'
import AdminSettings from './features/admin/pages/Settings'
import SuperadminOverview from './features/superadmin/pages/Overview'
import SuperadminTracking from './features/superadmin/pages/Tracking'
import SuperadminSystemHealth from './features/superadmin/pages/SystemHealth'
import SuperadminCompanies from './features/superadmin/pages/Companies'
import SuperadminSpamStats from './features/superadmin/pages/SpamStats'
import SuperadminReports from './features/superadmin/pages/Reports'

function dashboardPathForRole(role) {
  if (role === 'superadmin') return '/superadmin/overview'
  if (role === 'admin') return '/admin/overview'
  return '/inbox'
}

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
    if (role === 'mailbox') return children
    if (role === 'superadmin' || role === 'admin') {
      return <Navigate to={`${dashboardPathForRole(role)}`} replace />
    }
    return children
  }

  const mailboxPath = window.location.pathname.match(/^\/mail\/([^/]+)\//)
  if (mailboxPath?.[1]) {
    return <Navigate to={`/mail/${encodeURIComponent(mailboxPath[1])}/login`} replace />
  }

  return <Navigate to="/mailbox-login" replace />
}

function UserRoute({ children }) {
  const { data, isLoading } = useMe()

  if (isLoading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', fontFamily: 'Google Sans, Roboto, sans-serif', color: 'var(--text-muted)', backgroundColor: 'var(--bg)' }}>Memeriksa autentikasi...</div>
  if (!data?.authenticated) return <Navigate to="/login" replace />

  const role = data?.user?.role
  if (role === 'superadmin' || role === 'admin') {
    return <Navigate to={dashboardPathForRole(role)} replace />
  }
  if (role !== 'user') return <Navigate to="/login" replace />

  return children
}

function SettingsRouteHandler() {
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

  if (!data?.authenticated) return <Navigate to="/login" replace />

  const role = data?.user?.role
  const qs = searchParams.toString()

  if (role === 'admin') {
    return <Navigate to={`/admin/settings${qs ? `?${qs}` : ''}`} replace />
  }
  if (role === 'superadmin') {
    return <Navigate to={`/superadmin/settings${qs ? `?${qs}` : ''}`} replace />
  }

  return <UserDashboardShell><UserSettingsPage /></UserDashboardShell>
}

function AdminGuard({ children, scope }) {
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
    if (role === 'mailbox') return <Navigate to="/login" replace />
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
  if (role === 'mailbox') return <Navigate to="/login" replace />
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
        <Route path="/mail/:mailboxId/login" element={<MailboxLoginPage />} />

        {/* User routes — only for non-admin users */}
        <Route path="/inbox" element={<MailboxRoute><InboxPage /></MailboxRoute>} />
        <Route path="/email/:emailId" element={<MailboxRoute><EmailDetailPage /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/inbox" element={<MailboxRoute><InboxPage /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/starred" element={<MailboxRoute><InboxPage view="starred" /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/sent" element={<MailboxRoute><SentPage /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/drafts" element={<MailboxRoute><DraftPage /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/all" element={<MailboxRoute><InboxPage view="allmail" /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/trash" element={<MailboxRoute><InboxPage view="trash" /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/spam" element={<MailboxRoute><InboxPage view="spam" /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/phishing" element={<MailboxRoute><InboxPage view="phishing" /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/malware" element={<MailboxRoute><InboxPage view="malware" /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/profile" element={<MailboxRoute><ProfilePage /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/metrics" element={<MailboxRoute><MetricsPage /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/email/:emailId" element={<MailboxRoute><EmailDetailPage /></MailboxRoute>} />
        <Route path="/metrics" element={<ProtectedRoute><MetricsPage /></ProtectedRoute>} />
        <Route path="/help" element={<ProtectedRoute><HelpPage /></ProtectedRoute>} />
        <Route path="/settings" element={<SettingsRouteHandler />} />
        <Route path="/audit" element={<AdminGuard><AuditPage /></AdminGuard>} />
        <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
        <Route path="/starred" element={<RequireMailbox><MailboxRoute><StarredPage /></MailboxRoute></RequireMailbox>} />
        <Route path="/sent" element={<RequireMailbox><MailboxRoute><SentPage /></MailboxRoute></RequireMailbox>} />
        <Route path="/snoozed" element={<RequireMailbox><MailboxRoute><SnoozedPage /></MailboxRoute></RequireMailbox>} />
        <Route path="/draft" element={<RequireMailbox><MailboxRoute><DraftPage /></MailboxRoute></RequireMailbox>} />
        <Route path="/pembelian" element={<RequireMailbox><MailboxRoute><PembelianPage /></MailboxRoute></RequireMailbox>} />
        <Route path="/analyzer" element={<ProtectedRoute><AnalyzerPage /></ProtectedRoute>} />

        {/* User dashboard - redirect to inbox */}
        <Route path="/dashboard" element={<UserRoute><Navigate to="/inbox" replace /></UserRoute>} />

        {/* ── Admin Routes (proper path-based routing) ── */}
        <Route path="/admin" element={<AdminGuard><AdminLayout /></AdminGuard>}>
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<AdminOverview />} />
          <Route path="users" element={<AdminUsers />} />
          <Route path="mailboxes" element={<AdminMailboxes />} />
          <Route path="detection" element={<AdminDetectionLogs />} />
          <Route path="quarantine" element={<AdminQuarantine />} />
          <Route path="reports" element={<AdminReports />} />
          <Route path="activity" element={<AdminActivity />} />
          <Route path="settings" element={<AdminSettings />} />
        </Route>

        {/* ── Superadmin Routes ── */}
        <Route path="/superadmin" element={<AdminGuard scope="superadmin"><AdminLayout /></AdminGuard>}>
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<SuperadminOverview />} />
          <Route path="users" element={<AdminUsers />} />
          <Route path="mailboxes" element={<AdminMailboxes />} />
          <Route path="tracking" element={<SuperadminTracking />} />
          <Route path="health" element={<SuperadminSystemHealth />} />
          <Route path="companies" element={<SuperadminCompanies />} />
          <Route path="spamstats" element={<SuperadminSpamStats />} />
          <Route path="reports" element={<SuperadminReports />} />
          <Route path="detection" element={<AdminDetectionLogs />} />
          <Route path="quarantine" element={<AdminQuarantine />} />
          <Route path="activity" element={<AdminActivity />} />
          <Route path="settings" element={<AdminSettings />} />
        </Route>

        {/* Legacy redirects for backward compatibility */}
        <Route path="/admin/dashboard" element={<Navigate to="/admin/overview" replace />} />
        <Route path="/admin/dashboard/:tab" element={<LegacyTabRedirect />} />
        <Route path="/superadmin/dashboard" element={<Navigate to="/superadmin/overview" replace />} />
        <Route path="/superadmin/dashboard/:tab" element={<LegacyTabRedirect />} />
        <Route path="/super-admin" element={<Navigate to="/superadmin/overview" replace />} />
        <Route path="/super-admin/dashboard" element={<Navigate to="/superadmin/overview" replace />} />
        <Route path="/super-admin/dashboard/:tab" element={<LegacyTabRedirect />} />

        {/* Fallback — redirect based on role */}
        <Route path="*" element={<RoleRedirect />} />
      </Routes>
    </Router>
  )
}

function LegacyTabRedirect() {
  const tabMap = {
    overview: 'overview', users: 'users', email: 'mailboxes',
    review: 'quarantine', logs: 'detection',
    settings: 'settings', track: 'tracking', health: 'health',
    companies: 'companies', reports: 'reports', 'spam-stats': 'spamstats',
    activity: 'activity',
  }
  const tab = window.location.pathname.split('/').pop()
  const target = tabMap[tab] || 'overview'
  const base = window.location.pathname.includes('/superadmin') ? '/superadmin' : '/admin'
  return <Navigate to={`${base}/${target}`} replace />
}
