import AdminUserManagement from '../../../pages/AdminUserManagement'
import { useMe } from '../../../api/auth'
import SuperadminUserManagement from '../../../pages/SuperadminUserManagement'

export default function Users() {
  const { data: me } = useMe()
  const isSuper = me?.user?.role === 'superadmin'

  if (isSuper) return <SuperadminUserManagement />
  return <AdminUserManagement />
}
