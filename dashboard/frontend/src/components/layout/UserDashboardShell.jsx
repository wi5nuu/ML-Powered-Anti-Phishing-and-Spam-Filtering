import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useMe, useLogout } from '../../api/auth'
import { useTheme } from '../../hooks/useTheme'
import { useTranslation } from '../../i18n/context'
import {
  LayoutDashboard, Inbox, BarChart3, Settings, HelpCircle,
  LogOut, ChevronLeft, ChevronRight, Bell, Shield, Menu, Sun, Moon
} from 'lucide-react'
import { avatarColor, avatarText, hasUploadedAvatar } from '../../utils/avatar'
import styles from './UserDashboardShell.module.css'

const NAV_ITEMS = [
  { path: '/dashboard', icon: LayoutDashboard, labelKey: 'userDashboard.dashboard' },
  { path: '/inbox', icon: Inbox, labelKey: 'userDashboard.inbox' },
  { path: '/metrics', icon: BarChart3, labelKey: 'userDashboard.metrics' },
  { path: '/settings', icon: Settings, labelKey: 'nav.settings' },
  { path: '/help', icon: HelpCircle, labelKey: 'userDashboard.help' },
]

export default function UserDashboardShell({ children }) {
  const { t } = useTranslation()
  const { data: auth } = useMe()
  const logout = useLogout()
  const navigate = useNavigate()
  const location = useLocation()
  const { theme, toggle: toggleTheme } = useTheme()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  // Close the mobile drawer on route change.
  useEffect(() => { setMobileNavOpen(false) }, [location.pathname])

  // Lock background scroll while the mobile drawer is open.
  useEffect(() => {
    if (mobileNavOpen) document.body.classList.add('no-scroll')
    else document.body.classList.remove('no-scroll')
    return () => document.body.classList.remove('no-scroll')
  }, [mobileNavOpen])

  // Close the drawer when the viewport grows past the mobile breakpoint,
  // otherwise the hidden drawer would keep body scroll locked.
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 769px)')
    const handleChange = (e) => { if (e.matches) setMobileNavOpen(false) }
    mq.addEventListener('change', handleChange)
    return () => mq.removeEventListener('change', handleChange)
  }, [])

  const openMobileNav = () => {
    setCollapsed(false) // ensure drawer shows expanded content
    setMobileNavOpen(true)
  }

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
      {mobileNavOpen && (
        <button
          type="button"
          className="mobileBackdrop"
          aria-label={t('gmail.closeMenu')}
          onClick={() => setMobileNavOpen(false)}
        />
      )}
      <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''} ${mobileNavOpen ? styles.mobileOpen : ''}`}>
        <div className={styles.brand}>
          {collapsed ? (
            <button
              className={styles.collapseBtn}
              onClick={() => setCollapsed(false)}
              title={t('userDashboard.expandSidebar')}
              style={{ margin: '0 auto' }}
            >
              <ChevronRight size={15} />
            </button>
          ) : (
            <>
              <div className={styles.brandIcon}>
                <Shield size={18} />
              </div>
              <div className={styles.brandText}>
                <span className={styles.brandName}>CogniMail</span>
                <span className={styles.brandSub}>{t('userDashboard.subtitle')}</span>
              </div>
              <button className={styles.collapseBtn} onClick={() => setCollapsed(true)}>
                <ChevronLeft size={15} />
              </button>
            </>
          )}
        </div>

        {!collapsed && (
          <div className={styles.userCard}>
            <div className={styles.ucAvatar} style={generatedAvatarStyle}>{userAvatar}</div>
            <div className={styles.ucInfo}>
              <span className={styles.ucName}>{user?.username || t('userDashboard.username')}</span>
              <span className={styles.ucRole}>{t('userDashboard.protected')}</span>
            </div>
          </div>
        )}

        <nav className={styles.nav}>
          <span className={styles.sectionLabel}>{collapsed ? '' : t('nav.main')}</span>
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
                {!collapsed && <span className={styles.navLabel}>{t(item.labelKey)}</span>}
              </button>
            )
          })}
        </nav>

        <div className={styles.spacer} />

        <button className={styles.logoutBtnSide} onClick={() => logout.mutate()}>
          <LogOut size={16} />
          {!collapsed && <span>{t('nav.logout')}</span>}
        </button>
      </aside>

      <main className={styles.main}>
        <header className={styles.topbar}>
          <div className={styles.topLeft}>
            <button
              className={`${styles.topBtn} ${styles.hamburger}`}
              onClick={openMobileNav}
              title={t('userDashboard.menu')}
              aria-label={t('userDashboard.openMenu')}
            >
              <Menu size={18} />
            </button>
            <div className={styles.breadcrumb}>
              <LayoutDashboard size={15} className={styles.breadcrumbIcon} />
              <span className={styles.breadcrumbRoot}>CogniMail</span>
              <span className={styles.breadcrumbSep}>/</span>
              <span className={styles.breadcrumbCurrent}>{t('userDashboard.dashboard')}</span>
            </div>
          </div>
          <div className={styles.topRight}>
            <button 
              className={styles.topBtn}
              onClick={toggleTheme}
              title={theme === 'dark' ? t('theme.light') : t('theme.dark')}
            >
              {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button className={styles.topBtn}>
              <Bell size={17} />
            </button>
            <div className={styles.userChip}>
              <div className={styles.avatar} style={generatedAvatarStyle}>{userAvatar}</div>
              {!collapsed && (
                <div className={styles.userInfo}>
                  <span className={styles.userName}>{user?.username || t('userDashboard.username')}</span>
                  <span className={styles.userRole}>{user?.role || t('userDashboard.role')}</span>
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
