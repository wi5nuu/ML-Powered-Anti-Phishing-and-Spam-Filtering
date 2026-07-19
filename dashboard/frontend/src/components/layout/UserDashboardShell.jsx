import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useMe, useLogout } from '../../api/auth'
import {
<<<<<<< HEAD
  LayoutDashboard, Inbox, BarChart3, Settings, HelpCircle,
  LogOut, ChevronLeft, ChevronRight, Bell, Shield
} from 'lucide-react'
=======
  Shield, Mail, LogOut, BarChart2, ChevronRight,
  Inbox, Lock, Settings, Bell, Flag, Menu, X
} from 'lucide-react'
import { avatarColor, avatarText, hasUploadedAvatar } from '../../utils/avatar'
>>>>>>> origin/mailbox
import styles from './UserDashboardShell.module.css'

const NAV_ITEMS = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/inbox', icon: Inbox, label: 'Inbox' },
  { path: '/metrics', icon: BarChart3, label: 'Metrics' },
  { path: '/settings', icon: Settings, label: 'Settings' },
  { path: '/help', icon: HelpCircle, label: 'Help' },
]

export default function UserDashboardShell({ children }) {
  const { data: auth } = useMe()
  const logout = useLogout()
  const navigate = useNavigate()
  const location = useLocation()
<<<<<<< HEAD
  const [collapsed, setCollapsed] = useState(false)

  const user = auth?.user
  const initials = user?.username ? user.username[0].toUpperCase() : 'U'
=======
  const user = me?.user
  const avatarKey = user?.username || 'U'
  const initials = avatarText(avatarKey, 2)
  const userAvatarUrl = user?.avatar_url || ''
  const uploadedAvatar = hasUploadedAvatar(userAvatarUrl)
  const userAvatar = uploadedAvatar
    ? <img src={userAvatarUrl} alt="" className={styles.avatarImage} />
    : initials
  const generatedAvatarStyle = uploadedAvatar ? undefined : { background: avatarColor(avatarKey) }
  const mailboxPath = '/user/mailboxes'
  const metricsPath = '/metrics'
  const currentPage = location.pathname === mailboxPath || location.pathname.startsWith('/mail/')
    ? 'Mailbox'
    : 'Dashboard'

  const NavItem = ({ to, icon, label, external }) => {
    const isActive = location.pathname === to || (to === mailboxPath && location.pathname.startsWith('/mail/'))
    return (
      <button
        className={`${styles.navItem} ${isActive ? styles.navItemActive : ''}`}
        onClick={() => external ? window.open(to, '_self') : navigate(to)}
        title={!sidebarOpen ? label : undefined}
      >
        <span className={`${styles.navIcon} ${isActive ? styles.navIconActive : ''}`}>{icon}</span>
        {sidebarOpen && <span className={styles.navLabel}>{label}</span>}
        {sidebarOpen && isActive && <ChevronRight size={14} className={styles.navChevron} />}
      </button>
    )
  }
>>>>>>> origin/mailbox

  return (
    <div className={`${styles.shell} ${collapsed ? styles.collapsed : ''}`}>
      <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`}>
        <div className={styles.brand}>
          <div className={styles.brandIcon}>
            <Shield size={18} />
          </div>
          {!collapsed && (
            <div className={styles.brandText}>
              <span className={styles.brandName}>CogniMail</span>
              <span className={styles.brandSub}>Security Dashboard</span>
            </div>
          )}
<<<<<<< HEAD
          <button className={styles.collapseBtn} onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
=======
          <button
            className={styles.collapseBtn}
            onClick={() => setSidebarOpen(v => !v)}
            title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
>>>>>>> origin/mailbox
          </button>
        </div>

        {!collapsed && (
          <div className={styles.userCard}>
            <div className={styles.ucAvatar} style={generatedAvatarStyle}>{userAvatar}</div>
            <div className={styles.ucInfo}>
<<<<<<< HEAD
              <span className={styles.ucName}>{user?.username || 'User'}</span>
              <span className={styles.ucRole}>Protected</span>
=======
              <span className={styles.ucName}>{user?.username}</span>
              <span className={styles.ucRole}>User</span>
>>>>>>> origin/mailbox
            </div>
          </div>
        )}

        <nav className={styles.nav}>
<<<<<<< HEAD
          <span className={styles.sectionLabel}>{collapsed ? '' : 'Main'}</span>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.path
            return (
              <button
                key={item.path}
                className={`${styles.navItem} ${isActive ? styles.navItemActive : ''}`}
                onClick={() => navigate(item.path)}
              >
                <span className={`${styles.navIcon} ${isActive ? styles.navIconActive : ''}`}>
                  <Icon size={17} />
                </span>
                {!collapsed && <span className={styles.navLabel}>{item.label}</span>}
              </button>
            )
          })}
=======
          <div className={styles.sectionLabel}>MAILBOX</div>
          <NavItem to={mailboxPath} icon={<Inbox size={17} />} label="Mailbox" />

          <div className={styles.sectionLabel}>SECURITY</div>
          <NavItem to={metricsPath} icon={<BarChart2 size={17} />} label="Security Report" />
          <NavItem to="/analyzer" icon={<Lock size={17} />} label="Email Analyzer" />

          <div className={styles.sectionLabel}>ACCOUNT</div>
          <NavItem to="/settings" icon={<Settings size={17} />} label="Settings" />
          <NavItem to="/help" icon={<Flag size={17} />} label="Report Issue" />
>>>>>>> origin/mailbox
        </nav>

        <div className={styles.spacer} />

        <button className={styles.logoutBtnSide} onClick={() => logout.mutate()}>
          <LogOut size={16} />
          {!collapsed && <span>Logout</span>}
        </button>
      </aside>

      <main className={styles.main}>
        <header className={styles.topbar}>
          <div className={styles.topLeft}>
            <div className={styles.breadcrumb}>
              <LayoutDashboard size={15} className={styles.breadcrumbIcon} />
              <span className={styles.breadcrumbRoot}>CogniMail</span>
<<<<<<< HEAD
              <span className={styles.breadcrumbSep}>/</span>
              <span className={styles.breadcrumbCurrent}>Dashboard</span>
=======
              <ChevronRight size={13} className={styles.breadcrumbSep} />
              <span className={styles.breadcrumbCurrent}>{currentPage}</span>
>>>>>>> origin/mailbox
            </div>
          </div>
          <div className={styles.topRight}>
            <button className={styles.topBtn}>
              <Bell size={17} />
            </button>
            <div className={styles.userChip}>
<<<<<<< HEAD
              <div className={styles.avatar}>{initials}</div>
              {!collapsed && (
                <div className={styles.userInfo}>
                  <span className={styles.userName}>{user?.username || 'User'}</span>
                  <span className={styles.userRole}>User</span>
                </div>
              )}
=======
              <div className={styles.avatar} style={generatedAvatarStyle}>{userAvatar}</div>
              <div className={styles.userInfo}>
                <span className={styles.userName}>{user?.username}</span>
                <span className={styles.userRole}>User</span>
              </div>
>>>>>>> origin/mailbox
            </div>
            <button className={styles.logoutBtn} onClick={() => logout.mutate()}>
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
