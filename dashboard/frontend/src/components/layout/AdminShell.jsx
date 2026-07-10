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
  const isAdmin = user?.role === 'admin'
  const roleLabelMap = { superadmin: 'Superadmin', admin: 'Admin', user: 'User' }
  const roleThemeMap = {
    superadmin: {
      accent: '#7C3AED',
      accent2: '#A855F7',
      soft: '#F3E8FF',
      softStrong: '#E9D5FF',
      dark: '#6D28D9',
    },
    admin: {
      accent: '#2563EB',
      accent2: '#38BDF8',
      soft: '#EFF6FF',
      softStrong: '#DBEAFE',
      dark: '#1D4ED8',
    },
    user: {
      accent: '#059669',
      accent2: '#10B981',
      soft: '#ECFDF5',
      softStrong: '#D1FAE5',
      dark: '#047857',
    },
  }
  const roleLabel = roleLabelMap[user?.role] || user?.role
  const roleTheme = roleThemeMap[user?.role] || roleThemeMap.admin
  const dashboardPath = isSuper ? '/super-admin/dashboard' : '/admin/dashboard'
  const shellStyle = {
    '--role-accent': roleTheme.accent,
    '--role-accent-2': roleTheme.accent2,
    '--role-soft': roleTheme.soft,
    '--role-soft-strong': roleTheme.softStrong,
    '--role-dark': roleTheme.dark,
  }

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
    <div className={styles.shell} style={shellStyle}>
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

        {sidebarOpen && (
          <div className={styles.userCard}>
            <div className={styles.ucAvatar}>{initials}</div>
            <div className={styles.ucInfo}>
              <span className={styles.ucName}>{user?.username}</span>
              <span className={styles.ucRole}>{roleLabel}</span>
            </div>
          </div>
        )}

        <nav className={styles.nav}>
          <SectionLabel label="MAIN" />
          <NavItem tab="overview" icon={<BarChart2 size={17} />} label="Overview" />
          {(isSuper || isAdmin) && <NavItem tab="users" icon={<Users size={17} />} label={isSuper ? 'Users & Admins' : 'Users'} />}
          {(isSuper || isAdmin) && <NavItem tab="email" icon={<Mail size={17} />} label="Mailboxes" />}

          <SectionLabel label="SECURITY" />
          {isAdmin && <NavItem tab="quarantine" icon={<Lock size={17} />} label="Quarantine" />}
          {isAdmin && <NavItem tab="logs" icon={<FileText size={17} />} label="Detection Logs" />}
          <NavItem tab="reports" icon={<AlertCircle size={17} />} label="Reports" />
          <NavItem tab="activity" icon={<Activity size={17} />} label={isSuper ? 'Audit Logs' : 'Security Activity'} />

          <SectionLabel label="SYSTEM" />
          {isSuper && <NavItem tab="health" icon={<Server size={17} />} label="System Health" />}
          <NavItem tab="settings" icon={<Settings size={17} />} label="Settings" />
        </nav>

        <div className={styles.spacer} />

        <button
          className={styles.backBtn}
          onClick={() => navigate(dashboardPath)}
          title="Back to Dashboard"
        >
          <Home size={16} />
          {sidebarOpen && <span>Back to Dashboard</span>}
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
              <div className={styles.avatar}>{initials}</div>
              <div className={styles.userInfo}>
                <span className={styles.userName}>{user?.username}</span>
                <span className={styles.userRole}>{roleLabel}</span>
              </div>
            </div>
            <button className={styles.logoutBtn} onClick={() => logout()} title="Logout">
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
