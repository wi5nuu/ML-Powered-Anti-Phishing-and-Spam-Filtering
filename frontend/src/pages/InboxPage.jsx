import GmailShell from '../components/layout/GmailShell'
import EmailList from '../components/inbox/EmailList'
import { useWebSocket } from '../hooks/useWebSocket'
import { Navigate, useSearchParams } from 'react-router-dom'
import { useMe } from '../api/auth'
import { useUserMailbox } from '../api/userMailbox'
import { getActiveMailbox, getActiveMailboxId, withMailbox } from '../utils/mailbox'

export default function InboxPage({ view = '' }) {
  useWebSocket()
  const { data: auth } = useMe()
  const { data: userMailbox, isLoading } = useUserMailbox()
  const [searchParams] = useSearchParams()
  const mailboxId = getActiveMailboxId(searchParams)
  const isUserRole = auth?.user?.role === 'user'

  const folder = view || searchParams.get('folder')
  if (folder === 'draft') {
    return (
      <Navigate
        to={withMailbox('/draft', getActiveMailbox(searchParams), getActiveMailboxId(searchParams))}
        replace
      />
    )
  }

  if (isUserRole && !mailboxId) {
    if (isLoading) {
      return (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', color: '#9CA3AF', fontFamily: 'sans-serif', flexDirection: 'column', gap: 12 }}>
          <div style={{ width: 32, height: 32, border: '3px solid #E5E7EB', borderTop: '3px solid #6366F1', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
          Memuat mailbox...
        </div>
      )
    }
    if (userMailbox?.id) {
      return <Navigate to={`/mail/${userMailbox.id}/inbox`} replace />
    }
    // No mailbox assigned to this user
    return (
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100vh', gap: 16, fontFamily: 'Google Sans, Roboto, sans-serif', color: '#374151', background: '#F9FAFB' }}>
        <div style={{ fontSize: 48 }}>📭</div>
        <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600 }}>Mailbox belum tersedia</h2>
        <p style={{ margin: 0, color: '#6B7280', fontSize: '0.9rem', textAlign: 'center', maxWidth: 340 }}>
          Akun Anda belum memiliki mailbox yang terhubung. Hubungi administrator untuk mendapatkan akses.
        </p>
        <a href="/dashboard" style={{ marginTop: 8, padding: '10px 24px', background: '#6366F1', color: '#fff', borderRadius: 8, textDecoration: 'none', fontWeight: 500, fontSize: '0.9rem' }}>
          Ke Dashboard
        </a>
      </div>
    )
  }

  return (
    <GmailShell>
      <EmailList view={view} />
    </GmailShell>
  )
}
