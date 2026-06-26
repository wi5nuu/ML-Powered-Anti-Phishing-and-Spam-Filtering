import { useState, useEffect, useRef } from 'react'
import { NavLink, useNavigate, useSearchParams, useLocation } from 'react-router-dom'
import { useTheme } from '../../hooks/useTheme'
import { useMe, useLogout } from '../../api/auth'
import { useStats } from '../../api/metrics'
import api from '../../api/client'
import {
  Menu, Search, HelpCircle, Settings, Sun, Moon, User,
  Pencil, Inbox, Star, Clock, Send, FileText,
  ShoppingBag, BarChart2, BookOpen, Plus, Grid3X3,
  Shield, ClipboardList, AlertCircle, Users, Flag
} from 'lucide-react'
import ComposeModal from './ComposeModal'
import AppGrid from './AppGrid'
import SearchFilterPanel from './SearchFilterPanel'
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
  const [appGridOpen, setAppGridOpen] = useState(false)
  const [filterOpen, setFilterOpen] = useState(false)
  const [showAllCats, setShowAllCats] = useState(false)
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
    const handleOpenCompose = () => setComposeOpen(true)
    window.addEventListener('open-compose', handleOpenCompose)
    return () => window.removeEventListener('open-compose', handleOpenCompose)
  }, [])

  const user = me?.user

  const handleSearch = (e) => {
    if (e.key === 'Enter' && searchValue.trim()) {
      navigate(`/inbox?q=${encodeURIComponent(searchValue.trim())}`)
    }
  }

  // Close panels on outside click
  const handleShellClick = (e) => {
    if (!e.target.closest(`.${styles.avatarWrap}`)) {
      setUserMenuOpen(false)
    }
  }

  const navItem = (to, icon, label, count) => (
    <NavLink
      to={to}
      end
      className={({ isActive }) => `${styles.sidebarItem} ${isActive ? styles.active : ''}`}
    >
      <span className={styles.itemIcon}>{icon}</span>
      <span className={styles.itemLabel}>{label}</span>
      {count > 0 && <span className={styles.itemCount}>{count}</span>}
    </NavLink>
  )

  const currentCat = location.pathname === '/inbox' ? (searchParams.get('category') || null) : null
  const catItem = (category, label, color, count) => (
    <NavLink
      to={`/inbox?category=${category}`}
      className={`${styles.sidebarItem} ${currentCat === category ? styles.active : ''}`}
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
          <NavLink to="/inbox" className={styles.brand}>
            {/* Shield + checkmark logo */}
            <svg width="32" height="32" viewBox="0 0 40 40" fill="none">
              <circle cx="20" cy="20" r="20" fill="#f6f8fc"/>
              <path d="M20 6L8 11v9c0 6.07 5.12 11.74 12 13 6.88-1.26 12-6.93 12-13v-9L20 6z" fill="#EA4335"/>
              <path d="M20 6L8 11v9c0 6.07 5.12 11.74 12 13V6z" fill="#c5221f"/>
              <path d="M16 20l3 3 6-6" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span className={styles.brandText}>LTI <b>Anti-Phishing</b></span>
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
              onClick={(e) => { e.stopPropagation(); setFilterOpen((v) => !v); setAppGridOpen(false) }}
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
            onClick={() => navigate('/help')}
            title="Bantuan & Dokumentasi"
            id="help-btn"
          >
            <HelpCircle size={20} />
          </button>
          <button
            className={styles.iconRound}
            onClick={() => navigate('/metrics')}
            title="Pengaturan & Metrik"
            id="metrics-btn"
          >
            <Settings size={20} />
          </button>
          <button
            className={styles.iconRound}
            onClick={toggle}
            title={theme === 'dark' ? 'Mode terang' : 'Mode gelap'}
            id="theme-toggle-btn"
          >
            {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
          </button>
          <div style={{ position: 'relative' }}>
            <button
              className={styles.iconRound}
              title="Pintasan Aplikasi"
              id="apps-grid-btn"
              onClick={(e) => { e.stopPropagation(); setAppGridOpen((v) => !v); setUserMenuOpen(false); setFilterOpen(false) }}
              style={appGridOpen ? { background: 'var(--border-light)' } : {}}
            >
              <Grid3X3 size={18} />
            </button>
            <AppGrid
              open={appGridOpen}
              onClose={() => setAppGridOpen(false)}
              user={user}
            />
          </div>

          {user ? (
            <div className={styles.avatarWrap}>
              <div
                className={styles.avatar}
                onClick={() => setUserMenuOpen((v) => !v)}
                title={`${user.username} · ${user.role}`}
                id="user-avatar-btn"
              >
                {user.username[0].toUpperCase()}
              </div>
              {userMenuOpen && (
                <div className={styles.userMenu}>
                  <div className={styles.userMenuHeader} onClick={() => { navigate('/profile'); setUserMenuOpen(false) }} style={{ cursor: 'pointer' }}>
                    <div className={styles.userMenuAvatar}>
                      {user.username[0].toUpperCase()}
                    </div>
                    <div>
                      <div className={styles.userMenuName}>{user.username}</div>
                      <div className={styles.userMenuRole}>{user.role}</div>
                    </div>
                  </div>
                  <div className={styles.userMenuDivider} />
                  <button
                    className={styles.userMenuItem}
                    onClick={() => { navigate('/profile'); setUserMenuOpen(false) }}
                    id="menu-profile-btn"
                  >
                    <User size={16} />
                    <span>Profil Saya</span>
                  </button>
                  <button
                    className={styles.userMenuItem}
                    onClick={() => { navigate('/metrics'); setUserMenuOpen(false) }}
                    id="menu-metrics-btn"
                  >
                    <BarChart2 size={16} />
                    <span>Dashboard Metrik</span>
                  </button>
                  <button
                    className={styles.userMenuItem}
                    onClick={() => { navigate('/help'); setUserMenuOpen(false) }}
                    id="menu-help-btn"
                  >
                    <BookOpen size={16} />
                    <span>Dokumentasi</span>
                  </button>
                  <button
                    className={styles.userMenuItem}
                    onClick={() => { setReportOpen(true); setUserMenuOpen(false) }}
                  >
                    <AlertCircle size={16} />
                    <span>Lapor Masalah</span>
                  </button>
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
            <button className={styles.composeBtn} id="compose-btn" onClick={() => setComposeOpen(true)}>
              <Pencil size={20} color="#EA4335" />
              <span>Tulis</span>
            </button>

            {user?.role === 'superadmin' ? (
              <>
                {navItem('/admin', <Shield size={18} />, 'Admin Panel', 0)}
                {navItem('/admin?tab=users', <Users size={18} />, 'Users', 0)}
                {navItem('/admin?tab=reports', <Flag size={18} />, 'Laporan', 0)}

                <div className={styles.divider} />

                {navItem('/audit', <ClipboardList size={18} />, 'Audit Log', 0)}
                {navItem('/settings', <Settings size={18} />, 'Pengaturan', 0)}

                <div className={styles.divider} />

                <div className={styles.sidebarHeading}>Monitoring</div>
                {navItem('/metrics', <BarChart2 size={18} />, 'Metrik Sistem', 0)}
              </>
            ) : user?.role === 'admin' ? (
              <>
                {navItem('/admin', <Shield size={18} />, 'Admin Panel', 0)}
                {navItem('/admin?tab=reports', <Flag size={18} />, 'Laporan', 0)}

                <div className={styles.divider} />

                {navItem('/audit', <ClipboardList size={18} />, 'Audit Log', 0)}
                {navItem('/settings', <Settings size={18} />, 'Pengaturan', 0)}

                <div className={styles.divider} />

                <div className={styles.sidebarHeading}>Monitoring</div>
                {navItem('/metrics', <BarChart2 size={18} />, 'Metrik Sistem', 0)}
              </>
            ) : (
              <>
                {navItem('/inbox', <Inbox size={18} />, 'Kotak Masuk', stats?.quarantine || 0)}
                {navItem('/starred', <Star size={18} />, 'Berbintang', 0)}
                {navItem('/snoozed', <Clock size={18} />, 'Ditunda', 0)}
                {navItem('/sent', <Send size={18} />, 'Terkirim', 0)}
                {navItem('/draft', <FileText size={18} />, 'Draf', 0)}

                <div className={styles.divider} />

                {navItem('/pembelian', <ShoppingBag size={18} />, 'Pembelian', 0)}
                {navItem('/metrics', <BarChart2 size={18} />, 'Metrik', 0)}
                {navItem('/help', <BookOpen size={18} />, 'Dokumentasi', 0)}
                {navItem('/analyzer', <Shield size={18} />, 'Manual Analyzer', 0)}

                <div className={styles.divider} />

                <div className={styles.sidebarHeading}>Kategori</div>

                <NavLink to="/inbox" end className={styles.sidebarItem}>
                  <span className={styles.labelDot} style={{ background: '#34a853' }} />
                  <span className={styles.itemLabel}>Inbox</span>
                  {stats?.clean > 0 && <span className={styles.itemCount}>{stats.clean}</span>}
                </NavLink>

                {catItem('spam', 'Spam', '#f29900', stats?.categories?.spam || 0)}

                {catItem('phishing', 'Phishing', '#EA4335', stats?.categories?.phishing || 0)}

                {showAllCats && (
                  <>
                    <div className={styles.divider} />
                    {catItem('transaction', 'Transaction', '#34a853', stats?.categories?.transaction || 0)}
                    {catItem('customer_service', 'Customer Service', '#1a73e8', stats?.categories?.customer_service || 0)}
                    {catItem('internal_document', 'Internal Document', '#34a853', stats?.categories?.internal_document || 0)}
                    {catItem('b2b', 'B2B', '#34a853', stats?.categories?.b2b || 0)}
                    {catItem('malware', 'Malware', '#EA4335', stats?.categories?.malware || 0)}
                  </>
                )}

                <div
                  className={styles.sidebarItem}
                  style={{ cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.8rem' }}
                  onClick={() => setShowAllCats(!showAllCats)}
                >
                  <span className={styles.itemIcon}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                      {showAllCats
                        ? <path d="M19 13H5v-2h14v2z"/>
                        : <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
                      }
                    </svg>
                  </span>
                  <span>{showAllCats ? 'Ciutkan' : 'Lihat Lengkap'}</span>
                </div>
              </>
            )}
          </nav>
        )}

        {/* MAIN CONTENT */}
        <main className={styles.main}>{children}</main>
      </div>
      <ComposeModal open={composeOpen} onClose={() => setComposeOpen(false)} />

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
