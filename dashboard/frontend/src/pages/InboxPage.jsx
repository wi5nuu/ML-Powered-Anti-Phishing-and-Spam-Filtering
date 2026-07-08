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
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', color: '#9CA3AF', fontFamily: 'sans-serif' }}>
          Loading mailbox...
        </div>
      )
    }
    if (userMailbox?.id) {
      return <Navigate to={`/mail/${userMailbox.id}/inbox`} replace />
    }
  }

  return (
    <GmailShell>
      <EmailList view={view} />
    </GmailShell>
  )
}
