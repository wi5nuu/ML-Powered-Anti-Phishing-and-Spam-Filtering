import GmailShell from '../components/layout/GmailShell'
import EmailList from '../components/inbox/EmailList'
import { useWebSocket } from '../hooks/useWebSocket'

export default function InboxPage() {
  useWebSocket()
  return (
    <GmailShell>
      <EmailList />
    </GmailShell>
  )
}
