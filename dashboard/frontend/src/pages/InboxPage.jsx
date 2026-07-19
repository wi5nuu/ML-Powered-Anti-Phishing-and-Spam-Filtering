import GmailShell from '../components/layout/GmailShell'
import EmailList from '../components/inbox/EmailList'
import { useWebSocket } from '../hooks/useWebSocket'
import { Navigate, useSearchParams } from 'react-router-dom'
import { getActiveMailbox, getActiveMailboxId, withMailbox } from '../utils/mailbox'

export default function InboxPage({ view = '' }) {
  useWebSocket()
  const [searchParams] = useSearchParams()
  const folder = view || searchParams.get('folder')
  if (folder === 'draft') {
    return (
      <Navigate
        to={withMailbox('/draft', getActiveMailbox(searchParams), getActiveMailboxId(searchParams))}
        replace
      />
    )
  }
  return (
    <GmailShell>
      <EmailList view={view} />
    </GmailShell>
  )
}
