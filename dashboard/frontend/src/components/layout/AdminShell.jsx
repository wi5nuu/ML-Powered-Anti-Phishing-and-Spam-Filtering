import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { useMe, useLogout } from '../../api/auth'
import { useTheme } from '../../hooks/useTheme'
import { useTranslation } from '../../i18n/context'
import api from '../../api/client'
import {
  Users, Activity, LogOut, BarChart2, AlertCircle,
  Mail, Settings, Bell, Server, Menu, ChevronLeft, ChevronRight,
  Home, FileText, Shield, ShieldAlert, Sun, Moon, Search, X, Loader2,
  Database
} from 'lucide-react'
import { avatarColor, avatarText, hasUploadedAvatar } from '../../utils/avatar'
import logoImg from '../../assets/logo.png'
import styles from './AdminShell.module.css'

// Admin nav structure - similar to User but with tab parameter
const SUPERADMIN_NAV_ITEMS = [
  { tab: 'overview',  icon: Home,       label: 'Overview' },
  { tab: 'users',     icon: Users,      label: 'Manajemen Pengguna' },
  { tab: 'email',     icon: Mail,       label: 'Manajemen Email' },
  { tab: 'health',    icon: Server,     label: 'Kesehatan Sistem' },
  { tab: 'analytics', icon: BarChart2,  label: 'Analitik' },
  { tab: 'threat',    icon: ShieldAlert,label: 'Laporan Ancaman' },
  { tab: 'activity',  icon: FileText,   label: 'Log Audit' },
  { tab: 'training',  icon: Database,   label: 'ML Training', externalPath: '/super-admin/training' },
  { tab: 'settings',  icon: Settings,   label: 'Pengaturan' },
]

const ADMIN_NAV_ITEMS = [
  { tab: 'overview',   icon: Home,       label: 'Overview' },
  { tab: 'users',      icon: Users,      label: 'Manajemen Pengguna' },
  { tab: 'email',      icon: Mail,       label: 'Manajemen Email' },
  { tab: 'quarantine', icon: ShieldAlert,label: 'Review Karantina' },
  { tab: 'logs',       icon: Activity,   label: 'Log Deteksi' },
  { tab: 'activity',   icon: FileText,   label: 'Log Audit' },
]

export default function AdminShell({ children }) {
  const { data: me } = useMe()
  const logout = useLogout()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [searchValue, setSearchValue] = useState('')
  const [searchFocused, setSearchFocused] = useState(false)
  const [suggestions, setSuggestions] = useState([])
  const [searchResults, setSearchResults] = useState({ pages: [], users: [], emails: [], logs: [] })
  const [searchLoading, setSearchLoading] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const searchRef = useRef(null)
  const debounceRef = useRef(null)
  const { theme, toggle: toggleTheme } = useTheme()
  const { t, lang, toggleLang } = useTranslation()

  const user = me?.user
  const isSuper = user?.role === 'superadmin'
  const isAdmin = user?.role === 'admin'
  const activeTab = searchParams.get('tab') || 'overview'

  const allNavItems = isSuper ? SUPERADMIN_NAV_ITEMS : ADMIN_NAV_ITEMS
  
  const roleLabelMap = { superadmin: 'Superadmin', admin: 'Admin', user: 'User' }
  const roleThemeMap = {
    superadmin: {
      accent: '#7C3AED', accent2: '#A855F7',
      soft: '#F3E8FF', softStrong: '#E9D5FF', dark: '#6D28D9',
    },
    admin: {
      accent: '#2563EB', accent2: '#38BDF8',
      soft: '#EFF6FF', softStrong: '#DBEAFE', dark: '#1D4ED8',
    },
  }
  
  const roleLabel = roleLabelMap[user?.role] || user?.role
  const roleTheme = roleThemeMap[user?.role] || roleThemeMap.admin
  const shellStyle = {
    '--role-accent': roleTheme.accent,
    '--role-accent-2': roleTheme.accent2,
    '--role-soft': roleTheme.soft,
    '--role-soft-strong': roleTheme.softStrong,
    '--role-dark': roleTheme.dark,
  }

  const navItems = allNavItems

  // Close mobile drawer on route change
  useEffect(() => { setMobileNavOpen(false) }, [location.pathname, activeTab])

  // Lock background scroll while mobile drawer is open
  useEffect(() => {
    if (mobileNavOpen) document.body.classList.add('no-scroll')
    else document.body.classList.remove('no-scroll')
    return () => document.body.classList.remove('no-scroll')
  }, [mobileNavOpen])

  // Close drawer when viewport grows past mobile breakpoint
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 769px)')
    const handleChange = (e) => { if (e.matches) setMobileNavOpen(false) }
    mq.addEventListener('change', handleChange)
    return () => mq.removeEventListener('change', handleChange)
  }, [])

  const openMobileNav = () => {
    setCollapsed(false)
    setMobileNavOpen(true)
  }

  const navTo = (tab) => setSearchParams({ tab })

  const runSearch = () => {
    const q = searchValue.trim()
    if (!q) return
    // Navigate to users tab with search query
    setSearchParams({ tab: 'users', q })
  }

  const clearSearch = () => {
    setSearchValue('')
    setSuggestions([])
    setShowSuggestions(false)
    const params = new URLSearchParams(searchParams)
    params.delete('q')
    setSearchParams(params, { replace: true })
  }

  const doSearch = useCallback(async (query) => {
    if (!query.trim()) {
      setSuggestions([])
      setSearchResults({ pages: [], users: [], emails: [], logs: [] })
      setShowSuggestions(false)
      return
    }
    setSearchLoading(true)
    const lower = query.toLowerCase()

    // Filter pages from nav items (match both original label and translated label)
    const pages = allNavItems.filter((item) =>
      item.label.toLowerCase().includes(lower) || t('nav.' + item.tab).toLowerCase().includes(lower)
    ).map((item) => ({ ...item, _type: 'page' }))

    try {
      const { data } = await api.get('/admin/search', { params: { q: query } })
      const users = (data?.users || []).map((u) => ({ ...u, _type: 'user' }))
      const emails = (data?.emails || []).map((e) => ({ ...e, _type: 'email' }))
      const logs = (data?.logs || []).map((l) => ({ ...l, _type: 'log' }))
      const results = { pages, users, emails, logs }
      setSearchResults(results)
      setSuggestions([...pages, ...users, ...emails, ...logs])
      setShowSuggestions(true)
      setActiveIndex(-1)
    } catch {
      setSearchResults({ pages, users: [], emails: [], logs: [] })
      setSuggestions(pages)
      setShowSuggestions(true)
      setActiveIndex(-1)
    } finally {
      setSearchLoading(false)
    }
  }, [allNavItems])

  const handleSearchChange = (e) => {
    const val = e.target.value
    setSearchValue(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(val), 250)
  }

  const selectSuggestion = (item) => {
    setShowSuggestions(false)
    setSearchValue('')
    if (item._type === 'page') {
      setSearchParams({ tab: item.tab })
    } else if (item._type === 'user') {
      setSearchParams({ tab: 'users', q: item.username || '' })
    } else if (item._type === 'email') {
      setSearchParams({ tab: 'email', q: item.subject || '' })
    } else if (item._type === 'log') {
      setSearchParams({ tab: 'activity', q: item.user || '' })
    }
  }

  const handleSearchKey = (e) => {
    if (e.key === 'Enter') {
      if (activeIndex >= 0 && suggestions[activeIndex]) {
        selectSuggestion(suggestions[activeIndex])
      } else if (suggestions.length > 0) {
        selectSuggestion(suggestions[0])
      } else {
        runSearch()
      }
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, suggestions.length - 1))
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, -1))
    }
    if (e.key === 'Escape') {
      setShowSuggestions(false)
    }
  }

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const avatarKey = user?.username || 'A'
  const initials = avatarText ? avatarText(avatarKey, 2) : (user?.username ? user.username[0].toUpperCase() : 'A')
  const userAvatarUrl = user?.avatar_url || ''
  const uploadedAvatar = hasUploadedAvatar ? hasUploadedAvatar(userAvatarUrl) : false
  const userAvatar = uploadedAvatar
    ? <img src={userAvatarUrl} alt="" className={styles.avatarImage} onError={() => {}} />
    : initials
  const generatedAvatarStyle = uploadedAvatar ? undefined : (avatarColor ? { background: avatarColor(avatarKey) } : undefined)

  return (
    <div className={styles.shell} style={shellStyle}>
      {mobileNavOpen && (
        <button
          type="button"
          className="mobileBackdrop"
          aria-label="Close menu"
          onClick={() => setMobileNavOpen(false)}
        />
      )}
      <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''} ${mobileNavOpen ? styles.mobileOpen : ''}`}>
        {/* Brand */}
        <div className={styles.brand}>
          {collapsed ? (
            <button
              className={styles.collapseBtn}
              onClick={() => setCollapsed(false)}
              title="Expand sidebar"
              style={{ margin: '0 auto' }}
            >
              <ChevronRight size={15} />
            </button>
          ) : (
            <>
              <div className={styles.brandIcon}>
                <img src={logoImg} alt="CogniMail" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
              </div>
              <div className={styles.brandText}>
                <span className={styles.brandName}>CogniMail</span>
                <span className={styles.brandSub}>{t('brand.subtitle')}</span>
              </div>
              <button className={styles.collapseBtn} onClick={() => setCollapsed(true)}>
                <ChevronLeft size={15} />
              </button>
            </>
          )}
        </div>

        {/* Navigation */}
        <nav className={styles.nav}>
          <span className={styles.sectionLabel}>{collapsed ? '' : t('nav.main')}</span>
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = item.externalPath
              ? location.pathname === item.externalPath
              : activeTab === item.tab
            return (
              <button
                key={item.tab}
                className={`${styles.navItem} ${isActive ? styles.navItemActive : ''}`}
                onClick={() => item.externalPath ? navigate(item.externalPath) : navTo(item.tab)}
                title={collapsed ? t('nav.' + item.tab) : undefined}
              >
                <span className={`${styles.navIcon} ${isActive ? styles.navIconActive : ''}`}>
                  <Icon size={17} />
                </span>
                {!collapsed && <span className={styles.navLabel}>{t('nav.' + item.tab)}</span>}
              </button>
            )
          })}
        </nav>

        <div className={styles.spacer} />

        {/* Logout */}
        <button className={styles.logoutBtnSide} onClick={() => logout.mutate()}>
          <LogOut size={16} />
          {!collapsed && <span>{t('nav.logout')}</span>}
        </button>
      </aside>

      {/* Main content */}
      <main className={styles.main}>
        <header className={styles.topbar}>
          <div className={styles.topLeft}>
            <button
              className={`${styles.topBtn} ${styles.hamburger}`}
              onClick={openMobileNav}
              title="Menu"
              aria-label="Open menu"
            >
              <Menu size={18} />
            </button>
            <div className={styles.breadcrumb}>
              <Home size={15} className={styles.breadcrumbIcon} />
              <span className={styles.breadcrumbRoot}>{t('breadcrumb.root')}</span>
              <span className={styles.breadcrumbSep}>/</span>
              <span className={styles.breadcrumbCurrent}>{t('nav.' + activeTab)}</span>
            </div>
          </div>

          {/* Global search */}
          <div className={styles.searchWrap} ref={searchRef}>
            <div className={`${styles.searchBar} ${searchFocused ? styles.searchBarFocused : ''}`}>
              <button className={styles.searchIcon} onClick={runSearch} title={t('btn.search')}>
                {searchLoading ? <Loader2 size={14} className={styles.spinIcon} /> : <Search size={15} />}
              </button>
              <input
                type="text"
                placeholder={t('search.placeholder')}
                value={searchValue}
                onChange={handleSearchChange}
                onKeyDown={handleSearchKey}
                onFocus={() => setSearchFocused(true)}
                onBlur={() => setSearchFocused(false)}
              />
              {searchValue && (
                <button className={styles.searchClear} onClick={clearSearch} title={t('search.hapus')}>
                  <X size={14} />
                </button>
              )}
            </div>
            {showSuggestions && suggestions.length > 0 && (
              <div className={styles.searchDropdown}>
                {searchResults.pages.length > 0 && (
                  <>
                    <div className={styles.searchSectionLabel}>{t('search.section.pages')}</div>
                    {searchResults.pages.map((item, i) => {
                      const flatIdx = suggestions.indexOf(item)
                      return (
                        <button key={`page-${item.tab}`} className={`${styles.searchItem} ${flatIdx === activeIndex ? styles.searchItemActive : ''}`}
                          onMouseDown={() => selectSuggestion(item)} onMouseEnter={() => setActiveIndex(flatIdx)}>
                          <div className={styles.searchItemIcon} style={{ color: 'var(--role-accent)' }}>{item.icon && <item.icon size={16} />}</div>
                          <div className={styles.searchItemBody}>
                            <span className={styles.searchItemName}>{t('nav.' + item.tab)}</span>
                          </div>
                        </button>
                      )
                    })}
                  </>
                )}
                {searchResults.users.length > 0 && (
                  <>
                    <div className={styles.searchSectionLabel}>{t('search.section.users')}</div>
                    {searchResults.users.map((item, i) => {
                      const flatIdx = suggestions.indexOf(item)
                      return (
                        <button key={`user-${item.username}`} className={`${styles.searchItem} ${flatIdx === activeIndex ? styles.searchItemActive : ''}`}
                          onMouseDown={() => selectSuggestion(item)} onMouseEnter={() => setActiveIndex(flatIdx)}>
                          <div className={styles.searchItemAvatar}>{item.username ? item.username[0].toUpperCase() : '?'}</div>
                          <div className={styles.searchItemBody}>
                            <span className={styles.searchItemName}>{item.username}</span>
                            <span className={styles.searchItemSub}>{item.email || '—'}</span>
                          </div>
                          <span className={styles.searchItemBadge}>{item.role}</span>
                        </button>
                      )
                    })}
                  </>
                )}
                {searchResults.emails.length > 0 && (
                  <>
                    <div className={styles.searchSectionLabel}>{t('search.section.emails')}</div>
                    {searchResults.emails.map((item) => {
                      const flatIdx = suggestions.indexOf(item)
                      return (
                        <button key={`email-${item.email_id}`} className={`${styles.searchItem} ${flatIdx === activeIndex ? styles.searchItemActive : ''}`}
                          onMouseDown={() => selectSuggestion(item)} onMouseEnter={() => setActiveIndex(flatIdx)}>
                          <div className={styles.searchItemIcon} style={{ color: '#5f6368' }}><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg></div>
                          <div className={styles.searchItemBody}>
                            <span className={styles.searchItemName}>{item.subject || '(no subject)'}</span>
                            <span className={styles.searchItemSub}>{item.sender}</span>
                          </div>
                        </button>
                      )
                    })}
                  </>
                )}
                {searchResults.logs.length > 0 && (
                  <>
                    <div className={styles.searchSectionLabel}>{t('search.section.logs')}</div>
                    {searchResults.logs.map((item) => {
                      const flatIdx = suggestions.indexOf(item)
                      return (
                        <button key={`log-${item.id}`} className={`${styles.searchItem} ${flatIdx === activeIndex ? styles.searchItemActive : ''}`}
                          onMouseDown={() => selectSuggestion(item)} onMouseEnter={() => setActiveIndex(flatIdx)}>
                          <div className={styles.searchItemIcon} style={{ color: '#5f6368' }}><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm-1 7V3.5L18.5 9H13zM6 20V4h5v7h7v9H6z"/></svg></div>
                          <div className={styles.searchItemBody}>
                            <span className={styles.searchItemName}>{item.action}</span>
                            <span className={styles.searchItemSub}>{item.user} &middot; {item.details ? item.details.substring(0, 60) : ''}</span>
                          </div>
                        </button>
                      )
                    })}
                  </>
                )}
              </div>
            )}
          </div>

          <div className={styles.topRight}>
            <button className={styles.topBtn} onClick={toggleLang} title={lang === 'id' ? 'English' : 'Indonesia'}>
              <span style={{ fontSize: '0.75rem', fontWeight: 700 }}>{lang === 'id' ? 'EN' : 'ID'}</span>
            </button>
            <button 
              className={styles.topBtn} 
              onClick={toggleTheme}
              title={theme === 'dark' ? t('theme.light') : t('theme.dark')}
            >
              {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button className={styles.topBtn} title="Notifications">
              <Bell size={17} />
            </button>
            <div className={styles.userChip}>
              <div className={styles.avatar} style={generatedAvatarStyle}>{userAvatar}</div>
              {!collapsed && (
                <div className={styles.userInfo}>
                  <span className={styles.userName}>{user?.username}</span>
                  <span className={styles.userRole}>{roleLabel}</span>
                </div>
              )}
            </div>
            <button className={styles.logoutBtn} onClick={() => logout.mutate()} title="Logout">
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
