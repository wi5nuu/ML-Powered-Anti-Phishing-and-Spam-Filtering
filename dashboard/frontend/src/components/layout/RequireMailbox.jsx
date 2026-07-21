import { Navigate, useLocation, useParams } from 'react-router-dom'
import { getMailboxSession } from '../../utils/mailbox'

/**
 * RequireMailbox — protects mailbox routes.
 *
 * When used inside a /mail/:mailboxId/* route, extracts mailboxId from URL params.
 * Falls back to the mailboxId prop when provided explicitly.
 * Redirects to the mailbox login page if no valid session exists.
 */
export default function RequireMailbox({ children, mailboxId: mailboxIdProp }) {
  const location = useLocation()
  const params = useParams()

  // Prefer URL param over prop (works for /mail/:mailboxId/* routes)
  const mailboxId = params.mailboxId || mailboxIdProp || ''

  // For legacy routes without a mailboxId in the URL, check any active session
  if (!mailboxId) {
    // Try to extract from pathname e.g. /mail/some-id/inbox
    const match = location.pathname.match(/^\/mail\/([^/]+)/)
    const idFromPath = match ? decodeURIComponent(match[1]) : ''
    if (!idFromPath || !getMailboxSession(idFromPath)) {
      return <Navigate to="/login" state={{ from: location }} replace />
    }
    return children
  }

  if (!getMailboxSession(mailboxId)) {
    const loginPath = `/mail/${encodeURIComponent(mailboxId)}/login`
    return <Navigate to={loginPath} state={{ from: location }} replace />
  }

  return children
}
