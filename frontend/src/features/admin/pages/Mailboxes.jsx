import { useMe } from '../../../api/auth'
import SuperadminMailboxManagement from '../../../pages/SuperadminMailboxManagement'
import AdminMailboxManagement from '../../../pages/AdminMailboxManagement'

export default function Mailboxes() {
  const { data: me } = useMe()
  const isSuper = me?.user?.role === 'superadmin'

  if (isSuper) return <SuperadminMailboxManagement />
  return <AdminMailboxManagement />
}
