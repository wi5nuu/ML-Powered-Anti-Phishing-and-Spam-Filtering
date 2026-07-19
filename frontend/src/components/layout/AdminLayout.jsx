import { useState } from 'react'
import { useNavigate, useLocation, Outlet } from 'react-router-dom'
import { useMe, useLogout } from '../../api/auth'
import {
  Shield, Users, Activity, LogOut, BarChart2, AlertCircle,
  Mail, Settings, ChevronRight, Bell, Server, Menu, X,
  Home, FileText, Building2, MapPin, TrendingUp, ShieldAlert
} from 'lucide-react'
import styles from './AdminShell.module.css'

export default function AdminLayout() {
  const { data: me } = useMe()
  const { mutate: logout } = useLogout()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const location = useLocation()
  const navigate = useNavigate()
  const user = me?.user
  const isSuper = user?.role === 'superadmin'

  const pathParts = location.pathname.split('/').filter(Boolean)
  const basePath = isSuper ? '/superadmin' : '/admin'
  const activeTab = pathParts[1] || 'overview'

  const navItems = []

  const addNav = (tab, icon, label, section) => {
    const roles = section?.roles || ['superadmin', 'admin']
    if (!roles.includes(user?.role)) return
    if (section?.name && navItems.find(n => n.section === section.name)) return
    navItems.push({ tab, icon, label, section: section?.name, sectionFirst: section?.first })
  }

  addNav('overview', <BarChart2 size={17} />, 'Overview', { name: 'main', first: true })
  if (isSuper) addNav('tracking', <MapPin size={17} />, 'Tracking', { name: 'main' })
  addNav('users', <Users size={17} />, 'Users', { name: 'main' })
  if (isSuper) addNav('mailboxes', <Mail size={17} />, 'Mailboxes', { name: 'main' })

  addNav('reports', <AlertCircle size={17} />, 'Reports', { name: 'security', first: true })
  addNav('activity', <Activity size={17} />, 'Activity', { name: 'security' })
  if (isSuper) addNav('companies', <Building2 size={17} />, 'Companies', { name: 'security' })
  if (isSuper) addNav('spamstats', <TrendingUp size={17} />, 'Spam Stats', { name: 'security' })
  addNav('quarantine', <ShieldAlert size={17} />, 'Quarantine', { name: 'security' })
  addNav('detection', <Shield size={17} />, 'Detection Logs', { name: 'security' })

  addNav('health', <Server size={17} />, 'System Health', { name: 'system', first: true })
  addNav('settings', <Settings size={17} />, 'Settings', { name: 'system' })

  let lastSection = ''
  const sectionLabels = { main: 'MAIN', security: 'SECURITY', system: 'SYSTEM' }

  const initials = (user?.username || 'A').slice(0, 2).toUpperCase()
  const roleColor = isSuper ? '#7C3AED' : '#2563EB'

  const navTo = (tab) => navigate(`/${basePath}/${tab}`)

  return (
    <div className={styles.shell}>
      <aside className={`${styles.sidebar} ${!sidebarOpen ? styles.collapsed : ''}`}>
        <div className={styles.brand}>
          <div className={styles.brandIcon}>
            <Shield size={18} strokeWidth={2.5} />
          </div>
          {sidebarOpen && (
            <div className={styles.brandText}>
              <span className={styles.brandName}>CogniMail</span>
              <span className={styles.brandSub}>Security Platform</span>
            </div>
          )}
          <button
            className={styles.collapseBtn}
            onClick={() => setSidebarOpen(v => !v)}
            title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
          </button>
        </div>

        <nav className={styles.nav}>
          {navItems.map((item) => {
            let sectionLabel = null
            if (item.section && item.section !== lastSection) {
              lastSection = item.section
              sectionLabel = sidebarOpen
                ? <div key={`label-${item.section}`} className={styles.sectionLabel}>{sectionLabels[item.section]}</div>
                : <div key={`label-${item.section}`} className={styles.sectionDivider} />
            }

            const isActive = activeTab === item.tab

            return (
              <div key={item.tab}>
                {sectionLabel}
                <button
                  className={`${styles.navItem} ${isActive ? styles.navItemActive : ''}`}
                  onClick={() => navTo(item.tab)}
                  title={!sidebarOpen ? item.label : undefined}
                >
                  <span className={`${styles.navIcon} ${isActive ? styles.navIconActive : ''}`}>{item.icon}</span>
                  {sidebarOpen && <span className={styles.navLabel}>{item.label}</span>}
                  {sidebarOpen && isActive && <ChevronRight size={14} className={styles.navChevron} />}
                </button>
              </div>
            )
          })}
        </nav>

        <div className={styles.spacer} />

        <button
          className={styles.backBtn}
          onClick={() => navigate(`/${basePath}/overview`)}
          title="Back to Dashboard"
        >
          <Home size={16} />
          {sidebarOpen && <span>Home</span>}
        </button>
      </aside>

      <main className={styles.main}>
        <header className={styles.topbar}>
          <div className={styles.topLeft}>
            <div className={styles.breadcrumb}>
              <Shield size={15} className={styles.breadcrumbIcon} />
              <span className={styles.breadcrumbRoot}>Admin Panel</span>
              <ChevronRight size={13} className={styles.breadcrumbSep} />
              <span className={styles.breadcrumbCurrent}>
                {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
              </span>
            </div>
          </div>

          <div className={styles.topRight}>
            <button className={styles.topBtn} title="Notifications">
              <Bell size={17} />
            </button>
            <div className={styles.userChip}>
              <div className={styles.avatar} style={{ background: roleColor }}>
                {initials}
              </div>
              <div className={styles.userInfo}>
                <span className={styles.userName}>{user?.username}</span>
              </div>
            </div>
            <button className={styles.logoutBtn} onClick={() => logout()} title="Logout">
              <LogOut size={16} />
            </button>
          </div>
        </header>

        <div className={styles.content}>
          <Outlet />
        </div>
      </main>
    </div>
  )
}
