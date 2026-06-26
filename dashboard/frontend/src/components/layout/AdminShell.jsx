import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMe, useLogout } from '../../api/auth'
import { Shield, Users, Activity, LogOut, Menu, Sun, Moon, BarChart2, AlertCircle } from 'lucide-react'
import { useTheme } from '../../hooks/useTheme'
import styles from './AdminShell.module.css'

export default function AdminShell({ children }) {
  const { theme, toggle } = useTheme()
  const { data: me } = useMe()
  const { mutate: logout } = useLogout()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = searchParams.get('tab') || 'overview'
  const navigate = useNavigate()
  const user = me?.user

  const navTo = (tab) => setSearchParams({ tab })

  const navItem = (tab, icon, label) => (
    <button
      className={`${styles.navItem} ${activeTab === tab ? styles.active : ''}`}
      onClick={() => navTo(tab)}
    >
      {icon}
      {sidebarOpen && <span>{label}</span>}
    </button>
  )

  return (
    <div className={styles.shell}>
      <aside className={`${styles.sidebar} ${sidebarOpen ? '' : styles.collapsed}`}>
        <div className={styles.brand}>
          <Shield size={22} />
          {sidebarOpen && <span>Admin Panel</span>}
        </div>

        <nav className={styles.nav}>
          {navItem('overview', <BarChart2 size={18} />, 'Overview')}
          {navItem('users', <Users size={18} />, 'Users')}
          {navItem('activity', <Activity size={18} />, 'Aktivitas')}
          {navItem('reports', <AlertCircle size={18} />, 'Laporan')}
        </nav>

        <div className={styles.spacer} />

        <button className={styles.backBtn} onClick={() => navigate('/inbox')}>
          {sidebarOpen ? 'Kembali ke Dashboard' : '←'}
        </button>
      </aside>

      <main className={styles.main}>
        <header className={styles.topbar}>
          <button className={styles.toggleBtn} onClick={() => setSidebarOpen((v) => !v)}>
            <Menu size={20} />
          </button>
          <div className={styles.topRight}>
            <button className={styles.themeBtn} onClick={toggle}>
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <span className={styles.userBadge}>{user?.username}</span>
            <button className={styles.logoutBtn} onClick={() => logout()}>
              <LogOut size={16} />
            </button>
          </div>
        </header>
        <div className={styles.content}>
          {children}
        </div>
      </main>
    </div>
  )
}
