import { useState, useEffect } from 'react'
import { NavLink, useNavigate, useSearchParams, useLocation } from 'react-router-dom'
import { useTheme } from '../../hooks/useTheme'
import { useMe, useLogout } from '../../api/auth'
import { useStats } from '../../api/metrics'
import api from '../../api/client'
import {
  Menu, Search, Settings, Sun, Moon, User,
  Pencil, Inbox, Send, BarChart2,
  Shield, Flag,
  Star, FileText, Mail, Trash2, ChevronDown, ChevronRight
} from 'lucide-react'
import ComposeModal from './ComposeModal'
import { clearMailboxSession, getActiveMailbox, getActiveMailboxId, setMailboxSession, withMailbox } from '../../utils/mailbox'
import styles from './GmailShell.module.css'

export default function GmailShell({ children }) {
  const { theme, toggle } = useTheme()
  const { data: me } = useMe()
  const { data: stats } = useStats()
  const { mutate: logout } = useLogout()
  const [sidebarOpen, setSidebarOpen] = useState(true)
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
  const activeMailbox = getActiveMailbox(searchParams)
  const activeMailboxId = getActiveMailboxId(searchParams)
  const userMailboxEmail = user?.role === 'mailbox' ? user?.mailbox_email || user?.username : ''
  const userMailboxId = user?.role === 'mailbox' ? user?.mailbox_id || '' : ''
  const mailboxIdentity = activeMailbox || userMailboxEmail
  const mailboxId = activeMailboxId || userMailboxId
  const displayIdentity = mailboxIdentity || user?.username || ''
  const displayRole = mailboxIdentity ? 'Mailbox perusahaan' : user?.role
  const displayInitial = (displayIdentity || 'U')[0].toUpperCase()
  const hasMailboxIdentity = Boolean(mailboxId && mailboxIdentity)
  const hasTopbarIdentity = Boolean(user || hasMailboxIdentity)

  useEffect(() => {
    setExpiredLoginOpen(Boolean(mailboxId && searchParams.get('expired') === '1'))
  }, [mailboxId, searchParams])

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
      setExpiredError(err.response?.data?.detail || 'Login mailbox gagal. Periksa password mailbox.')
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

  const handleLogoutClick = () => {
    if (mailboxIdentity) {
      // Mailbox logout: clear the mailbox_token cookie on the server (NOT access_token)
      // and clear the localStorage session. Dashboard session is NOT affected.
      api.post('/mailboxes/logout').catch(() => {})
      clearMailboxSession(mailboxId || mailboxIdentity, mailboxIdentity)
      setUserMenuOpen(false)
      const target = mailboxId ? `/mail/${encodeURIComponent(mailboxId)}/login` : '/mailbox-login'
      navigate(target, { replace: true })
      return
    }
    // Dashboard logout: clears the server access_token cookie (handled by useLogout).
    logout()
  }

  const runSearch = () => {
    const value = searchValue.trim()
    const params = new URLSearchParams()
    if (value) params.set('q', value)
    const query = params.toString()
    navigate(withMailbox(query ? `/inbox?${query}` : '/inbox', mailboxIdentity, mailboxId))
  }

  const clearSearch = () => {
    setSearchValue('')
    navigate(withMailbox('/inbox', mailboxIdentity, mailboxId))
  }

  const handleSearch = (e) => {
    if (e.key === 'Enter') runSearch()
  }

  const isEmailDetailPath = location.pathname.startsWith('/email/')
    || /^\/mail\/[^/]+\/email\//.test(location.pathname)

  // Close panels on outside click
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
      {count > 0 && <span className={styles.itemCount}>{count}</span>}
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
      {count > 0 && <span className={styles.itemCount} style={{ color }}>{count}</span>}
    </NavLink>
  )

  return (
    <div className={styles.shell} onClick={handleShellClick}>
      {/* ═══ TOP BAR ═══ */}
      <header className={styles.topbar}>
        {/* LEFT: hamburger + brand */}
        <div className={styles.topbarLeft}>
          <button
            className={styles.iconRound}
            onClick={() => setSidebarOpen((v) => !v)}
            title="Menu utama"
            id="sidebar-toggle-btn"
          >
            <Menu size={20} />
          </button>
          <NavLink to={withMailbox('/inbox', mailboxIdentity, mailboxId)} className={styles.brand}>
            {/* Shield + checkmark logo */}
            <svg width="32" height="32" viewBox="0 0 40 40" fill="none">
              <circle cx="20" cy="20" r="20" fill="#f6f8fc" />
              <path d="M20 6L8 11v9c0 6.07 5.12 11.74 12 13 6.88-1.26 12-6.93 12-13v-9L20 6z" fill="#EA4335" />
              <path d="M20 6L8 11v9c0 6.07 5.12 11.74 12 13V6z" fill="#c5221f" />
              <path d="M16 20l3 3 6-6" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className={styles.brandText}>CogniMail</span>
          </NavLink>
        </div>

        {/* CENTER: search bar */}
        <div className={styles.searchWrap} style={{ position: 'relative' }}>
          <div className={`${styles.searchBar} ${searchFocused ? styles.searchBarFocused : ''}`}>
            <button className={styles.searchIcon} title="Cari" onClick={runSearch}>
              <Search size={20} />
            </button>
            <input
              type="text"
              placeholder="Telusuri email..."
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
                title="Hapus pencarian"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* RIGHT: icons matching Gmail order */}
        <div className={styles.topbarRight}>
          <button
            className={styles.iconRound}
            onClick={toggle}
            title={theme === 'dark' ? 'Mode terang' : 'Mode gelap'}
            id="theme-toggle-btn"
          >
            {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
          </button>

          {hasTopbarIdentity ? (
            <div className={styles.avatarWrap}>
              <div
                className={styles.avatar}
                onClick={() => setUserMenuOpen((v) => !v)}
                title={`${displayIdentity} · ${displayRole}`}
                id="user-avatar-btn"
              >
                {displayInitial}
              </div>
              {userMenuOpen && (
                <div className={styles.userMenu}>
                  <div className={styles.userMenuHeader}>
                    <div className={styles.userMenuAvatar}>
                      {displayInitial}
                    </div>
                    <div>
                      <div className={styles.userMenuName}>{displayIdentity}</div>
                      <div className={styles.userMenuRole}>{displayRole}</div>
                    </div>
                  </div>
                  <div className={styles.userMenuDivider} />
                  <button
                    className={styles.userMenuItem}
                    onClick={() => { navigate(withMailbox('/profile', mailboxIdentity, mailboxId)); setUserMenuOpen(false) }}
                    id="menu-profile-btn"
                  >
                    <User size={16} />
                    <span>Profil Saya</span>
                  </button>
                  <button
                    className={styles.userMenuItem}
                    onClick={() => { navigate(withMailbox('/metrics', mailboxIdentity, mailboxId)); setUserMenuOpen(false) }}
                    id="menu-metrics-btn"
                  >
                    <BarChart2 size={16} />
                    <span>Dashboard Metrik</span>
                  </button>
                  <button
                    className={styles.userMenuItem}
                    onClick={() => { setReportOpen(true); setUserMenuOpen(false) }}
                  >
                    <Flag size={16} />
                    <span>Lapor Masalah</span>
                  </button>
                  {!mailboxIdentity && (
                    <button
                      className={styles.userMenuItem}
                      onClick={() => { navigate('/settings'); setUserMenuOpen(false) }}
                      id="menu-settings-btn"
                    >
                      <Settings size={16} />
                      <span>Pengaturan</span>
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
                    <span>Keluar</span>
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
              Masuk
            </button>
          )}
        </div>
      </header>

      {/* ═══ BODY ═══ */}
      <div className={styles.body}>
        {/* SIDEBAR */}
        {sidebarOpen && (
          <nav className={styles.sidebar}>
            {/* Compose button */}
            <button className={styles.composeBtn} id="compose-btn" onClick={() => {
              setComposeDraft(null)
              setComposeThreadId('')
              setComposeParentEmailId('')
              setComposeMode('new')
              setComposeOpen(true)
            }}>
              <Pencil size={20} color="#EA4335" />
              <span>Tulis</span>
            </button>

            {navItem('/inbox', <Inbox size={18} />, 'Kotak Masuk', 0)}
            {navItem('/inbox?folder=starred', <Star size={18} />, 'Berbintang', 0)}
            {navItem('/sent', <Send size={18} />, 'Terkirim', 0)}
            {navItem('/draft', <FileText size={18} />, 'Draf', 0)}
            {navItem('/inbox?folder=allmail', <Mail size={18} />, 'Semua Email', 0)}
            {navItem('/inbox?folder=trash', <Trash2 size={18} />, 'Sampah', 0)}

            <div className={styles.divider} />
            <div className={styles.sidebarHeading}>Label Ancaman</div>
            <button
              className={`${styles.sidebarItem} ${styles.sidebarButton} ${currentCat ? styles.active : ''}`}
              onClick={() => setThreatOpen((v) => !v)}
            >
              <span className={styles.itemIcon}><Shield size={18} /></span>
              <span className={styles.itemLabel}>Karantina</span>
              <span className={styles.expandIcon}>
                {threatOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
              </span>
            </button>
            {threatOpen && (
              <div className={styles.subNav}>
                {catItem('phishing', 'Phishing', '#EA4335', 0)}
                {catItem('spam', 'Spam', '#f29900', 0)}
                {catItem('malware', 'Malware', '#8b1a10', 0)}
              </div>
            )}

            <div className={styles.divider} />
            <div className={styles.sidebarHeading}>Sistem</div>
            <button className={`${styles.sidebarItem} ${styles.sidebarButton}`} onClick={() => setReportOpen(true)}>
              <span className={styles.itemIcon}><Flag size={18} /></span>
              <span className={styles.itemLabel}>Lapor Masalah</span>
            </button>
            {!mailboxIdentity && (
              <button
                className={`${styles.sidebarItem} ${styles.sidebarButton}`}
                onClick={() => navigate('/settings')}
              >
                <span className={styles.itemIcon}><Settings size={18} /></span>
                <span className={styles.itemLabel}>Pengaturan</span>
              </button>
            )}
          </nav>
        )}

        {/* MAIN CONTENT */}
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
            <h3>Sesi mailbox berakhir</h3>
            <p>Masuk kembali sebagai <strong>{mailboxIdentity}</strong> untuk melanjutkan webmail.</p>
            {expiredError && <div className={styles.sessionError}>{expiredError}</div>}
            <input
              type="password"
              value={expiredPassword}
              onChange={(event) => setExpiredPassword(event.target.value)}
              placeholder="Password mailbox"
              autoComplete="current-password"
              autoFocus
              required
            />
            <div className={styles.sessionActions}>
              <button type="submit" className={styles.sessionSubmit} disabled={expiredLoading}>
                {expiredLoading ? 'Memproses...' : 'Masuk lagi'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Report Modal */}
      {reportOpen && (
        <div className={styles.overlay} onClick={() => setReportOpen(false)}>
          <div className={styles.reportModal} onClick={(e) => e.stopPropagation()}>
            <h3>Lapor Masalah ke Admin</h3>
            {reportMsg && <div className={styles.reportMsg}>{reportMsg}</div>}
            <select
              value={reportCategory}
              onChange={(e) => setReportCategory(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 6, background: 'var(--surface)', color: 'var(--text)', fontSize: '0.8125rem', marginBottom: 8, fontFamily: 'inherit' }}
            >
              <option value="question">Pertanyaan / Bantuan</option>
              <option value="bug">Laporkan Bug / Error</option>
              <option value="false_positive">False Positive (salah karantina)</option>
              <option value="access">Permintaan Akses</option>
              <option value="other">Lainnya</option>
            </select>
            <input
              placeholder="Judul masalah"
              value={reportSubject}
              onChange={(e) => setReportSubject(e.target.value)}
            />
            <textarea
              placeholder="Jelaskan masalah yang Anda alami..."
              value={reportMessage}
              onChange={(e) => setReportMessage(e.target.value)}
              rows={4}
            />
            <div className={styles.reportActions}>
              <button onClick={() => { setReportOpen(false); setReportSubject(''); setReportMessage(''); setReportCategory('other'); setReportMsg('') }}>
                Batal
              </button>
              <button
                className={styles.reportSend}
                disabled={!reportSubject || !reportMessage}
                onClick={async () => {
                  try {
                    await api.post('/reports', { subject: reportSubject, message: reportMessage, category: reportCategory })
                    setReportMsg('Laporan terkirim! Admin akan segera meninjau.')
                    setReportSubject(''); setReportMessage(''); setReportCategory('other')
                    setTimeout(() => { setReportOpen(false); setReportMsg('') }, 2000)
                  } catch (e) {
                    setReportMsg('Gagal mengirim. Coba lagi.')
                  }
                }}
              >
                Kirim Laporan
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
