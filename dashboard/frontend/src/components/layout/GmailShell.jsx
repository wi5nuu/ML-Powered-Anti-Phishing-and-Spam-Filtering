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
  Pencil, Inbox, Send,
  Shield, Flag,
  Star, FileText, Mail, ChevronDown, ChevronRight
} from 'lucide-react'
import ComposeModal from './ComposeModal'
import { clearMailboxSession, getActiveMailbox, getActiveMailboxId, getMailboxById, getMailboxSession, setMailboxSession, withMailbox } from '../../utils/mailbox'
import { useUserMailbox } from '../../api/userMailbox'
import { avatarColor, avatarInitial, hasUploadedAvatar } from '../../utils/avatar'
import styles from './GmailShell.module.css'

export default function GmailShell({ children }) {
  const { t } = useTranslation()
  const { theme, toggle } = useTheme()
  const { data: me } = useMe()
  const { mutate: logout } = useLogout()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
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
  const { data: stats } = useStats({ mailbox: mailboxIdentity, mailboxId })
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
  const isEmailDetailPath =
    /^\/email\/[^/]+/.test(location.pathname) ||
    /^\/mail\/[^/]+\/email\/[^/]+/.test(location.pathname)

  useEffect(() => {
    const previousTitle = document.title
    document.title = 'CogniMail Box'
    return () => { document.title = previousTitle || 'CogniMail Dashboard' }
  }, [])


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

  const getSearchContext = () => {
    const sourcePath = isEmailDetailPath
      ? (searchParams.get('from') || '/inbox')
      : `${location.pathname}${location.search}`
    const [basePath, baseQuery = ''] = sourcePath.split('?')
    const baseParams = new URLSearchParams(baseQuery)
    const mailSection = basePath.match(/^\/mail\/[^/]+\/([^/]+)/)?.[1] || ''

    let searchBase = '/inbox'
    if (basePath.startsWith('/sent') || mailSection === 'sent') searchBase = '/sent'
    else if (basePath.startsWith('/draft') || mailSection === 'drafts') searchBase = '/draft'

    const params = new URLSearchParams()
    if (searchBase === '/inbox') {
      const folder = mailSection === 'starred'
        ? 'starred'
        : mailSection === 'all'
          ? 'allmail'
          : mailSection === 'trash'
            ? 'trash'
            : baseParams.get('folder')
      const category = ['spam', 'phishing', 'malware'].includes(mailSection)
        ? mailSection
        : baseParams.get('category')
      if (folder) params.set('folder', folder)
      if (category) params.set('category', category)
    }

    return { searchBase, params }
  }

  const runSearch = () => {
    const value = searchValue.trim()
    const { searchBase, params } = getSearchContext()
    if (value) params.set('q', value)

    const query = params.toString()
    navigate(withMailbox(query ? `${searchBase}?${query}` : searchBase, mailboxIdentity, mailboxId))
  }

  const clearSearch = () => {
    setSearchValue('')
    const { searchBase, params } = getSearchContext()
    const query = params.toString()
    navigate(withMailbox(query ? `${searchBase}?${query}` : searchBase, mailboxIdentity, mailboxId))
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
            <img src={logoImg} alt="CogniMail" />
            <span className={styles.brandText}><b>CogniMail</b><small>{mailboxIdentity || 'Secure Mail'}</small></span>
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
              placeholder={t('gmail.searchPlaceholder')}
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              onKeyDown={handleSearch}
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setSearchFocused(false)}
              id="search-input"
            />
            {searchValue && (
              <button
                className={styles.searchIcon}
                onClick={clearSearch}
                title={t('gmail.clearSearch')}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* RIGHT: icons matching Gmail order in UI_user_page.png */}
        <div className={styles.topbarRight}>
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
              {navItem('/sent', <Send size={18} color="#444746" />, 'Terkirim', stats?.sent)}
              {navItem('/draft', <FileText size={18} color="#444746" />, 'Draf', stats?.draft)}
              {navItem('/inbox?folder=allmail', <Mail size={18} color="#444746" />, 'Semua Email', stats?.total)}

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

        <main className={styles.main}>{children}</main>

      </div>

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
