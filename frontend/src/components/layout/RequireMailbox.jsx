import { Navigate, useSearchParams, useLocation } from 'react-router-dom'
import { useMe } from '../../api/auth'
import { useUserMailbox } from '../../api/userMailbox'
import { getActiveMailboxId } from '../../utils/mailbox'

export default function RequireMailbox({ children }) {
  const { data: auth } = useMe()
  const { data: userMailbox, isLoading } = useUserMailbox()
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const mailboxId = getActiveMailboxId(searchParams)

  const isUserRole = auth?.user?.role === 'user'
  if (isUserRole && !mailboxId) {
    if (isLoading) {
      return (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', color: '#9CA3AF', fontFamily: 'sans-serif' }}>
          Loading...
        </div>
      )
    }
    if (userMailbox?.id) {
      const target = `/mail/${userMailbox.id}${location.pathname}`
      return <Navigate to={target} replace />
    }
  }

  return children
}
