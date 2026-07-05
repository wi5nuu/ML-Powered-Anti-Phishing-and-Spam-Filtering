import { useState, useEffect, useRef } from 'react'
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
import SearchFilterPanel from './SearchFilterPanel'
import { getActiveMailbox, getActiveMailboxId, withMailbox } from '../../utils/mailbox'
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
  const [filterOpen, setFilterOpen] = useState(false)
  const [threatOpen, setThreatOpen] = useState(true)
  const [reportOpen, setReportOpen] = useState(false)
  const [reportSubject, setReportSubject] = useState('')
  const [reportMessage, setReportMessage] = useState('')
  const [reportCategory, setReportCategory] = useState('other')
  const [reportMsg, setReportMsg] = useState('')
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const searchWrapRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    const handleOpenCompose = (event) => {
      setComposeDraft(event.detail || null)
      setComposeOpen(true)
    }
    window.addEventListener('open-compose', handleOpenCompose)
    return () => window.removeEventListener('open-compose', handleOpenCompose)
  }, [])

  const user = me?.user
  const activeMailbox = getActiveMailbox(searchParams)
  const activeMailboxId = getActiveMailboxId(searchParams)
  const displayIdentity = activeMailbox || user?.username || ''
  const displayRole = activeMailbox ? 'Mailbox perusahaan' : user?.role
  const displayInitial = (displayIdentity || 'U')[0].toUpperCase()

  const handleSearch = (e) => {
    if (e.key === 'Enter' && searchValue.trim()) {
      navigate(withMailbox(`/inbox?q=${encodeURIComponent(searchValue.trim())}`, activeMailbox, activeMailboxId))
    }
  }

  // Close panels on outside click
  const handleShellClick = (e) => {
    if (!e.target.closest(`.${styles.avatarWrap}`)) {
      setUserMenuOpen(false)
    }
  }

  const isNavActive = (to) => {
    const [path, query = ''] = to.split('?')
    const activeSource = location.pathname.startsWith('/email/')
      ? searchParams.get('from')
      : null
    const [currentPath, currentQuery = ''] = (activeSource || location.pathname).split('?')
    const currentParams = activeSource ? new URLSearchParams(currentQuery) : searchParams

    if (currentPath !== path) return false

    const targetParams = new URLSearchParams(query)
    if (path === '/inbox') {
      return (targetParams.get('filter') || '') === (currentParams.get('filter') || '')
        && (targetParams.get('category') || '') === (currentParams.get('category') || '')
        && (targetParams.get('folder') || '') === (currentParams.get('folder') || '')
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
      to={withMailbox(to, activeMailbox, activeMailboxId)}
      end
      className={() => `${styles.sidebarItem} ${isNavActive(to) ? styles.active : ''}`}
    >
      <span className={styles.itemIcon}>{icon}</span>
      <span className={styles.itemLabel}>{label}</span>
      {count > 0 && <span className={styles.itemCount}>{count}</span>}
    </NavLink>
  )

  const activeSourcePath = location.pathname.startsWith('/email/')
    ? searchParams.get('from') || ''
    : `${location.pathname}${location.search}`
  const activeSourceParams = new URLSearchParams(activeSourcePath.split('?')[1] || '')
  const currentCat = activeSourcePath.startsWith('/inbox') ? (activeSourceParams.get('category') || null) : null
  const catItem = (category, label, color, count) => (
    <NavLink
      to={withMailbox(`/inbox?category=${category}`, activeMailbox, activeMailboxId)}
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
          <NavLink to={withMailbox('/inbox', activeMailbox, activeMailboxId)} className={styles.brand}>
            {/* Shield + checkmark logo */}
            <svg width="32" height="32" viewBox="0 0 40 40" fill="none">
              <circle cx="20" cy="20" r="20" fill="#f6f8fc"/>
              <path d="M20 6L8 11v9c0 6.07 5.12 11.74 12 13 6.88-1.26 12-6.93 12-13v-9L20 6z" fill="#EA4335"/>
              <path d="M20 6L8 11v9c0 6.07 5.12 11.74 12 13V6z" fill="#c5221f"/>
              <path d="M16 20l3 3 6-6" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span className={styles.brandText}>CogniMail</span>
          </NavLink>
        </div>

        {/* CENTER: search bar */}
        <div className={styles.searchWrap} style={{ position: 'relative' }}>
          <div className={`${styles.searchBar} ${searchFocused ? styles.searchBarFocused : ''}`}>
            <button className={styles.searchIcon} title="Cari">
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
                onClick={() => setSearchValue('')}
                title="Hapus pencarian"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                </svg>
              </button>
            )}
            <button
              className={styles.searchIcon}
              title="Filter penelusuran"
              id="search-filter-btn"
              onClick={(e) => { e.stopPropagation(); setFilterOpen((v) => !v) }}
              style={filterOpen ? { background: 'rgba(26,115,232,.12)', color: '#1a73e8' } : {}}
            >
              {/* tune/sliders icon */}
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M10 18h4v-2h-4v2zm-7-5v2h18v-2H3zm3-4v2h12V9H6z"/>
              </svg>
            </button>
          </div>
          <SearchFilterPanel
            open={filterOpen}
            onClose={() => setFilterOpen(false)}
          />
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

          {user ? (
            <div className={styles.avatarWrap}>
              <div
                className={styles.avatar}
                onClick={() => setUserMenuOpen((v) => !v)}
                title={displayIdentity}
                id="user-avatar-btn"
              >
                {displayInitial}
              </div>
              {userMenuOpen && (
                <div className={styles.userMenu}>
                  <div className={styles.userMenuHeader} onClick={() => { navigate(withMailbox('/profile', activeMailbox, activeMailboxId)); setUserMenuOpen(false) }} style={{ cursor: 'pointer' }}>
                    <div className={styles.userMenuAvatar}>
                      {displayInitial}
                    </div>
                    <div>
                      <div className={styles.userMenuName}>{displayIdentity}</div>
                      {activeMailbox && <div className={styles.userMenuRole}>{displayRole}</div>}
                    </div>
                  </div>
                  <div className={styles.userMenuDivider} />
                  <button
                    className={styles.userMenuItem}
                    onClick={() => { navigate(withMailbox('/profile', activeMailbox, activeMailboxId)); setUserMenuOpen(false) }}
                    id="menu-profile-btn"
                  >
                    <User size={16} />
                    <span>Profil Saya</span>
                  </button>
                  <button
                    className={styles.userMenuItem}
                    onClick={() => { navigate(withMailbox('/metrics', activeMailbox, activeMailboxId)); setUserMenuOpen(false) }}
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
                  {!activeMailbox && (
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
                    onClick={() => logout()}
                    id="logout-btn"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/>
                    </svg>
                    <span>Keluar</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button
              className={styles.loginBtn}
              onClick={() => navigate('/login')}
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
            <button className={styles.composeBtn} id="compose-btn" onClick={() => { setComposeDraft(null); setComposeOpen(true) }}>
              <Pencil size={20} color="#EA4335" />
              <span>Tulis</span>
            </button>

            {navItem('/inbox', <Inbox size={18} />, 'Kotak Masuk', 0)}
            {navItem('/inbox?folder=starred', <Star size={18} />, 'Berbintang', 0)}
            {navItem('/sent', <Send size={18} />, 'Terkirim', 0)}
            {navItem('/inbox?folder=draft', <FileText size={18} />, 'Draf', 0)}
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
            {!activeMailbox && (
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
        onClose={() => { setComposeOpen(false); setComposeDraft(null) }}
        fromMailbox={activeMailbox}
        initialDraft={composeDraft}
      />

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
