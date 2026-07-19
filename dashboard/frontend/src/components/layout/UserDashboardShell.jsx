import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useMe, useLogout } from '../../api/auth'
import {
  LayoutDashboard, Inbox, BarChart3, Settings, HelpCircle,
  LogOut, ChevronLeft, ChevronRight, Bell, Shield
} from 'lucide-react'
import { avatarColor, avatarText, hasUploadedAvatar } from '../../utils/avatar'
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
  const [collapsed, setCollapsed] = useState(false)

  const user = auth?.user
  const avatarKey = user?.username || 'U'
  const initials = avatarText ? avatarText(avatarKey, 2) : (user?.username ? user.username[0].toUpperCase() : 'U')
  const userAvatarUrl = user?.avatar_url || ''
  const uploadedAvatar = hasUploadedAvatar ? hasUploadedAvatar(userAvatarUrl) : false
  const userAvatar = uploadedAvatar
    ? <img src={userAvatarUrl} alt="" className={styles.avatarImage} />
    : initials
  const generatedAvatarStyle = uploadedAvatar ? undefined : (avatarColor ? { background: avatarColor(avatarKey) } : undefined)

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
          <button className={styles.collapseBtn} onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
          </button>
        </div>

        {!collapsed && (
          <div className={styles.userCard}>
            <div className={styles.ucAvatar} style={generatedAvatarStyle}>{userAvatar}</div>
            <div className={styles.ucInfo}>
              <span className={styles.ucName}>{user?.username || 'User'}</span>
              <span className={styles.ucRole}>Protected</span>
            </div>
          </div>
        )}

        <nav className={styles.nav}>
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
              <span className={styles.breadcrumbSep}>/</span>
              <span className={styles.breadcrumbCurrent}>Dashboard</span>
            </div>
          </div>
          <div className={styles.topRight}>
            <button className={styles.topBtn}>
              <Bell size={17} />
            </button>
            <div className={styles.userChip}>
              <div className={styles.avatar} style={generatedAvatarStyle}>{userAvatar}</div>
              {!collapsed && (
                <div className={styles.userInfo}>
                  <span className={styles.userName}>{user?.username || 'User'}</span>
                  <span className={styles.userRole}>User</span>
                </div>
              )}
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
