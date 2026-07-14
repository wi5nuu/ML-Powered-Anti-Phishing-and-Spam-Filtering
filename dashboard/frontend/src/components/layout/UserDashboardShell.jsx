import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useMe, useLogout } from '../../api/auth'
import {
  Shield, Mail, LogOut, BarChart2, ChevronRight,
  Inbox, Lock, Settings, Bell, Flag, Menu, X
} from 'lucide-react'
import { avatarColor, avatarText, hasUploadedAvatar } from '../../utils/avatar'
import styles from './UserDashboardShell.module.css'

export default function UserDashboardShell({ children }) {
  const { data: me } = useMe()
  const { mutate: logout } = useLogout()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const navigate = useNavigate()
  const location = useLocation()
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

        {/* User info */}
        {sidebarOpen && (
          <div className={styles.userCard}>
            <div className={styles.ucAvatar} style={generatedAvatarStyle}>{userAvatar}</div>
            <div className={styles.ucInfo}>
              <span className={styles.ucName}>{user?.username}</span>
              <span className={styles.ucRole}>User</span>
            </div>
          </div>
        )}

        {/* Nav */}
        <nav className={styles.nav}>
          <div className={styles.sectionLabel}>MAILBOX</div>
          <NavItem to={mailboxPath} icon={<Inbox size={17} />} label="Mailbox" />

          <div className={styles.sectionLabel}>SECURITY</div>
          <NavItem to={metricsPath} icon={<BarChart2 size={17} />} label="Security Report" />
          <NavItem to="/analyzer" icon={<Lock size={17} />} label="Email Analyzer" />

          <div className={styles.sectionLabel}>ACCOUNT</div>
          <NavItem to="/settings" icon={<Settings size={17} />} label="Settings" />
          <NavItem to="/help" icon={<Flag size={17} />} label="Report Issue" />
        </nav>

        <div className={styles.spacer} />

        <button className={styles.logoutBtnSide} onClick={() => logout()}>
          <LogOut size={15} />
          {sidebarOpen && <span>Logout</span>}
        </button>
      </aside>

      {/* Main */}
      <main className={styles.main}>
        {/* Topbar */}
        <header className={styles.topbar}>
          <div className={styles.topLeft}>
            <div className={styles.breadcrumb}>
              <Shield size={15} className={styles.breadcrumbIcon} />
              <span className={styles.breadcrumbRoot}>CogniMail</span>
              <ChevronRight size={13} className={styles.breadcrumbSep} />
              <span className={styles.breadcrumbCurrent}>{currentPage}</span>
            </div>
          </div>
          <div className={styles.topRight}>
            <button className={styles.topBtn} title="Notifications">
              <Bell size={17} />
            </button>
            <div className={styles.userChip}>
              <div className={styles.avatar} style={generatedAvatarStyle}>{userAvatar}</div>
              <div className={styles.userInfo}>
                <span className={styles.userName}>{user?.username}</span>
                <span className={styles.userRole}>User</span>
              </div>
            </div>
            <button className={styles.logoutBtn} onClick={() => logout()} title="Logout">
              <LogOut size={16} />
            </button>
          </div>
        </header>

        <div className={styles.content}>{children}</div>
      </main>
    </div>
  )
}
