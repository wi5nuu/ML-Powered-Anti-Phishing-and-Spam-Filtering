import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMe, useLogout } from '../../api/auth'
import {
  Shield, Users, Activity, LogOut, BarChart2, AlertCircle,
  Mail, Settings, ChevronRight, Bell, Server, Menu, X,
  Home, FileText, Lock
} from 'lucide-react'
import styles from './AdminShell.module.css'

export default function AdminShell({ children }) {
  const { data: me } = useMe()
  const { mutate: logout } = useLogout()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = searchParams.get('tab') || 'overview'
  const navigate = useNavigate()
  const user = me?.user
  const isSuper = user?.role === 'superadmin'
  const roleLabelMap = { superadmin: 'Superadmin', admin: 'Admin', user: 'User' }
  const roleColorMap = { superadmin: '#7C3AED', admin: '#2563EB', user: '#059669' }
  const roleLabel = roleLabelMap[user?.role] || user?.role
  const roleColor = roleColorMap[user?.role] || '#2563EB'
  const dashboardPath = isSuper ? '/super-admin/dashboard' : '/admin/dashboard'

  const navTo = (tab) => setSearchParams({ tab })

  const NavItem = ({ tab, icon, label, section }) => {
    const isActive = activeTab === tab
    return (
      <button
        className={`${styles.navItem} ${isActive ? styles.navItemActive : ''}`}
        onClick={() => navTo(tab)}
        title={!sidebarOpen ? label : undefined}
      >
        <span className={`${styles.navIcon} ${isActive ? styles.navIconActive : ''}`}>{icon}</span>
        {sidebarOpen && <span className={styles.navLabel}>{label}</span>}
        {sidebarOpen && isActive && <ChevronRight size={14} className={styles.navChevron} />}
      </button>
    )
  }

  const SectionLabel = ({ label }) =>
    sidebarOpen ? <div className={styles.sectionLabel}>{label}</div> : <div className={styles.sectionDivider} />

  const initials = (user?.username || 'A').slice(0, 2).toUpperCase()

  return (
    <div className={styles.shell}>
      {/* Sidebar */}
      <aside className={`${styles.sidebar} ${!sidebarOpen ? styles.collapsed : ''}`}>
        {/* Brand */}
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

        {/* Role badge */}
        {sidebarOpen && (
          <div className={styles.rolePill} style={{ background: `${roleColor}15`, borderColor: `${roleColor}30` }}>
            <span className={styles.roleDot} style={{ background: roleColor }} />
            <span className={styles.roleText} style={{ color: roleColor }}>{roleLabel}</span>
          </div>
        )}

        {/* Nav */}
        <nav className={styles.nav}>
          <SectionLabel label="MAIN" />
          <NavItem tab="overview" icon={<BarChart2 size={17} />} label="Overview" />
          {isSuper && <NavItem tab="users" icon={<Users size={17} />} label="Users" />}
          <NavItem tab="email" icon={<Mail size={17} />} label="Mailboxes" />

          <SectionLabel label="SECURITY" />
          <NavItem tab="reports" icon={<AlertCircle size={17} />} label="Reports" />
          <NavItem tab="activity" icon={<Activity size={17} />} label="Security Activity" />

          <SectionLabel label="SYSTEM" />
          {isSuper && <NavItem tab="health" icon={<Server size={17} />} label="System Health" />}
          <NavItem tab="settings" icon={<Settings size={17} />} label="Settings" />
        </nav>

        <div className={styles.spacer} />

        {/* Back to Dashboard */}
        <button
          className={styles.backBtn}
          onClick={() => navigate(dashboardPath)}
          title="Back to Dashboard"
        >
          <Home size={16} />
          {sidebarOpen && <span>Back to Dashboard</span>}
        </button>
      </aside>

      {/* Main */}
      <main className={styles.main}>
        {/* Topbar */}
        <header className={styles.topbar}>
          <div className={styles.topLeft}>
            <div className={styles.breadcrumb}>
              <Shield size={15} className={styles.breadcrumbIcon} />
              <span className={styles.breadcrumbRoot}>{isSuper ? 'Superadmin' : 'Admin'}</span>
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
                <span className={styles.userRole} style={{ color: roleColor }}>{roleLabel}</span>
              </div>
            </div>
            <button className={styles.logoutBtn} onClick={() => logout()} title="Logout">
              <LogOut size={16} />
            </button>
          </div>
        </header>

        {/* Content */}
        <div className={styles.content}>
          {children}
        </div>
      </main>
    </div>
  )
}
