import { useMe } from '../../../api/auth'
import SuperadminSettingsPage from '../../../pages/SuperadminSettings'
import AdminSettingsPage from '../../../pages/AdminSettings'

export default function Settings() {
  const { data: me } = useMe()
  const isSuper = me?.user?.role === 'superadmin'

  if (isSuper) return <SuperadminSettingsPage />
  return <AdminSettingsPage />
}
