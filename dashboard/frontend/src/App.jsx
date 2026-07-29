import { useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useMe } from './api/auth'
import api from './api/client'
import { useWebSocket } from './hooks/useWebSocket'
import { I18nProvider } from './i18n/context'
import LoginPage from './pages/LoginPage'
import MailboxLoginPage from './pages/MailboxLoginPage'
import InboxPage from './pages/InboxPage'
import EmailDetailPage from './pages/EmailDetailPage'
import HelpPage from './pages/HelpPage'
import StarredPage from './pages/StarredPage'
import SentPage from './pages/SentPage'
import DraftPage from './pages/DraftPage'
import AnalyzerPage from './pages/AnalyzerPage'
import MetricsPage from './pages/MetricsPage'
import SettingsPage from './pages/SettingsPage'
import ProfilePage from './pages/ProfilePage'
import AdminPage from './pages/AdminPage'
import RequireMailbox from './components/layout/RequireMailbox'
import UserDashboardShell from './components/layout/UserDashboardShell'
import UserMailboxPage from './pages/UserMailboxPage'
import UserDashboardPage from './pages/UserDashboardPage'
import SuperadminTrainingPage from './pages/SuperadminTrainingPage'
import { removeMailboxLocalState } from './utils/mailbox'

function dashboardPathForRole(role) {
  if (role === 'superadmin') return '/super-admin/dashboard'
  if (role === 'admin') return '/admin/dashboard'
  if (role === 'user') return '/user/dashboard'
  if (role === 'mailbox') return '/login'
  return '/login'
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
  const mailboxNotificationsEnabled = data?.authenticated && data?.user?.role === 'mailbox'
  useWebSocket({
    enabled: mailboxNotificationsEnabled,
    mailboxEmail: data?.user?.mailbox_email || '',
  })
  const location = useLocation()
  const mailboxPath = location.pathname.match(/^\/mail\/([^/]+)\//)
  const routeMailboxId = mailboxPath?.[1] ? decodeURIComponent(mailboxPath[1]) : ''
  const requestedFolder = new URLSearchParams(location.search).get('folder') || ''
  const requestedCategory = new URLSearchParams(location.search).get('category') || ''
  const requestsTrash = /\/mail\/[^/]+\/trash\/?$/.test(location.pathname)
    || requestedFolder.toLowerCase() === 'trash'
  const requestsThreatReview = /\/mail\/[^/]+\/(?:spam|phishing|warn|malware)\/?$/.test(location.pathname)
    || ['spam', 'phishing', 'warn', 'malware'].includes(requestedCategory.toLowerCase())
  const shouldValidateMailbox = Boolean(data?.authenticated && routeMailboxId)
  const mailboxAccess = useQuery({
    queryKey: ['mailbox-access', routeMailboxId],
    queryFn: async () => {
      const { data: result } = await api.get(`/mailboxes/${encodeURIComponent(routeMailboxId)}/access`)
      return result
    },
    enabled: shouldValidateMailbox,
    retry: (failureCount, error) => {
      const status = error?.response?.status
      return failureCount < 2 && (!status || status >= 500)
    },
    staleTime: 0,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  })

  const mailboxAccessStatus = mailboxAccess.error?.response?.status
  const mailboxIsGone = [403, 404, 410].includes(mailboxAccessStatus)

  useEffect(() => {
    if (routeMailboxId && mailboxIsGone) removeMailboxLocalState(routeMailboxId)
  }, [routeMailboxId, mailboxIsGone])

  if (isLoading || (shouldValidateMailbox && mailboxAccess.isLoading)) {
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

  if (
    data?.authenticated
    && (requestsTrash || requestsThreatReview)
    && !['admin', 'superadmin'].includes(data?.user?.role)
  ) {
    const target = routeMailboxId
      ? `/mail/${encodeURIComponent(routeMailboxId)}/inbox`
      : '/inbox'
    return <Navigate to={target} replace />
  }

  if (shouldValidateMailbox && mailboxIsGone) {
    const role = data?.user?.role
    if (role === 'superadmin' || role === 'admin') {
      return <Navigate to={`${dashboardPathForRole(role)}?tab=email&mailbox=not-found`} replace />
    }
    return <Navigate to={`/mail/${encodeURIComponent(routeMailboxId)}/login?removed=1`} replace />
  }

  if (shouldValidateMailbox && mailboxAccess.isError) {
    if (mailboxAccessStatus === 401) return <Navigate to="/login" replace />
    return (
      <div style={{ display: 'grid', placeItems: 'center', minHeight: '100vh', padding: 24, background: 'var(--bg)', color: 'var(--text)', fontFamily: 'Google Sans, Roboto, sans-serif' }}>
        <div style={{ textAlign: 'center' }}>
          <p>Mailbox sementara tidak dapat diverifikasi. Sesi Anda tidak dihapus.</p>
          <button type="button" onClick={() => mailboxAccess.refetch()} style={{ padding: '9px 14px', borderRadius: 8, border: 0, background: '#1a73e8', color: '#fff', cursor: 'pointer' }}>Coba lagi</button>
        </div>
      </div>
    )
  }

  if (shouldValidateMailbox && mailboxAccess.data?.ok) return children

  if (data?.authenticated) {
    const role = data?.user?.role
    if (role === 'mailbox') return children
    if (role === 'user') return children
    if (role === 'superadmin' || role === 'admin') {
      // Allow admin/superadmin through on email detail routes and /mail/:mailboxId/* webmail routes
      const isMailboxRoute = /\/mail\/[^/]+/.test(location.pathname)
      const isEmailDetailRoute = /\/email\/[^/]+/.test(location.pathname)
      if (isEmailDetailRoute || isMailboxRoute) return children
      return <Navigate to={`${dashboardPathForRole(role)}?tab=email`} replace />
    }
    return children
  }

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

function AdminRoute({ children, scope }) {
  const { data, isLoading } = useMe()
  const [searchParams] = useSearchParams()

  if (isLoading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', fontFamily: 'Google Sans, Roboto, sans-serif', color: 'var(--text-muted)', backgroundColor: 'var(--bg)' }}>Memeriksa autentikasi...</div>
  if (!data?.authenticated) return <Navigate to="/login" replace />

  const role = data?.user?.role
  if (role !== 'superadmin' && role !== 'admin') {
    return <Navigate to={dashboardPathForRole(role)} replace />
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

function LegacyMalwareRedirect() {
  const { mailboxId } = useParams()
  const location = useLocation()
  return <Navigate to={`/mail/${encodeURIComponent(mailboxId)}/phishing${location.search}`} replace />
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
      <I18nProvider>
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
        <Route path="/mail/:mailboxId/warn" element={<MailboxRoute><InboxPage view="warn" /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/malware" element={<MailboxRoute><LegacyMalwareRedirect /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/profile" element={<MailboxRoute><ProfilePage /></MailboxRoute>} />
        <Route path="/mail/:mailboxId/email/:emailId" element={<MailboxRoute><EmailDetailPage /></MailboxRoute>} />
        <Route path="/help" element={<ProtectedRoute><HelpPage /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        {/* /audit route removed - audit logs now accessed via admin dashboard tab */}
        <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
        <Route path="/starred" element={<RequireMailbox><MailboxRoute><StarredPage /></MailboxRoute></RequireMailbox>} />
        <Route path="/sent" element={<RequireMailbox><MailboxRoute><SentPage /></MailboxRoute></RequireMailbox>} />
        <Route path="/draft" element={<RequireMailbox><MailboxRoute><DraftPage /></MailboxRoute></RequireMailbox>} />
        <Route path="/analyzer" element={<ProtectedRoute><AnalyzerPage /></ProtectedRoute>} />
        <Route path="/metrics" element={<ProtectedRoute><MetricsPage /></ProtectedRoute>} />

        {/* User routes */}
        <Route path="/user/dashboard" element={<UserRoute><UserDashboardShell><UserDashboardPage /></UserDashboardShell></UserRoute>} />
        <Route path="/user/mailboxes" element={<UserRoute><UserMailboxPage /></UserRoute>} />

        {/* Admin routes — split URL by role */}
        <Route path="/admin" element={<RoleRedirect />} />
        <Route path="/super-admin" element={<RoleRedirect />} />
        <Route path="/super-admin/dashboard" element={<AdminRoute scope="superadmin"><AdminPage /></AdminRoute>} />
        <Route path="/super-admin/training" element={<AdminRoute scope="superadmin"><SuperadminTrainingPage /></AdminRoute>} />
        <Route path="/admin/dashboard" element={<AdminRoute scope="admin"><AdminPage /></AdminRoute>} />

        {/* Fallback — redirect based on role */}
        <Route path="*" element={<RoleRedirect />} />
      </Routes>
      </I18nProvider>
    </Router>
  )
}
