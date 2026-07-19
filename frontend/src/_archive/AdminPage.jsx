import { useState, useEffect } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import AdminShell from '../components/layout/AdminShell'
import api from '../api/client'
import { useMe } from '../api/auth'
import { Users, Shield, Mail, Activity, Plus, X, Check, AlertCircle, Reply, ChevronDown, ChevronUp, Flag, ChevronRight, Settings, Save, Eye, EyeOff, Copy, AtSign, TrendingUp, TrendingDown, Inbox, Server, Wifi, Database, Cpu, Clock, CheckCircle2, XCircle, AlertTriangle, ShieldCheck, ShieldAlert, Zap, FileText, ListFilter, ArrowUpRight, MoreVertical, KeyRound, Forward, MailCheck, BarChart3 } from 'lucide-react'
import SuperadminDashboardOverview from './SuperadminDashboardOverview'
import SuperadminUserManagement from './SuperadminUserManagement'
import SuperadminMailboxManagement from './SuperadminMailboxManagement'
import SuperadminSystemHealth from './SuperadminSystemHealth'
import SuperadminReports from './SuperadminReports'
import AdminUserManagement from './AdminUserManagement'
import AdminMailboxManagement from './AdminMailboxManagement'
import AdminQuarantineReview from './AdminQuarantineReview'
import AdminDetectionLogs from './AdminDetectionLogs'
import AdminSettingsPage from './AdminSettings'
import SuperadminSettingsPage from './SuperadminSettings'
import SuperadminTracking from './SuperadminTracking'
import SuperadminSpamStats from './SuperadminSpamStats'
import SuperadminCompanies from './SuperadminCompanies'
import { DEFAULT_MAIL_DOMAIN, getMailboxSession, getMailDomain, getMailboxes, setMailDomain, setMailboxDirectory, setMailboxes } from '../utils/mailbox'
import styles from './AdminPage.module.css'

const CATEGORY_LABELS = { bug: 'Bug / Error', question: 'Pertanyaan', access: 'Akses', false_positive: 'False Positive', other: 'Lainnya' }
const CATEGORY_COLORS = { bug: '#ea4335', question: '#1a73e8', access: '#f29900', false_positive: '#34a853', other: '#5f6368' }
const PRIORITY_COLORS = { low: '#5f6368', normal: '#1a73e8', high: '#f29900', urgent: '#ea4335' }
export default function AdminPage() {
  const { data: me } = useMe()
  const navigate = useNavigate()
  const { tab: tabParam } = useParams()
  const tab = tabParam || 'overview'
  const isSuper = me?.user?.role === 'superadmin'
  const isAdmin = me?.user?.role === 'admin'
  const basePath = isSuper ? '/superadmin/dashboard' : '/admin/dashboard'
  // Safety: redirect unauthorized users away from tabs
  useEffect(() => {
    if (tab === 'users' && !isSuper && !isAdmin && me) {
      navigate(basePath, { replace: true })
    }
    if (tab === 'email' && !isSuper && !isAdmin && me) {
      navigate(basePath, { replace: true })
    }
    if (tab === 'track' && !isSuper && me) {
      navigate(basePath, { replace: true })
    }
    if (tab === 'health' && !isSuper && me) {
      navigate(basePath, { replace: true })
    }
    if (tab === 'companies' && !isSuper && me) {
      navigate(basePath, { replace: true })
    }
    if (tab === 'review' && !isSuper && !isAdmin && me) {
      navigate(basePath, { replace: true })
    }
    if (tab === 'logs' && !isSuper && !isAdmin && me) {
      navigate(basePath, { replace: true })
    }
  }, [tab, isSuper, isAdmin, me])

  const [logs, setLogs] = useState([])
  const [stats, setStats] = useState(null)
  const [adminEmailStats, setAdminEmailStats] = useState(null)
  const [reports, setReports] = useState([])
  const [msg, setMsg] = useState('')
  const [expandedReport, setExpandedReport] = useState(null)
  const [replyText, setReplyText] = useState('')
  const [filterCategory, setFilterCategory] = useState('all')
  const [mailDomain, setMailDomainState] = useState(() => getMailDomain())
  const [mailboxRows, setMailboxRows] = useState([])
  const [mailboxes, setMailboxState] = useState(() => getMailboxes())
  const [mailboxInput, setMailboxInput] = useState('')
  const [mailboxPassword, setMailboxPassword] = useState('')
  const [mailboxSenderName, setMailboxSenderName] = useState('')
  const [showMailboxPassword, setShowMailboxPassword] = useState(false)
  const [createMailboxOpen, setCreateMailboxOpen] = useState(false)
  const [mailboxError, setMailboxError] = useState('')
  const [domainDraft, setDomainDraft] = useState(() => getMailDomain())
  const [domainError, setDomainError] = useState('')
  const [mailboxMenuId, setMailboxMenuId] = useState(null)
  const [passwordMailbox, setPasswordMailbox] = useState(null)
  const [passwordDraft, setPasswordDraft] = useState('')
  const [showPasswordDraft, setShowPasswordDraft] = useState(false)
  const [forwarderMailbox, setForwarderMailbox] = useState(null)
  const [forwarderTarget, setForwarderTarget] = useState('')
  const [forwarderKeepCopy, setForwarderKeepCopy] = useState(true)
  const [deleteMailboxTarget, setDeleteMailboxTarget] = useState(null)

  const fetchData = () => {
    api.get('/admin/stats').then((r) => setStats(r.data)).catch(() => {})
    api.get('/admin/audit-logs').then((r) => setLogs(r.data)).catch(() => {})
    api.get('/admin/reports').then((r) => setReports(r.data)).catch(() => {})
    if (!isSuper && me?.user?.username) {
      api.get('/admin/my-emails').then((r) => setAdminEmailStats(r.data)).catch(() => {})
    }
  }

  const fetchMailboxes = async () => {
    try {
      const r = await api.get('/admin/mailboxes')
      const rows = Array.isArray(r.data) ? r.data : []
      setMailboxRows(rows)
      setMailboxDirectory(rows)
      const emails = rows.map((row) => row.email)
      setMailboxState(emails)
      setMailboxes(emails)
    } catch {
      const fallback = getMailboxes()
      setMailboxRows(fallback.map((email, index) => ({ id: `local-${index}`, email, domain: email.split('@')[1] || mailDomain })))
      setMailboxState(fallback)
    }
  }

  useEffect(() => { fetchData(); fetchMailboxes() }, [])

  const handleResolveReport = async (id) => {
    try {
      await api.put(`/admin/reports/${id}`, { status: 'resolved' })
      fetchData()
    } catch (e) { setMsg('Gagal update laporan') }
  }

  const handleReplyReport = async (id) => {
    if (!replyText.trim()) return
    try {
      await api.put(`/admin/reports/${id}`, { admin_reply: replyText.trim() })
      setReplyText('')
      setExpandedReport(null)
      fetchData()
    } catch (e) { setMsg('Gagal membalas laporan') }
  }

  const handleStatusChange = async (id, status) => {
    try {
      await api.put(`/admin/reports/${id}`, { status })
      fetchData()
    } catch (e) { setMsg('Gagal update status') }
  }

  const persistMailboxes = (next) => {
    setMailboxState(next)
    setMailboxes(next)
  }

  const passwordChecks = {
    length: mailboxPassword.length >= 8,
    lower: /[a-z]/.test(mailboxPassword),
    upper: /[A-Z]/.test(mailboxPassword),
    number: /\d/.test(mailboxPassword),
    symbol: /[^A-Za-z0-9]/.test(mailboxPassword),
    latin: mailboxPassword.length > 0 && /^[\x20-\x7E]+$/.test(mailboxPassword),
  }
  const passwordValid = Object.values(passwordChecks).every(Boolean)
  const actionPasswordChecks = {
    length: passwordDraft.length >= 8,
    lower: /[a-z]/.test(passwordDraft),
    upper: /[A-Z]/.test(passwordDraft),
    number: /\d/.test(passwordDraft),
    symbol: /[^A-Za-z0-9]/.test(passwordDraft),
    latin: passwordDraft.length > 0 && /^[\x20-\x7E]+$/.test(passwordDraft),
  }
  const actionPasswordValid = Object.values(actionPasswordChecks).every(Boolean)

  const handleAddMailbox = async () => {
    const localPart = mailboxInput.trim().toLowerCase().replace(/@.*$/, '')
    const email = `${localPart}@${mailDomain}`
    setMailboxError('')

    if (!/^[a-z0-9._%+-]+$/i.test(localPart)) {
      setMailboxError('Masukkan nama email yang valid.')
      return
    }
    if (!passwordValid) {
      setMailboxError('Password belum memenuhi semua persyaratan.')
      return
    }
    if (mailboxes.includes(email)) {
      setMailboxError('Email ini sudah ada.')
      return
    }

    try {
      await api.post('/admin/mailboxes', {
        email,
        domain: mailDomain,
        password: mailboxPassword,
        sender_name: mailboxSenderName,
      })
      await fetchMailboxes()
      setMailboxInput('')
      setMailboxPassword('')
      setMailboxSenderName('')
      setShowMailboxPassword(false)
      setCreateMailboxOpen(false)
      setMsg(`Email ${email} berhasil ditambahkan.`)
      setTimeout(() => setMsg(''), 4000)
    } catch (e) {
      setMailboxError(e.response?.data?.detail || 'Gagal menambahkan email.')
    }
  }

  const removeMailbox = async (row) => {
    try {
      if (typeof row.id === 'number') {
        await api.delete(`/admin/mailboxes/${row.id}`)
        await fetchMailboxes()
      } else {
        persistMailboxes(mailboxes.filter((item) => item !== row.email))
        setMailboxRows(mailboxRows.filter((item) => item.email !== row.email))
      }
      setMsg(`Email ${row.email} dihapus dari daftar.`)
      setTimeout(() => setMsg(''), 4000)
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Gagal menghapus mailbox.')
      setTimeout(() => setMsg(''), 4000)
    }
  }

  const openPasswordModal = (row) => {
    setMailboxMenuId(null)
    setPasswordMailbox(row)
    setPasswordDraft('')
    setShowPasswordDraft(false)
    setMailboxError('')
  }

  const updateMailboxPassword = async () => {
    if (!passwordMailbox || !actionPasswordValid) return
    setMailboxError('')
    try {
      await api.put(`/admin/mailboxes/${passwordMailbox.id}/password`, { password: passwordDraft })
      setMsg(`Password ${passwordMailbox.email} berhasil diubah.`)
      setPasswordMailbox(null)
      setPasswordDraft('')
      setTimeout(() => setMsg(''), 4000)
    } catch (e) {
      setMailboxError(e.response?.data?.detail || 'Gagal mengubah password mailbox.')
    }
  }

  const openForwarderModal = (row) => {
    setMailboxMenuId(null)
    setForwarderMailbox(row)
    setForwarderTarget(row.forward_to || '')
    setForwarderKeepCopy(row.forward_keep_copy ?? true)
    setMailboxError('')
  }

  const saveForwarder = async () => {
    if (!forwarderMailbox || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(forwarderTarget.trim())) {
      setMailboxError('Masukkan alamat email tujuan yang valid.')
      return
    }
    setMailboxError('')
    try {
      await api.put(`/admin/mailboxes/${forwarderMailbox.id}/forwarder`, {
        target: forwarderTarget.trim().toLowerCase(),
        enabled: true,
        keep_copy: forwarderKeepCopy,
      })
      await fetchMailboxes()
      setMsg(`Forwarder ${forwarderMailbox.email} berhasil dibuat.`)
      setForwarderMailbox(null)
      setForwarderTarget('')
      setMailboxError('')
      setTimeout(() => setMsg(''), 4000)
    } catch (e) {
      setMailboxError(e.response?.data?.detail || 'Gagal menyimpan forwarder.')
    }
  }

  const handleSaveDomain = () => {
    const clean = domainDraft.trim().toLowerCase().replace(/^@+/, '')
    setDomainError('')
    if (!/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(clean)) {
      setDomainError('Masukkan domain yang valid, contoh: zenime.my.id')
      return
    }
    const existingOutsideDomain = mailboxes.filter((email) => !email.endsWith(`@${clean}`))
    if (existingOutsideDomain.length > 0) {
      setDomainError(`Hapus atau sesuaikan mailbox lama terlebih dahulu: ${existingOutsideDomain.join(', ')}`)
      return
    }
    const saved = setMailDomain(clean)
    setMailDomainState(saved)
    setDomainDraft(saved)
    setMsg(`Domain email default diubah menjadi @${saved}.`)
    setTimeout(() => setMsg(''), 4000)
  }

  const openMailbox = (email, newWindow = false) => {
    const row = mailboxRows.find((item) => item.email === email)
    const mailboxId = String(row?.id || email)
    const hasSession = getMailboxSession(mailboxId, email)
    const target = hasSession
      ? `/mail/${encodeURIComponent(mailboxId)}/inbox`
      : `/mail/${encodeURIComponent(mailboxId)}/login`
    if (newWindow) {
      window.open(target, '_blank', 'noopener,noreferrer')
      return
    }
    navigate(target)
  }

  const openReports = reports.filter((r) => r.status === 'open')
  const filteredReports = filterCategory === 'all' ? reports : reports.filter((r) => r.category === filterCategory)

  const recentActivityIcons = {
    login: { icon: <Users size={14} />, color: '#2563EB', bg: '#EFF6FF' },
    mailbox_created: { icon: <Mail size={14} />, color: '#059669', bg: '#ECFDF5' },
    phishing: { icon: <ShieldAlert size={14} />, color: '#DC2626', bg: '#FEF2F2' },
    report: { icon: <FileText size={14} />, color: '#D97706', bg: '#FFFBEB' },
    default: { icon: <Activity size={14} />, color: '#6B7280', bg: '#F9FAFB' },
  }

  const getActivityMeta = (action = '') => {
    if (action.includes('login')) return recentActivityIcons.login
    if (action.includes('mailbox')) return recentActivityIcons.mailbox_created
    if (action.includes('phishing') || action.includes('quarantine')) return recentActivityIcons.phishing
    if (action.includes('report')) return recentActivityIcons.report
    return recentActivityIcons.default
  }

  const totalThreats = stats ? (stats.warn || 0) + (stats.quarantine || 0) : 0
  const totalEmails = stats ? Math.max(stats.total_emails || 1, 1) : 1
  const safePct = stats ? Math.round(((stats.clean || 0) / totalEmails) * 100) : 0
  const spamPct = stats ? Math.round(((stats.warn || 0) / totalEmails) * 100) : 0
  const quarantinePct = stats ? Math.round(((stats.quarantine || 0) / totalEmails) * 100) : 0

  return (
    <AdminShell>
      <div className={styles.page}>
        {msg && <div className={styles.msg}>{msg}</div>}

          <div className={styles.tabs}>
            <button className={`${styles.tab} ${tab === 'overview' ? styles.tabActive : ''}`} onClick={() => navigate(`${basePath}/overview`)}>Overview</button>
            {isSuper && <button className={`${styles.tab} ${tab === 'track' ? styles.tabActive : ''}`} onClick={() => navigate(`${basePath}/track`)}>Tracking</button>}
            <button className={`${styles.tab} ${tab === 'users' ? styles.tabActive : ''}`} onClick={() => navigate(`${basePath}/users`)}>Users</button>
            <button className={`${styles.tab} ${tab === 'activity' ? styles.tabActive : ''}`} onClick={() => navigate(`${basePath}/activity`)}>Activity</button>
            <button className={`${styles.tab} ${tab === 'email' ? styles.tabActive : ''}`} onClick={() => navigate(`${basePath}/email`)}>Mailboxes</button>
            <button className={`${styles.tab} ${tab === 'reports' ? styles.tabActive : ''}`} onClick={() => navigate(`${basePath}/reports`)}>{isSuper ? 'Laporan' : 'Reports'}</button>
            {!isSuper && <button className={`${styles.tab} ${tab === 'review' ? styles.tabActive : ''}`} onClick={() => navigate(`${basePath}/review`)}>Review</button>}
            {!isSuper && <button className={`${styles.tab} ${tab === 'logs' ? styles.tabActive : ''}`} onClick={() => navigate(`${basePath}/logs`)}>Logs</button>}
            {isSuper && <button className={`${styles.tab} ${tab === 'health' ? styles.tabActive : ''}`} onClick={() => navigate(`${basePath}/health`)}>Health</button>}
            <button className={`${styles.tab} ${tab === 'settings' ? styles.tabActive : ''}`} onClick={() => navigate(`${basePath}/settings`)}>Settings</button>
          </div>

        {tab === 'overview' && isSuper && (
          <SuperadminDashboardOverview />
        )}
        {tab === 'overview' && !isSuper && (
          <div className={styles.dashWrap}>
            {/* ── Hero Header ── */}
            <div className={styles.dashHero}>
              <div className={styles.dashHeroLeft}>
                <div className={styles.dashGreetRow}>
                  <h1 className={styles.dashTitle}>
                    {isSuper ? 'Superadmin Dashboard' : 'Admin Dashboard'}
                  </h1>
                  <span className={styles.roleBadgePill} style={isSuper
                    ? { background: '#F3E8FF', color: '#7C3AED', border: '1px solid #DDD6FE' }
                    : { background: '#EFF6FF', color: '#2563EB', border: '1px solid #BFDBFE' }
                  }>
                    {isSuper ? '👑 Superadmin' : '🛡️ Admin'}
                  </span>
                </div>
                <p className={styles.dashSubtitle}>
                  {isSuper
                    ? 'Monitor platform security, users, mailboxes, and system health.'
                    : 'Review email security, quarantine, and detection activity.'}
                </p>
              </div>
              <div className={styles.dashHeroRight}>
                <div className={styles.dashHeroTime}>
                  <Clock size={13} />
                  <span>Last updated: {new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
              </div>
            </div>

            {/* ── Stat Cards ── */}
            {stats && (
              <div className={styles.statsGrid6}>
                {/* Card 1: Users */}
                <div className={`${styles.statCard2} ${styles.scBlue}`}>
                  <div className={styles.sc2Icon} style={{ background: '#EFF6FF', color: '#2563EB' }}>
                    <Users size={18} />
                  </div>
                  <div className={styles.sc2Body}>
                    <span className={styles.sc2Value}>{stats.total_users ?? '—'}</span>
                    <span className={styles.sc2Label}>Total Users</span>
                    <span className={styles.sc2Sub}>{stats.active_users ?? 0} active</span>
                  </div>
                  <ArrowUpRight size={14} className={styles.sc2Arrow} />
                </div>

                {/* Card 2: Mailboxes */}
                <div className={`${styles.statCard2} ${styles.scIndigo}`}>
                  <div className={styles.sc2Icon} style={{ background: '#EEF2FF', color: '#4F46E5' }}>
                    <Mail size={18} />
                  </div>
                  <div className={styles.sc2Body}>
                    <span className={styles.sc2Value}>{mailboxRows.length}</span>
                    <span className={styles.sc2Label}>{isSuper ? 'Active Mailboxes' : 'Inbox Emails'}</span>
                    <span className={styles.sc2Sub}>domain @{mailDomain}</span>
                  </div>
                  <ArrowUpRight size={14} className={styles.sc2Arrow} />
                </div>

                {/* Card 3: Emails Processed */}
                <div className={`${styles.statCard2} ${styles.scGray}`}>
                  <div className={styles.sc2Icon} style={{ background: '#F9FAFB', color: '#374151' }}>
                    <Inbox size={18} />
                  </div>
                  <div className={styles.sc2Body}>
                    <span className={styles.sc2Value}>{stats.total_emails ?? '—'}</span>
                    <span className={styles.sc2Label}>Emails Processed</span>
                    <span className={styles.sc2Sub}>{stats.clean ?? 0} safe emails</span>
                  </div>
                  <ArrowUpRight size={14} className={styles.sc2Arrow} />
                </div>

                {/* Card 4: Threats */}
                <div className={`${styles.statCard2} ${styles.scRed}`}>
                  <div className={styles.sc2Icon} style={{ background: '#FEF2F2', color: '#DC2626' }}>
                    <ShieldAlert size={18} />
                  </div>
                  <div className={styles.sc2Body}>
                    <span className={styles.sc2Value}>{totalThreats}</span>
                    <span className={styles.sc2Label}>Threats Detected</span>
                    <span className={styles.sc2Sub}>{((totalThreats / totalEmails) * 100).toFixed(1)}% of total</span>
                  </div>
                  <TrendingDown size={14} className={styles.sc2Arrow} style={{ color: '#DC2626' }} />
                </div>

                {/* Card 5: Quarantined */}
                <div className={`${styles.statCard2} ${styles.scOrange}`}>
                  <div className={styles.sc2Icon} style={{ background: '#FFFBEB', color: '#D97706' }}>
                    <AlertTriangle size={18} />
                  </div>
                  <div className={styles.sc2Body}>
                    <span className={styles.sc2Value}>{stats.quarantine ?? '—'}</span>
                    <span className={styles.sc2Label}>Quarantined</span>
                    <span className={styles.sc2Sub}>{quarantinePct}% quarantine rate</span>
                  </div>
                  <ArrowUpRight size={14} className={styles.sc2Arrow} />
                </div>

                {/* Card 6: System Health / Pending */}
                <div className={`${styles.statCard2} ${styles.scGreen}`}>
                  <div className={styles.sc2Icon} style={{ background: '#ECFDF5', color: '#059669' }}>
                    <ShieldCheck size={18} />
                  </div>
                  <div className={styles.sc2Body}>
                    <span className={styles.sc2Value} style={{ color: '#059669' }}>
                      {isSuper ? 'Healthy' : openReports.length}
                    </span>
                    <span className={styles.sc2Label}>{isSuper ? 'System Health' : 'Pending Review'}</span>
                    <span className={styles.sc2Sub}>{isSuper ? 'All services online' : `${reports.length} total reports`}</span>
                  </div>
                  <CheckCircle2 size={14} className={styles.sc2Arrow} style={{ color: '#059669' }} />
                </div>
              </div>
            )}

            {/* ── Main Content Grid ── */}
            <div className={styles.dashGrid}>
              {/* LEFT COLUMN */}
              <div className={styles.dashCol}>

                {/* Security Overview */}
                {stats && (
                  <div className={styles.sectionCard}>
                    <div className={styles.sectionCardHeader}>
                      <Shield size={16} className={styles.sectionCardIcon} />
                      <span>Security Overview</span>
                    </div>
                    <div className={styles.securityBars}>
                      <div className={styles.secBar}>
                        <div className={styles.secBarMeta}>
                          <span className={styles.secBarLabel}>
                            <span className={styles.secDot} style={{ background: '#059669' }} />
                            Ham / Safe
                          </span>
                          <span className={styles.secBarCount}>{stats.clean ?? 0}</span>
                        </div>
                        <div className={styles.secBarTrack}>
                          <div className={styles.secBarFill} style={{ width: `${safePct}%`, background: '#059669' }} />
                        </div>
                        <span className={styles.secBarPct}>{safePct}%</span>
                      </div>

                      <div className={styles.secBar}>
                        <div className={styles.secBarMeta}>
                          <span className={styles.secBarLabel}>
                            <span className={styles.secDot} style={{ background: '#D97706' }} />
                            Spam
                          </span>
                          <span className={styles.secBarCount}>{stats.warn ?? 0}</span>
                        </div>
                        <div className={styles.secBarTrack}>
                          <div className={styles.secBarFill} style={{ width: `${spamPct}%`, background: '#D97706' }} />
                        </div>
                        <span className={styles.secBarPct}>{spamPct}%</span>
                      </div>

                      <div className={styles.secBar}>
                        <div className={styles.secBarMeta}>
                          <span className={styles.secBarLabel}>
                            <span className={styles.secDot} style={{ background: '#DC2626' }} />
                            Phishing / Malware
                          </span>
                          <span className={styles.secBarCount}>{Math.round((stats.quarantine ?? 0) * 0.6)}</span>
                        </div>
                        <div className={styles.secBarTrack}>
                          <div className={styles.secBarFill} style={{ width: `${Math.round(quarantinePct * 0.6)}%`, background: '#DC2626' }} />
                        </div>
                        <span className={styles.secBarPct}>{Math.round(quarantinePct * 0.6)}%</span>
                      </div>

                      <div className={styles.secBar}>
                        <div className={styles.secBarMeta}>
                          <span className={styles.secBarLabel}>
                            <span className={styles.secDot} style={{ background: '#7C3AED' }} />
                            Quarantined
                          </span>
                          <span className={styles.secBarCount}>{stats.quarantine ?? 0}</span>
                        </div>
                        <div className={styles.secBarTrack}>
                          <div className={styles.secBarFill} style={{ width: `${quarantinePct}%`, background: '#7C3AED' }} />
                        </div>
                        <span className={styles.secBarPct}>{quarantinePct}%</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Mailbox Overview (superadmin) or Threat Breakdown (admin) */}
                {isSuper ? (
                  <div className={styles.sectionCard}>
                    <div className={styles.sectionCardHeader}>
                      <Mail size={16} className={styles.sectionCardIcon} />
                      <span>Mailbox Overview</span>
                    </div>
                    <div className={styles.mailboxOverview}>
                      <div className={styles.mboDomainRow}>
                        <div className={styles.mboDomainIcon}>
                          <AtSign size={18} />
                        </div>
                        <div>
                          <div className={styles.mboDomain}>{mailDomain}</div>
                          <div className={styles.mboSub}>Primary domain</div>
                        </div>
                      </div>
                      <div className={styles.mboStats}>
                        <div className={styles.mboStatItem}>
                          <span className={styles.mboStatValue}>{mailboxRows.length}</span>
                          <span className={styles.mboStatLabel}>Active Mailboxes</span>
                        </div>
                        <div className={styles.mboStatItem}>
                          <span className={styles.mboStatValue}>0 KB</span>
                          <span className={styles.mboStatLabel}>Storage Used</span>
                        </div>
                        <div className={styles.mboStatItem}>
                          <span className={styles.mboStatValue} style={{ color: '#059669' }}>100%</span>
                          <span className={styles.mboStatLabel}>Available</span>
                        </div>
                      </div>
                      <button className={styles.mboBtn} onClick={() => navigate(`${basePath}/email`)}>
                        <Mail size={14} />
                        Manage Mailboxes
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className={styles.sectionCard}>
                    <div className={styles.sectionCardHeader}>
                      <TrendingDown size={16} className={styles.sectionCardIcon} style={{ color: '#DC2626' }} />
                      <span>Threat Breakdown</span>
                    </div>
                    <div className={styles.threatGrid}>
                      <div className={styles.threatItem} style={{ '--tc': '#D97706', '--tb': '#FFFBEB' }}>
                        <span className={styles.threatValue}>{stats?.warn ?? 0}</span>
                        <span className={styles.threatLabel}>Spam</span>
                      </div>
                      <div className={styles.threatItem} style={{ '--tc': '#DC2626', '--tb': '#FEF2F2' }}>
                        <span className={styles.threatValue}>{Math.round((stats?.quarantine ?? 0) * 0.6)}</span>
                        <span className={styles.threatLabel}>Phishing</span>
                      </div>
                      <div className={styles.threatItem} style={{ '--tc': '#7C3AED', '--tb': '#F3E8FF' }}>
                        <span className={styles.threatValue}>{Math.round((stats?.quarantine ?? 0) * 0.4)}</span>
                        <span className={styles.threatLabel}>Malware</span>
                      </div>
                      <div className={styles.threatItem} style={{ '--tc': '#059669', '--tb': '#ECFDF5' }}>
                        <span className={styles.threatValue}>{stats?.clean ?? 0}</span>
                        <span className={styles.threatLabel}>Safe / Ham</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* RIGHT COLUMN */}
              <div className={styles.dashCol}>

                {/* System Health (superadmin) or Security Queue (admin) */}
                {isSuper ? (
                  <div className={styles.sectionCard}>
                    <div className={styles.sectionCardHeader}>
                      <Server size={16} className={styles.sectionCardIcon} />
                      <span>System Health</span>
                      <span className={styles.sectionCardBadge} style={{ background: '#ECFDF5', color: '#059669' }}>All Systems Online</span>
                    </div>
                    <div className={styles.healthList}>
                      {systemServices.map((svc) => {
                        const meta = statusMeta[svc.status]
                        return (
                          <div key={svc.name} className={styles.healthRow}>
                            <span className={styles.healthIcon} style={{ background: '#F9FAFB', color: '#374151' }}>{svc.icon}</span>
                            <span className={styles.healthName}>{svc.name}</span>
                            <span className={styles.healthBadge} style={{ background: meta.bg, color: meta.color }}>
                              {meta.icon} {meta.label}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                ) : (
                  <div className={styles.sectionCard}>
                    <div className={styles.sectionCardHeader}>
                      <ListFilter size={16} className={styles.sectionCardIcon} />
                      <span>Security Queue</span>
                      <button className={styles.sectionCardLink} onClick={() => navigate(`${basePath}/activity`)}>
                        View All
                      </button>
                    </div>
                    <div className={styles.queueList}>
                      {logs.slice(0, 5).length > 0 ? logs.slice(0, 5).map((l, i) => (
                        <div key={i} className={styles.queueRow}>
                          <div className={styles.queueSender}>
                            <div className={styles.queueAvatar}>{(l.user || 'U')[0].toUpperCase()}</div>
                            <div>
                              <div className={styles.queueUser}>{l.user}</div>
                              <div className={styles.queueTime}>{l.created_at?.split('.')[0]}</div>
                            </div>
                          </div>
                          <code className={styles.queueAction}>{l.action}</code>
                        </div>
                      )) : (
                        <div className={styles.emptySmall}>No recent queue items.</div>
                      )}
                    </div>
                  </div>
                )}

                {/* Per-Email Breakdown (admin only) */}
                {!isSuper && adminEmailStats?.emails?.length > 0 && (
                  <div className={styles.sectionCard}>
                    <div className={styles.sectionCardHeader}>
                      <BarChart3 size={16} className={styles.sectionCardIcon} />
                      <span>Per-Email Breakdown</span>
                    </div>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid var(--border)' }}>
                            <th style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)' }}>Email</th>
                            <th style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600, color: 'var(--text-muted)' }}>Total</th>
                            <th style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600, color: '#D97706' }}>Spam</th>
                            <th style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600, color: '#DC2626' }}>Phish</th>
                            <th style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600, color: '#7C3AED' }}>Mal</th>
                            <th style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600, color: '#059669' }}>Clean</th>
                          </tr>
                        </thead>
                        <tbody>
                          {adminEmailStats.emails.map((row) => (
                            <tr key={row.email} style={{ borderBottom: '1px solid var(--border)' }}>
                              <td style={{ padding: '8px 10px', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.7rem' }}>
                                <span style={{
                                  display: 'inline-flex', alignItems: 'center', gap: 4,
                                  padding: '1px 6px', borderRadius: 10, fontSize: '0.65rem', fontWeight: 500,
                                  background: row.owner === 'admin' ? '#EEF2FF' : '#F0FDF4',
                                  color: row.owner === 'admin' ? '#4F46E5' : '#15803D',
                                }}>
                                  <Mail size={9} />
                                  {row.email}
                                </span>
                              </td>
                              <td style={{ padding: '8px 10px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.total}</td>
                              <td style={{ padding: '8px 10px', textAlign: 'right', color: '#D97706', fontVariantNumeric: 'tabular-nums' }}>{row.spam}</td>
                              <td style={{ padding: '8px 10px', textAlign: 'right', color: '#DC2626', fontVariantNumeric: 'tabular-nums' }}>{row.phishing}</td>
                              <td style={{ padding: '8px 10px', textAlign: 'right', color: '#7C3AED', fontVariantNumeric: 'tabular-nums' }}>{row.malware}</td>
                              <td style={{ padding: '8px 10px', textAlign: 'right', color: '#059669', fontVariantNumeric: 'tabular-nums' }}>{row.clean}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Recent Activity */}
                <div className={styles.sectionCard}>
                  <div className={styles.sectionCardHeader}>
                    <Activity size={16} className={styles.sectionCardIcon} />
                    <span>Recent Activity</span>
                    <button className={styles.sectionCardLink} onClick={() => navigate(`${basePath}/activity`)}>
                      View All
                    </button>
                  </div>
                  <div className={styles.activityFeed}>
                    {logs.slice(0, 6).length > 0 ? logs.slice(0, 6).map((l, i) => {
                      const meta = getActivityMeta(l.action)
                      return (
                        <div key={i} className={styles.activityItem}>
                          <div className={styles.activityIconWrap} style={{ background: meta.bg, color: meta.color }}>
                            {meta.icon}
                          </div>
                          <div className={styles.activityBody}>
                            <span className={styles.activityAction}>{l.action}</span>
                            <span className={styles.activityUser}>by {l.user}</span>
                          </div>
                          <span className={styles.activityTime}>
                            {l.created_at ? new Date(l.created_at).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }) : '—'}
                          </span>
                        </div>
                      )
                    }) : (
                      <div className={styles.emptySmall}>No recent activity.</div>
                    )}
                  </div>
                </div>

                {/* Quick Actions */}
                <div className={styles.sectionCard}>
                  <div className={styles.sectionCardHeader}>
                    <Zap size={16} className={styles.sectionCardIcon} />
                    <span>Quick Actions</span>
                  </div>
                  <div className={styles.quickActions}>
                    <button className={styles.qaBtn} onClick={() => navigate(`${basePath}/${isSuper ? 'email' : 'review'}`)}>
                      <Mail size={16} />
                      <span>{isSuper ? 'Manage Mailboxes' : 'Review Quarantine'}</span>
                    </button>
                    <button className={styles.qaBtn} onClick={() => navigate(`${basePath}/users`)}>
                      <Users size={16} />
                      <span>{isSuper ? 'Manage Users' : 'Add Whitelist'}</span>
                    </button>
                    <button className={styles.qaBtn} onClick={() => navigate(`${basePath}/reports`)}>
                      <FileText size={16} />
                      <span>{isSuper ? 'View Reports' : 'Export Report'}</span>
                    </button>
                    <button className={styles.qaBtn} onClick={() => navigate(`${basePath}/settings`)}>
                      <Settings size={16} />
                      <span>{isSuper ? 'Settings' : 'Manage Rules'}</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === 'users' && isSuper && (
          <SuperadminUserManagement />
        )}
        {tab === 'users' && !isSuper && (
          <AdminUserManagement />
        )}

        {tab === 'reports' && isSuper && (
          <SuperadminReports />
        )}

        {tab === 'reports' && !isSuper && (
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <AlertCircle size={16} /> Laporan & Bantuan User
              <div style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
                {['all', 'question', 'bug', 'false_positive', 'access', 'other'].map((cat) => (
                  <button
                    key={cat}
                    className={styles.filterChip}
                    style={{ background: filterCategory === cat ? CATEGORY_COLORS[cat] || '#1a73e8' : 'transparent', color: filterCategory === cat ? '#fff' : 'var(--text-muted)' }}
                    onClick={() => setFilterCategory(cat)}
                  >
                    {cat === 'all' ? 'Semua' : CATEGORY_LABELS[cat]}
                  </button>
                ))}
              </div>
            </div>
            {filteredReports.length === 0 ? (
              <div className={styles.emptyState}>Belum ada laporan dari user.</div>
            ) : (
              <div className={styles.reportList}>
                {filteredReports.map((r) => (
                  <div key={r.id} className={styles.reportCard}>
                    <div className={styles.reportCardHeader}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <strong>{r.username}</strong>
                        <span className={styles.reportCategory} style={{ background: CATEGORY_COLORS[r.category] || '#5f6368' }}>
                          {CATEGORY_LABELS[r.category] || r.category}
                        </span>
                        <span className={styles.reportPriority} style={{ color: PRIORITY_COLORS[r.priority] || '#5f6368' }}>
                          <Flag size={12} /> {r.priority}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span className={r.status === 'open' ? styles.reportOpen : r.status === 'in_progress' ? styles.reportProgress : styles.reportDone}>
                          {r.status === 'open' ? 'Terbuka' : r.status === 'in_progress' ? 'Diproses' : 'Selesai'}
                        </span>
                        <button className={styles.expandBtn} onClick={() => setExpandedReport(expandedReport === r.id ? null : r.id)}>
                          {expandedReport === r.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </button>
                      </div>
                    </div>
                    <p className={styles.reportSubject}>{r.subject}</p>
                    <p className={styles.reportMessage}>{r.message}</p>
                    <div className={styles.reportFooter}>
                      <span className={styles.reportDate}>{r.created_at?.split('.')[0]}</span>
                      {r.status === 'open' && (
                        <button className={styles.resolveBtn} onClick={() => handleResolveReport(r.id)}>
                          <Check size={14} /> Selesai
                        </button>
                      )}
                    </div>

                    {expandedReport === r.id && (
                      <div className={styles.reportDetail}>
                        {r.admin_reply && (
                          <div className={styles.replyBubble}>
                            <strong style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Balasan Admin:</strong>
                            <p style={{ margin: '4px 0 0', fontSize: '0.8125rem', color: 'var(--text)' }}>{r.admin_reply}</p>
                          </div>
                        )}
                        <div className={styles.replyArea}>
                          <textarea
                            className={styles.replyInput}
                            placeholder="Tulis balasan untuk user ini..."
                            value={expandedReport === r.id ? replyText : ''}
                            onChange={(e) => setReplyText(e.target.value)}
                            rows={3}
                          />
                          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                            <button className={styles.replySendBtn} onClick={() => handleReplyReport(r.id)} disabled={!replyText.trim()}>
                              <Reply size={14} /> Kirim Balasan
                            </button>
                            {r.status !== 'resolved' && (
                              <>
                                <button className={styles.resolveBtn} onClick={() => handleStatusChange(r.id, 'in_progress')}>
                                  <Activity size={14} /> Proses
                                </button>
                                <button className={styles.resolveBtn} onClick={() => handleResolveReport(r.id)}>
                                  <Check size={14} /> Selesai
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'activity' && (
          <div className={styles.section}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Aksi</th>
                  <th>Email ID</th>
                  <th>Detail</th>
                  <th>Waktu</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l, i) => (
                  <tr key={i}>
                    <td>{l.user}</td>
                    <td><code className={styles.actionCode}>{l.action}</code></td>
                    <td className={styles.mono}>{l.email_id || '-'}</td>
                    <td className={styles.detailCell}>{l.details || '-'}</td>
                    <td className={styles.mono}>{l.created_at?.split('.')[0]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tab === 'track' && <SuperadminTracking />}

        {tab === 'spamstats' && isSuper && (
          <SuperadminSpamStats />
        )}

        {tab === 'companies' && isSuper && (
          <SuperadminCompanies />
        )}

        {tab === 'email' && isSuper && (
          <SuperadminMailboxManagement />
        )}
        {tab === 'email' && !isSuper && (
          <AdminMailboxManagement />
        )}

        {tab === 'review' && !isSuper && (
          <AdminQuarantineReview />
        )}

        {tab === 'logs' && !isSuper && (
          <AdminDetectionLogs />
        )}

        {tab === 'health' && isSuper && (
          <SuperadminSystemHealth />
        )}

        {tab === 'settings' && isSuper && (
          <SuperadminSettingsPage />
        )}
        {tab === 'settings' && !isSuper && (
          <AdminSettingsPage />
        )}
      </div>
    </AdminShell>
  )
}
