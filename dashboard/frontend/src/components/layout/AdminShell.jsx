import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useMe, useLogout } from '../../api/auth'
import { useTheme } from '../../hooks/useTheme'
import { useTranslation } from '../../i18n/context'
import {
  Activity,
  AlertCircle,
  BarChart2,
  ChevronLeft,
  ChevronRight,
  Database,
  FileText,
  Home,
  LogOut,
  Mail,
  Menu,
  Moon,
  Server,
  Settings,
  Shield,
  ShieldAlert,
  Sun,
  Users,
} from 'lucide-react'
import { avatarColor, avatarText, hasUploadedAvatar } from '../../utils/avatar'
import logoImg from '../../assets/logo.png'
import styles from './AdminShell.module.css'

const SUPERADMIN_NAV_ITEMS = [
  { tab: 'overview', icon: Home },
  { tab: 'track', icon: Shield },
  { tab: 'users', icon: Users },
  { tab: 'email', icon: Mail },
  { tab: 'analytics', icon: BarChart2 },
  { tab: 'threat', icon: ShieldAlert },
  { tab: 'activity', icon: FileText },
  { tab: 'reports', icon: AlertCircle },
  { tab: 'health', icon: Server },
  { tab: 'training', icon: Database, externalPath: '/super-admin/training' },
  { tab: 'settings', icon: Settings },
]

const ADMIN_NAV_ITEMS = [
  { tab: 'overview', icon: Home },
  { tab: 'email', icon: Mail },
  { tab: 'review', icon: ShieldAlert },
  { tab: 'logs', icon: Activity },
  { tab: 'activity', icon: FileText },
  { tab: 'reports', icon: AlertCircle },
  { tab: 'settings', icon: Settings },
]

const ROLE_THEME = {
  accent: '#2563EB',
  accent2: '#38BDF8',
  soft: '#EFF6FF',
  softStrong: '#DBEAFE',
  dark: '#1D4ED8',
}

export default function AdminShell({ children }) {
  const { data: me } = useMe()
  const logout = useLogout()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [avatarFailed, setAvatarFailed] = useState(false)
  const { theme, toggle: toggleTheme } = useTheme()
  const { t, lang, toggleLang } = useTranslation()

  const user = me?.user
  const isSuper = user?.role === 'superadmin'
  const activeTab = searchParams.get('tab') || 'overview'
  const navItems = isSuper ? SUPERADMIN_NAV_ITEMS : ADMIN_NAV_ITEMS
  const activeNavItem = navItems.find((item) => (
    item.externalPath ? location.pathname === item.externalPath : item.tab === activeTab
  ))
  const activeLabelKey = `nav.${activeNavItem?.tab || activeTab}`
  const roleLabel = isSuper ? t('label.superadmin') : t('label.admin')
  const shellStyle = {
    '--role-accent': ROLE_THEME.accent,
    '--role-accent-2': ROLE_THEME.accent2,
    '--role-soft': ROLE_THEME.soft,
    '--role-soft-strong': ROLE_THEME.softStrong,
    '--role-dark': ROLE_THEME.dark,
  }

  useEffect(() => setMobileNavOpen(false), [location.pathname, activeTab])

  useEffect(() => {
    // Older sidebar behavior could leave a dashboard tab on the dedicated
    // training pathname (for example /super-admin/training?tab=settings).
    // Normalize that invalid combination so refresh/back navigation is safe.
    if (location.pathname !== '/super-admin/training') return
    const requestedTab = searchParams.get('tab')
    if (requestedTab && requestedTab !== 'training') {
      navigate(`/super-admin/dashboard?tab=${encodeURIComponent(requestedTab)}`, { replace: true })
    }
  }, [location.pathname, navigate, searchParams])

  useEffect(() => {
    if (mobileNavOpen) document.body.classList.add('no-scroll')
    else document.body.classList.remove('no-scroll')
    return () => document.body.classList.remove('no-scroll')
  }, [mobileNavOpen])

  useEffect(() => {
    const mediaQuery = window.matchMedia('(min-width: 769px)')
    const closeMobileNav = (event) => { if (event.matches) setMobileNavOpen(false) }
    mediaQuery.addEventListener('change', closeMobileNav)
    return () => mediaQuery.removeEventListener('change', closeMobileNav)
  }, [])

  const userAvatarUrl = user?.avatar_url || ''
  useEffect(() => setAvatarFailed(false), [userAvatarUrl])

  const avatarKey = user?.username || 'A'
  const initials = avatarText(avatarKey, 2)
  const uploadedAvatar = hasUploadedAvatar(userAvatarUrl) && !avatarFailed
  const userAvatar = uploadedAvatar
    ? <img src={userAvatarUrl} alt="" className={styles.avatarImage} onError={() => setAvatarFailed(true)} />
    : initials
  const generatedAvatarStyle = uploadedAvatar ? undefined : { background: avatarColor(avatarKey) }

  const openMobileNav = () => {
    setCollapsed(false)
    setMobileNavOpen(true)
  }

  const navigateToItem = (item) => {
    if (item.externalPath) {
      navigate(item.externalPath)
      return
    }
    const dashboardPath = isSuper ? '/super-admin/dashboard' : '/admin/dashboard'
    navigate(`${dashboardPath}?tab=${encodeURIComponent(item.tab)}`)
  }

  return (
    <div className={styles.shell} style={shellStyle}>
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
              type="button"
              className={styles.collapseBtn}
              onClick={() => setCollapsed(false)}
              title={t('userDashboard.expandSidebar')}
              aria-label={t('userDashboard.expandSidebar')}
              style={{ margin: '0 auto' }}
            >
              <ChevronRight size={15} />
            </button>
          ) : (
            <>
              <div className={styles.brandIcon}>
                <img src={logoImg} alt="CogniMail" />
              </div>
              <div className={styles.brandText}>
                <span className={styles.brandName}>CogniMail</span>
                <span className={styles.brandSub}>{t(isSuper ? 'brand.superadminSubtitle' : 'brand.adminSubtitle')}</span>
              </div>
              <button
                type="button"
                className={styles.collapseBtn}
                onClick={() => setCollapsed(true)}
                title={t('userDashboard.collapseSidebar')}
                aria-label={t('userDashboard.collapseSidebar')}
              >
                <ChevronLeft size={15} />
              </button>
            </>
          )}
        </div>

        <nav className={styles.nav} aria-label={t('nav.main')}>
          <span className={styles.sectionLabel}>{collapsed ? '' : t('nav.main')}</span>
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = item.externalPath
              ? location.pathname === item.externalPath
              : activeTab === item.tab && location.pathname !== '/super-admin/training'
            return (
              <button
                type="button"
                key={item.tab}
                className={`${styles.navItem} ${isActive ? styles.navItemActive : ''}`}
                onClick={() => navigateToItem(item)}
                title={collapsed ? t(`nav.${item.tab}`) : undefined}
                aria-current={isActive ? 'page' : undefined}
              >
                <span className={`${styles.navIcon} ${isActive ? styles.navIconActive : ''}`}>
                  <Icon size={18} />
                </span>
                {!collapsed && <span className={styles.navLabel}>{t(`nav.${item.tab}`)}</span>}
              </button>
            )
          })}
        </nav>

        <button
          type="button"
          className={styles.logoutBtnSide}
          onClick={() => logout.mutate()}
          disabled={logout.isPending}
          title={collapsed ? t('nav.logout') : undefined}
        >
          <LogOut size={17} />
          {!collapsed && <span>{t('nav.logout')}</span>}
        </button>
      </aside>

      <main className={styles.main}>
        <header className={styles.topbar}>
          <div className={styles.topLeft}>
            <button
              type="button"
              className={`${styles.topBtn} ${styles.hamburger}`}
              onClick={openMobileNav}
              title={t('userDashboard.menu')}
              aria-label={t('userDashboard.openMenu')}
            >
              <Menu size={19} />
            </button>
            <div className={styles.breadcrumb}>
              <Home size={16} className={styles.breadcrumbIcon} />
              <span className={styles.breadcrumbRoot}>{t('breadcrumb.root')}</span>
              <span className={styles.breadcrumbSep}>/</span>
              <span className={styles.breadcrumbCurrent}>{t(activeLabelKey)}</span>
            </div>
          </div>

          <div className={styles.topRight}>
            <button type="button" className={styles.topBtn} onClick={toggleLang} title={lang === 'id' ? 'English' : 'Indonesia'}>
              <span style={{ fontSize: '0.75rem', fontWeight: 700 }}>{lang === 'id' ? 'EN' : 'ID'}</span>
            </button>
            <button
              type="button"
              className={styles.topBtn}
              onClick={toggleTheme}
              title={theme === 'dark' ? t('theme.light') : t('theme.dark')}
            >
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <button type="button" className={styles.userChip} onClick={() => navigate('/profile')} title={t('profile.title')}>
              <div className={styles.avatar} style={generatedAvatarStyle}>{userAvatar}</div>
              <div className={styles.userInfo}>
                <span className={styles.userName}>{user?.username}</span>
                <span className={styles.userRole}>{roleLabel}</span>
              </div>
            </button>
            <button
              type="button"
              className={styles.logoutBtn}
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
              title={t('nav.logout')}
            >
              <LogOut size={17} />
            </button>
          </div>
        </header>

        <div className={styles.content}>{children}</div>
      </main>
    </div>
  )
}
