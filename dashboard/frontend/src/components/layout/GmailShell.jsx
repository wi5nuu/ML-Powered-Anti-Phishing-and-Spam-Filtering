import { useState, useEffect } from 'react'
import { NavLink, useNavigate, useSearchParams, useLocation, useParams } from 'react-router-dom'
import { useTheme } from '../../hooks/useTheme'
import { useMe, useLogout } from '../../api/auth'
import { useStats } from '../../api/metrics'
import api from '../../api/client'
import { useTranslation } from '../../i18n/context'
import logoImg from '../../assets/logo.png'
import {
  Menu, Search, Settings, Sun, Moon, User,
  Pencil, Inbox, Send, SlidersHorizontal, HelpCircle, Grid,
  Shield, Flag, Calendar, CheckSquare, Users, Plus, Sparkles,
  Star, FileText, Mail, Trash2, ChevronDown, ChevronRight
} from 'lucide-react'
import ComposeModal from './ComposeModal'
import EmailList from '../inbox/EmailList'
import AppGrid from './AppGrid'
import EmailDetailPage from '../../pages/EmailDetailPage'
import { ReadPaneProvider, useReadPane } from '../../contexts/ReadPaneContext'
import { clearMailboxSession, getActiveMailbox, getActiveMailboxId, getMailboxById, getMailboxSession, setMailboxSession, withMailbox } from '../../utils/mailbox'
import { useUserMailbox } from '../../api/userMailbox'
import { avatarColor, avatarInitial, hasUploadedAvatar } from '../../utils/avatar'
import styles from './GmailShell.module.css'

// Derive which list view to show alongside the email detail, based on the
// `from` query param that EmailRow embeds when navigating to the detail route.
function getListViewFromPath(fromPath) {
  if (!fromPath) return ''
  const segment = fromPath.match(/^\/mail\/[^/]+\/([^/?]+)/)?.[1] || ''
  if (segment === 'sent') return 'sent'
  if (segment === 'drafts') return 'draft'
  if (segment === 'all') return 'allmail'
  if (segment === 'trash') return 'trash'
  if (segment === 'starred') return 'starred'
  if (['spam', 'phishing', 'malware'].includes(segment)) return segment
  if (fromPath.startsWith('/sent')) return 'sent'
  if (fromPath.startsWith('/draft')) return 'draft'
  // inbox: carry over folder/category
  return ''
}

export default function GmailShell({ children }) {
  // Move all hooks before any conditional returns (Rules of Hooks)
  const inReadPane = useReadPane()
  const { t } = useTranslation()
  const { theme, toggle } = useTheme()
  const { data: me } = useMe()
  const { data: stats } = useStats()
  const { mutate: logout } = useLogout()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [appGridOpen, setAppGridOpen] = useState(false)
  const [searchValue, setSearchValue] = useState('')
  const [searchFocused, setSearchFocused] = useState(false)
  const [composeOpen, setComposeOpen] = useState(false)
  const [composeDraft, setComposeDraft] = useState(null)
  const [composeThreadId, setComposeThreadId] = useState('')
  const [composeParentEmailId, setComposeParentEmailId] = useState('')
  const [composeMode, setComposeMode] = useState('new')
  const [threatOpen, setThreatOpen] = useState(true)
  const [reportOpen, setReportOpen] = useState(false)
  const [reportSubject, setReportSubject] = useState('')
  const [reportMessage, setReportMessage] = useState('')
  const [reportCategory, setReportCategory] = useState('other')
  const [reportMsg, setReportMsg] = useState('')
  const [expiredLoginOpen, setExpiredLoginOpen] = useState(false)
  const [expiredPassword, setExpiredPassword] = useState('')
  const [expiredError, setExpiredError] = useState('')
  const [expiredLoading, setExpiredLoading] = useState(false)
  const [avatarFailed, setAvatarFailed] = useState(false)
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    const handleOpenCompose = (event) => {
      const detail = event.detail || {}
      setComposeDraft(detail || null)
      setComposeThreadId(detail.thread_id || detail.threadId || '')
      setComposeParentEmailId(detail.parent_email_id || detail.parentEmailId || '')
      setComposeMode(detail.compose_mode || detail.composeMode || 'new')
      setComposeOpen(true)
    }
    window.addEventListener('open-compose', handleOpenCompose)
    return () => window.removeEventListener('open-compose', handleOpenCompose)
  }, [])

  const user = me?.user
  const activeMailboxId = getActiveMailboxId(searchParams)
  const activeMailboxSession = activeMailboxId ? getMailboxSession(activeMailboxId) : null
  const activeMailboxDirectory = activeMailboxId ? getMailboxById(activeMailboxId) : null
  const userMailboxEmail = user?.role === 'mailbox' ? user?.mailbox_email || user?.username : ''
  const userMailboxId = user?.role === 'mailbox' ? user?.mailbox_id || '' : ''
  // Resolve mailbox email: from session, directory, query param, or directly from URL path
  // when mailboxId is already an email address (admin impersonation via /mail/:email/inbox)
  const rawActiveMailbox = getActiveMailbox(searchParams)
  const urlMailboxIsEmail = activeMailboxId && activeMailboxId.includes('@')
  const activeMailbox = rawActiveMailbox || (urlMailboxIsEmail ? activeMailboxId : '')
  const mailboxIdentity = activeMailbox || userMailboxEmail
  const mailboxId = activeMailboxId || userMailboxId
  const displayIdentity = mailboxIdentity || user?.username || ''
  const displayRole = mailboxIdentity ? t('gmail.mailboxRole') : user?.role
  const displayInitial = avatarInitial(displayIdentity || 'U')
  const mailboxAvatarUrl = activeMailboxSession?.avatar_url || activeMailboxDirectory?.avatar_url || ''
  const avatarUrl = mailboxIdentity ? mailboxAvatarUrl : user?.avatar_url || ''
  const uploadedAvatar = hasUploadedAvatar(avatarUrl) && !avatarFailed
  const avatarStyle = uploadedAvatar ? undefined : { background: avatarColor(displayIdentity) }
  const hasMailboxIdentity = Boolean(mailboxId && mailboxIdentity)
  const hasTopbarIdentity = Boolean(user || hasMailboxIdentity)

  // ── Split-pane detection ──────────────────────────────────────────────────
  const isInboxPath =
    location.pathname === '/inbox' ||
    /^\/mail\/[^/]+\/inbox$/.test(location.pathname) ||
    location.pathname === '/'
  const isEmailDetailPath =
    /^\/email\/[^/]+/.test(location.pathname) ||
    /^\/mail\/[^/]+\/email\/[^/]+/.test(location.pathname)
  const isSplitPane = isEmailDetailPath || isInboxPath
  const activeEmailId =
    location.pathname.match(/\/email\/([^/?]+)/)?.[1] ||
    (isInboxPath ? 'gdg-event-1' : null)
  const fromPath = searchParams.get('from') || ''
  const splitListView = getListViewFromPath(fromPath)


  useEffect(() => {
    setExpiredLoginOpen(Boolean(mailboxId && searchParams.get('expired') === '1'))
  }, [mailboxId, searchParams])

  useEffect(() => {
    setAvatarFailed(false)
  }, [avatarUrl])

  const handleExpiredLogin = async (event) => {
    event.preventDefault()
    if (!mailboxId || !mailboxIdentity) return
    setExpiredError('')
    setExpiredLoading(true)
    try {
      const { data } = await api.post('/mailboxes/login', {
        mailbox_id: mailboxId,
        email: mailboxIdentity,
        password: expiredPassword,
      })
      const mailbox = data.mailbox || data
      setMailboxSession(mailbox)
      setExpiredPassword('')
      setExpiredLoginOpen(false)
      const next = new URLSearchParams(searchParams)
      next.delete('expired')
      const query = next.toString()
      navigate(query ? `${location.pathname}?${query}` : location.pathname, { replace: true })
    } catch (err) {
      setExpiredError(err.response?.data?.detail || t('gmail.expiredError'))
    } finally {
      setExpiredLoading(false)
    }
  }

  useEffect(() => {
    if (!activeMailboxId && !searchParams.get('mailbox')) return
    const next = new URLSearchParams(searchParams)
    let changed = false

    if (activeMailboxId && next.has('mailbox')) {
      next.delete('mailbox')
      changed = true
    }

    const from = next.get('from')
    if (from?.includes('mailbox=')) {
      const [fromPath, fromQuery = ''] = from.split('?')
      const fromParams = new URLSearchParams(fromQuery)
      if (fromParams.has('mailbox_id') && fromParams.has('mailbox')) {
        fromParams.delete('mailbox')
        next.set('from', fromParams.toString() ? `${fromPath}?${fromParams.toString()}` : fromPath)
        changed = true
      }
    }

    if (changed) {
      const query = next.toString()
      navigate(query ? `${location.pathname}?${query}` : location.pathname, { replace: true })
    }
  }, [activeMailboxId, location.pathname, navigate, searchParams])

  useEffect(() => {
    setSearchValue(searchParams.get('q') || '')
  }, [searchParams])

  useEffect(() => {
    setMobileNavOpen(false)
  }, [location.pathname, location.search])

  useEffect(() => {
    if (mobileNavOpen) {
      document.body.classList.add('no-scroll')
    } else {
      document.body.classList.remove('no-scroll')
    }
    return () => document.body.classList.remove('no-scroll')
  }, [mobileNavOpen])

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 769px)')
    const handleChange = (e) => { if (e.matches) setMobileNavOpen(false) }
    mq.addEventListener('change', handleChange)
    return () => mq.removeEventListener('change', handleChange)
  }, [])

  const handleLogoutClick = () => {
    if (mailboxIdentity) {
      const shouldReturnToMainLogin = activeMailboxSession?.login_source === 'main_login'
      api.post('/mailboxes/logout').catch(() => {})
      clearMailboxSession(mailboxId || mailboxIdentity, mailboxIdentity)
      setUserMenuOpen(false)
      if (shouldReturnToMainLogin) {
        navigate('/login', { replace: true })
        return
      }
      const target = mailboxId
        ? `/mail/${encodeURIComponent(mailboxId)}/login`
        : '/mailbox-login'
      navigate(target, { replace: true })
      return
    }
    logout()
  }

  const runSearch = () => {
    const value = searchValue.trim()
    const sourcePath = isEmailDetailPath
      ? (searchParams.get('from') || '/inbox')
      : `${location.pathname}${location.search}`
    const [basePath, baseQuery = ''] = sourcePath.split('?')
    const baseParams = new URLSearchParams(baseQuery)

    let searchBase = '/inbox'
    if (basePath.startsWith('/sent')) searchBase = '/sent'
    else if (basePath.startsWith('/draft')) searchBase = '/draft'
    else if (/^\/mail\/[^/]+\/sent/.test(basePath)) searchBase = '/sent'
    else if (/^\/mail\/[^/]+\/drafts/.test(basePath)) searchBase = '/draft'

    const params = new URLSearchParams()
    if (value) params.set('q', value)

    if (searchBase === '/inbox') {
      const folder = baseParams.get('folder')
      const category = baseParams.get('category')
      if (folder) params.set('folder', folder)
      if (category) params.set('category', category)
    }

    const query = params.toString()
    navigate(withMailbox(query ? `${searchBase}?${query}` : searchBase, mailboxIdentity, mailboxId))
  }

  const clearSearch = () => {
    setSearchValue('')
    const sourcePath = isEmailDetailPath
      ? (searchParams.get('from') || '/inbox')
      : `${location.pathname}${location.search}`
    const [basePath, baseQuery = ''] = sourcePath.split('?')
    const baseParams = new URLSearchParams(baseQuery)
    baseParams.delete('q')

    let clearBase = '/inbox'
    if (basePath.startsWith('/sent')) clearBase = '/sent'
    else if (basePath.startsWith('/draft')) clearBase = '/draft'
    else if (/^\/mail\/[^/]+\/sent/.test(basePath)) clearBase = '/sent'
    else if (/^\/mail\/[^/]+\/drafts/.test(basePath)) clearBase = '/draft'
    else {
      const folder = baseParams.get('folder')
      const category = baseParams.get('category')
      const keep = new URLSearchParams()
      if (folder) keep.set('folder', folder)
      if (category) keep.set('category', category)
      const q = keep.toString()
      navigate(withMailbox(q ? `/inbox?${q}` : '/inbox', mailboxIdentity, mailboxId))
      return
    }
    navigate(withMailbox(clearBase, mailboxIdentity, mailboxId))
  }

  const handleSearch = (e) => {
    if (e.key === 'Enter') runSearch()
  }

  const handleShellClick = (e) => {
    if (!e.target.closest(`.${styles.avatarWrap}`)) {
      setUserMenuOpen(false)
    }
  }

  const isNavActive = (to) => {
    const [path, query = ''] = to.split('?')
    const activeSource = isEmailDetailPath
      ? searchParams.get('from')
      : null
    const [currentPath, currentQuery = ''] = (activeSource || location.pathname).split('?')
    const logicalCurrentPath = (() => {
      const match = currentPath.match(/^\/mail\/[^/]+\/([^/]+)/)
      const section = match?.[1]
      if (!section) return currentPath
      if (section === 'drafts') return '/draft'
      if (section === 'sent') return '/sent'
      if (section === 'all' || section === 'trash' || section === 'starred') return '/inbox'
      if (['spam', 'phishing', 'malware'].includes(section)) return '/inbox'
      if (section === 'email') return currentPath
      return `/${section}`
    })()
    const currentParams = activeSource ? new URLSearchParams(currentQuery) : searchParams

    if (logicalCurrentPath !== path) return false

    const targetParams = new URLSearchParams(query)
    if (path === '/inbox') {
      const mailSection = currentPath.match(/^\/mail\/[^/]+\/([^/]+)/)?.[1] || ''
      const currentCategory = ['spam', 'phishing', 'malware'].includes(mailSection) ? mailSection : (currentParams.get('category') || '')
      const currentFolder = mailSection === 'starred'
        ? 'starred'
        : mailSection === 'all'
          ? 'allmail'
          : mailSection === 'trash'
            ? 'trash'
            : (currentParams.get('folder') || '')
      return (targetParams.get('filter') || '') === (currentParams.get('filter') || '')
        && (targetParams.get('category') || '') === currentCategory
        && (targetParams.get('folder') || '') === currentFolder
    }
    if (path === '/admin/dashboard' || path === '/super-admin/dashboard') {
      return (targetParams.get('tab') || '') === (currentParams.get('tab') || '')
    }
    for (const [key, value] of targetParams.entries()) {
      if (currentParams.get(key) !== value) return false
    }
    return true
  }

  const navItem = (to, icon, label, count) => (
    <NavLink
      to={withMailbox(to, mailboxIdentity, mailboxId)}
      end
      className={() => `${styles.sidebarItem} ${isNavActive(to) ? styles.active : ''}`}
    >
      <span className={styles.itemIcon}>{icon}</span>
      <span className={styles.itemLabel}>{label}</span>
      {(count ?? 0) > 0 && <span className={styles.itemCount}>{count}</span>}
    </NavLink>
  )

  const activeSourcePath = isEmailDetailPath
    ? searchParams.get('from') || ''
    : `${location.pathname}${location.search}`
  const activeSourceParams = new URLSearchParams(activeSourcePath.split('?')[1] || '')
  const activeMailSection = activeSourcePath.match(/^\/mail\/[^/]+\/([^/?]+)/)?.[1] || ''
  const currentCat = ['spam', 'phishing', 'malware'].includes(activeMailSection)
    ? activeMailSection
    : activeSourcePath.startsWith('/inbox')
      ? (activeSourceParams.get('category') || null)
      : null
  const catItem = (category, label, color, count) => (
    <NavLink
      to={withMailbox(`/inbox?category=${category}`, mailboxIdentity, mailboxId)}
      className={() => `${styles.sidebarItem} ${currentCat === category ? styles.active : ''}`}
    >
      <span className={styles.labelDot} style={{ background: color }} />
      <span className={styles.itemLabel}>{label}</span>
      {(count ?? 0) > 0 && <span className={styles.itemCount} style={{ color }}>{count}</span>}
    </NavLink>
  )

  // Early return after all hooks have been called (Rules of Hooks compliance)
  if (inReadPane) {
    return <div className={styles.readPaneContent}>{children}</div>
  }

  return (
    <div className={styles.shell} onClick={handleShellClick}>
      {/* ═══ TOP BAR (100% Gmail Style matching UI_user_page.png) ═══ */}
      <header className={styles.topbar}>
        {/* LEFT: hamburger + brand */}
        <div className={styles.topbarLeft}>
          <button
            className={styles.iconRound}
            onClick={() => {
              if (typeof window !== 'undefined' && window.matchMedia('(max-width: 768px)').matches) {
                setMobileNavOpen((v) => {
                  const next = !v
                  if (next) setSidebarOpen(true)
                  return next
                })
              } else {
                setSidebarOpen((v) => !v)
              }
            }}
            title={t('gmail.mainMenu')}
            id="sidebar-toggle-btn"
          >
            <Menu size={20} />
          </button>
          <NavLink to={withMailbox('/inbox', mailboxIdentity, mailboxId)} className={styles.brand}>
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <path d="M4 8L16 17L28 8V24H4V8Z" fill="#EA4335" />
              <path d="M4 8L16 17L28 8H4Z" fill="#C5221F" />
              <path d="M28 8V24H24V11L16 17L8 11V24H4V8H28Z" fill="#4285F4" />
            </svg>
            <span className={styles.brandText}>Gmail</span>
          </NavLink>
        </div>

        {/* CENTER: search bar with filter icon */}
        <div className={styles.searchWrap} style={{ position: 'relative' }}>
          <div className={`${styles.searchBar} ${searchFocused ? styles.searchBarFocused : ''}`}>
            <button className={styles.searchIcon} title={t('gmail.search')} onClick={runSearch}>
              <Search size={20} />
            </button>
            <input
              type="text"
              placeholder="Telusuri email"
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              onKeyDown={handleSearch}
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setSearchFocused(false)}
              id="search-input"
            />
            {searchValue ? (
              <button
                className={styles.searchIcon}
                onClick={clearSearch}
                title={t('gmail.clearSearch')}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                </svg>
              </button>
            ) : (
              <button className={styles.searchIcon} title="Opsi penelusuran" onClick={runSearch}>
                <SlidersHorizontal size={18} />
              </button>
            )}
          </div>
        </div>

        {/* RIGHT: icons matching Gmail order in UI_user_page.png */}
        <div className={styles.topbarRight}>
          <button className={styles.iconRound} title="Dukungan / Bantuan">
            <HelpCircle size={20} />
          </button>
          
          <button
            className={styles.iconRound}
            onClick={() => { if (!mailboxIdentity) navigate('/settings') }}
            title="Setelan"
            id="settings-top-btn"
          >
            <Settings size={20} />
          </button>

          <button className={styles.upgradeBtn} title="Upgrade ke versi premium">
            Upgrade
          </button>

          <button
            className={styles.iconRound}
            onClick={() => setAppGridOpen(true)}
            title="Aplikasi Google"
            id="app-grid-btn"
          >
            <Grid size={20} />
          </button>

          <button
            className={styles.iconRound}
            onClick={toggle}
            title={theme === 'dark' ? t('theme.light') : t('theme.dark')}
            id="theme-toggle-btn"
          >
            {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
          </button>

          {hasTopbarIdentity ? (
            <div className={styles.avatarWrap}>
              <div
                className={styles.avatar}
                onClick={() => setUserMenuOpen((v) => !v)}
                title={displayIdentity}
                id="user-avatar-btn"
                style={avatarStyle}
              >
                {uploadedAvatar ? <img src={avatarUrl} alt="" className={styles.avatarImage} onError={() => setAvatarFailed(true)} /> : displayInitial}
              </div>
              {userMenuOpen && (
                <div className={styles.userMenu}>
                  <div className={styles.userMenuHeader}>
                    <div className={styles.userMenuAvatar} style={avatarStyle}>
                      {uploadedAvatar ? <img src={avatarUrl} alt="" className={styles.avatarImage} onError={() => setAvatarFailed(true)} /> : displayInitial}
                    </div>
                    <div>
                      <div className={styles.userMenuName}>{displayIdentity}</div>
                      {activeMailbox && <div className={styles.userMenuRole}>{displayRole}</div>}
                    </div>
                  </div>
                  <div className={styles.userMenuDivider} />
                  <button
                    className={styles.userMenuItem}
                    onClick={() => { navigate(withMailbox('/profile', mailboxIdentity, mailboxId)); setUserMenuOpen(false) }}
                    id="menu-profile-btn"
                  >
                    <User size={16} />
                    <span>{t('gmail.profile')}</span>
                  </button>
                  <button
                    className={styles.userMenuItem}
                    onClick={() => { setReportOpen(true); setUserMenuOpen(false) }}
                  >
                    <Flag size={16} />
                    <span>{t('gmail.report')}</span>
                  </button>
                  {!mailboxIdentity && (
                    <button
                      className={styles.userMenuItem}
                      onClick={() => { navigate('/settings'); setUserMenuOpen(false) }}
                      id="menu-settings-btn"
                    >
                      <Settings size={16} />
                      <span>{t('gmail.settings')}</span>
                    </button>
                  )}
                  <div className={styles.userMenuDivider} />
                  <button
                    className={`${styles.userMenuItem} ${styles.logoutItem}`}
                    onClick={handleLogoutClick}
                    id="logout-btn"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z" />
                    </svg>
                    <span>{t('gmail.logout')}</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button
              className={styles.loginBtn}
              onClick={() => navigate(mailboxId ? `/mail/${encodeURIComponent(mailboxId)}/login` : '/mailbox-login')}
              id="login-btn"
            >
              {t('gmail.login')}
            </button>
          )}
        </div>
      </header>

      {/* ═══ BODY ═══ */}
      <div className={styles.body}>
        {/* Mobile drawer backdrop */}
        {mobileNavOpen && (
          <button
            type="button"
            className="mobileBackdrop"
            aria-label={t('gmail.closeMenu')}
            onClick={() => setMobileNavOpen(false)}
          />
        )}
        {/* SIDEBAR — Retaining current sidebar intact as requested */}
        <nav className={`${styles.sidebar} ${!sidebarOpen ? styles.sidebarCollapsed : ''} ${mobileNavOpen ? styles.sidebarMobileOpen : ''}`}>
          {!sidebarOpen && (
            <button
              className={styles.sidebarToggleBtn}
              onClick={() => setSidebarOpen(true)}
              title={t('gmail.openSidebar')}
            >
              <Menu size={20} />
            </button>
          )}
          {sidebarOpen && (
            <>
              <button className={styles.composeBtn} id="compose-btn" onClick={() => {
                setComposeDraft(null)
                setComposeThreadId('')
                setComposeParentEmailId('')
                setComposeMode('new')
                setComposeOpen(true)
              }}>
                <Pencil size={20} color="#001d35" />
                <span>{t('gmail.compose')}</span>
              </button>

              {navItem('/inbox', <Inbox size={18} color="#444746" />, 'Kotak Masuk', stats?.unread)}
              {navItem('/inbox?folder=starred', <Star size={18} color="#f29900" />, 'Berbintang', stats?.starred)}
              {navItem('/inbox?folder=snoozed', <FileText size={18} color="#444746" />, 'Ditunda', 0)}
              {navItem('/sent', <Send size={18} color="#444746" />, 'Terkirim', stats?.sent)}
              {navItem('/draft', <FileText size={18} color="#444746" />, 'Draf', stats?.draft)}
              {navItem('/pembelian', <Tag size={18} color="#444746" />, 'Pembelian', 78)}
              {navItem('/inbox?folder=allmail', <Mail size={18} color="#444746" />, 'Selengkapnya', stats?.total)}

              <div className={styles.divider} />
              <div className={styles.sidebarHeading}>{t('gmail.threatLabel')}</div>
              <button
                className={`${styles.sidebarItem} ${styles.sidebarButton} ${currentCat ? styles.active : ''}`}
                onClick={() => setThreatOpen((v) => !v)}
              >
                <span className={styles.itemIcon}><Shield size={18} color="#0b57d0" /></span>
                <span className={styles.itemLabel}>{t('gmail.quarantine')}</span>
                <span className={styles.expandIcon}>
                  {threatOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                </span>
              </button>
              {threatOpen && (
                <div className={styles.subNav}>
                  {catItem('phishing', t('gmail.phishing'), '#EA4335', stats?.categories?.phishing)}
                  {catItem('spam', t('gmail.spam'), '#f29900', stats?.categories?.spam)}
                  {catItem('malware', t('gmail.malware'), '#8b1a10', stats?.categories?.malware)}
                </div>
              )}

              <div className={styles.divider} />
              <div className={styles.sidebarHeading}>{t('gmail.system')}</div>
              <button className={`${styles.sidebarItem} ${styles.sidebarButton}`} onClick={() => setReportOpen(true)}>
                <span className={styles.itemIcon}><Flag size={18} color="#444746" /></span>
                <span className={styles.itemLabel}>{t('gmail.report')}</span>
              </button>
              {!mailboxIdentity && (
                <button
                  className={`${styles.sidebarItem} ${styles.sidebarButton}`}
                  onClick={() => navigate('/settings')}
                >
                  <span className={styles.itemIcon}><Settings size={18} color="#444746" /></span>
                  <span className={styles.itemLabel}>{t('gmail.settings')}</span>
                </button>
              )}
            </>
          )}
        </nav>

        {/* MAIN CONTENT — split pane on inbox or email detail routes (desktop only) */}
        {isSplitPane ? (
          <div className={styles.splitMain}>
            <div className={styles.listPane}>
              <EmailList view={splitListView} activeEmailId={activeEmailId} />
            </div>
            <div className={styles.readPane}>
              <ReadPaneProvider>
                {isEmailDetailPath ? children : <EmailDetailPage overrideEmailId={activeEmailId} />}
              </ReadPaneProvider>
            </div>
          </div>
        ) : (
          <main className={styles.main}>{children}</main>
        )}

        {/* FAR RIGHT COMPANION DOCK (100% Gmail Side Dock in UI_user_page.png) */}
        <aside className={styles.companionDock}>
          <button className={styles.dockItem} title="Kalender">
            <Calendar size={20} color="#1a73e8" />
          </button>
          <button className={styles.dockItem} title="Keep">
            <div className={styles.keepIconWrap}>
              <FileText size={18} color="#fbbc04" />
            </div>
          </button>
          <button className={styles.dockItem} title="Tasks">
            <CheckSquare size={20} color="#1a73e8" />
          </button>
          <button className={styles.dockItem} title="Kontak">
            <Users size={20} color="#1a73e8" />
          </button>
          <div className={styles.dockDivider} />
          <button className={styles.dockItem} title="Dapatkan add-on">
            <Plus size={20} color="#444746" />
          </button>
          <div className={styles.dockSpacer} />
          <button className={styles.dockItem} title="Ciutkan panel samping">
            <ChevronRight size={18} color="#444746" />
          </button>
        </aside>
      </div>

      <AppGrid open={appGridOpen} onClose={() => setAppGridOpen(false)} user={user} />

      <ComposeModal
        open={composeOpen}
        onClose={() => {
          setComposeOpen(false)
          setComposeDraft(null)
          setComposeThreadId('')
          setComposeParentEmailId('')
          setComposeMode('new')
        }}
        fromMailbox={mailboxIdentity}
        initialDraft={composeDraft}
        threadId={composeThreadId}
        parentEmailId={composeParentEmailId}
        composeMode={composeMode}
      />


      {expiredLoginOpen && (
        <div className={styles.overlay}>
          <form className={styles.sessionModal} onSubmit={handleExpiredLogin}>
            <div className={styles.sessionIcon}><Mail size={22} /></div>
            <h3>{t('gmail.expiredTitle')}</h3>
            <p>{t('gmail.expiredMessageBefore')}<strong>{mailboxIdentity}</strong>{t('gmail.expiredMessageAfter')}</p>
            {expiredError && <div className={styles.sessionError}>{expiredError}</div>}
            <input
              type="password"
              value={expiredPassword}
              onChange={(event) => setExpiredPassword(event.target.value)}
              placeholder={t('gmail.expiredPasswordPlaceholder')}
              autoComplete="current-password"
              autoFocus
              required
            />
            <div className={styles.sessionActions}>
              <button type="submit" className={styles.sessionSubmit} disabled={expiredLoading}>
                {expiredLoading ? t('gmail.expiredProcessing') : t('gmail.expiredLoginAgain')}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Report Modal */}
      {reportOpen && (
        <div className={styles.overlay} onClick={() => setReportOpen(false)}>
          <div className={styles.reportModal} onClick={(e) => e.stopPropagation()}>
            <h3>{t('gmail.reportTitle')}</h3>
            {reportMsg && <div className={styles.reportMsg}>{reportMsg}</div>}
            <select
              value={reportCategory}
              onChange={(e) => setReportCategory(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 6, background: 'var(--surface)', color: 'var(--text)', fontSize: '0.8125rem', marginBottom: 8, fontFamily: 'inherit' }}
            >
              <option value="question">{t('gmail.reportCategoryQuestion')}</option>
              <option value="bug">{t('gmail.reportCategoryBug')}</option>
              <option value="false_positive">{t('gmail.reportCategoryFalsePositive')}</option>
              <option value="access">{t('gmail.reportCategoryAccess')}</option>
              <option value="other">{t('gmail.reportCategoryOther')}</option>
            </select>
            <input
              placeholder={t('gmail.reportSubjectPlaceholder')}
              value={reportSubject}
              onChange={(e) => setReportSubject(e.target.value)}
            />
            <textarea
              placeholder={t('gmail.reportMessagePlaceholder')}
              value={reportMessage}
              onChange={(e) => setReportMessage(e.target.value)}
              rows={4}
            />
            <div className={styles.reportActions}>
              <button onClick={() => { setReportOpen(false); setReportSubject(''); setReportMessage(''); setReportCategory('other'); setReportMsg('') }}>
                {t('btn.cancel')}
              </button>
              <button
                className={styles.reportSend}
                disabled={!reportSubject || !reportMessage}
                onClick={async () => {
                  try {
                    await api.post('/reports', { subject: reportSubject, message: reportMessage, category: reportCategory })
                    setReportMsg(t('gmail.reportSuccess'))
                    setReportSubject(''); setReportMessage(''); setReportCategory('other')
                    setTimeout(() => { setReportOpen(false); setReportMsg('') }, 2000)
                  } catch (e) {
                    setReportMsg(t('gmail.reportError'))
                  }
                }}
              >
                {t('gmail.reportSend')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
