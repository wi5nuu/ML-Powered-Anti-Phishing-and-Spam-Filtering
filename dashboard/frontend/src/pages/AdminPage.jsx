import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import AdminShell from '../components/layout/AdminShell'
import api from '../api/client'
import { useMe } from '../api/auth'
import { Users, Shield, Mail, Activity, Plus, X, Check, AlertCircle, Reply, ChevronDown, ChevronUp, Flag, ChevronRight, Trash2, Settings, ExternalLink, Save, Eye, EyeOff, Copy, AtSign, TrendingUp, TrendingDown, Inbox, Server, Wifi, Database, Cpu, Clock, CheckCircle2, XCircle, AlertTriangle, ShieldCheck, ShieldAlert, Zap, FileText, ListFilter, ArrowUpRight } from 'lucide-react'
import { DEFAULT_MAIL_DOMAIN, getMailboxSession, getMailDomain, getMailboxes, setMailDomain, setMailboxes } from '../utils/mailbox'
import styles from './AdminPage.module.css'

const CATEGORY_LABELS = { bug: 'Bug / Error', question: 'Pertanyaan', access: 'Akses', false_positive: 'False Positive', other: 'Lainnya' }
const CATEGORY_COLORS = { bug: '#ea4335', question: '#1a73e8', access: '#f29900', false_positive: '#34a853', other: '#5f6368' }
const PRIORITY_COLORS = { low: '#5f6368', normal: '#1a73e8', high: '#f29900', urgent: '#ea4335' }
const ROLES = ['superadmin', 'admin', 'user']
const ROLE_LABELS = {
  superadmin: 'Superadmin',
  admin: 'Admin',
  user: 'User',
}
export default function AdminPage() {
  const { data: me } = useMe()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'overview'
  const isSuper = me?.user?.role === 'superadmin'
  // Safety: redirect non-superadmin away from users tab
  useEffect(() => {
    if (tab === 'users' && !isSuper && me) {
      setSearchParams({ tab: 'overview' }, { replace: true })
    }
  }, [tab, isSuper, me])
  const [users, setUsers] = useState([])
  const [logs, setLogs] = useState([])
  const [stats, setStats] = useState(null)
  const [reports, setReports] = useState([])
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [newEmail, setNewEmail] = useState('')
  const [newRole, setNewRole] = useState('user')
  const [msg, setMsg] = useState('')
  const [selectedUser, setSelectedUser] = useState(null)
  const [userEmails, setUserEmails] = useState([])
  const [expandedReport, setExpandedReport] = useState(null)
  const [replyText, setReplyText] = useState('')
  const [filterCategory, setFilterCategory] = useState('all')
  const [roleFilter, setRoleFilter] = useState('all')
  const [editUser, setEditUser] = useState(null)
  const [editRole, setEditRole] = useState('')
  const [editPassword, setEditPassword] = useState('')
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

  const fetchData = () => {
    api.get('/admin/users').then((r) => setUsers(r.data)).catch(() => {})
    api.get('/admin/stats').then((r) => setStats(r.data)).catch(() => {})
    api.get('/admin/audit-logs').then((r) => setLogs(r.data)).catch(() => {})
    api.get('/admin/reports').then((r) => setReports(r.data)).catch(() => {})
  }

  const fetchMailboxes = async () => {
    try {
      const r = await api.get('/admin/mailboxes')
      const rows = Array.isArray(r.data) ? r.data : []
      setMailboxRows(rows)
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

  const roleBadge = (role) => {
    const colors = { superadmin: '#c5221f', admin: '#f29900', user: '#137333' }
    return <span className={styles.roleBadge} style={{ background: colors[role] || '#5f6368' }}>{ROLE_LABELS[role] || role}</span>
  }

  const handleAddUser = async () => {
    if (!newEmail.includes('@')) return
    const username = newEmail.split('@')[0]
    try {
      await api.post('/admin/users', { username, password: 'Welcome123!', email: newEmail, role: newRole })
      setMsg(`User ${username} berhasil ditambahkan. Password: Welcome123!`)
      setNewEmail(''); setShowAdd(false); fetchData()
    } catch (e) {
      setMsg('Gagal: ' + (e.response?.data?.detail || 'unknown error'))
    }
    setTimeout(() => setMsg(''), 5000)
  }

  const handleToggleUser = async (username, isActive) => {
    try {
      await api.put(`/admin/users/${username}`, { is_active: !isActive })
      fetchData()
    } catch (e) { setMsg('Gagal update user') }
  }

  const handleEditUser = async () => {
    if (!editUser) return
    const payload = {}
    if (editRole !== editUser.role) payload.role = editRole
    if (editPassword) payload.password = editPassword
    if (Object.keys(payload).length === 0) { setEditUser(null); return }
    try {
      await api.put(`/admin/users/${editUser.username}`, payload)
      setMsg(`User ${editUser.username} berhasil diperbarui.`)
      setEditUser(null); setEditRole(''); setEditPassword('')
      fetchData()
    } catch (e) { setMsg('Gagal update: ' + (e.response?.data?.detail || 'error')) }
    setTimeout(() => setMsg(''), 5000)
  }

  const handleDeleteUser = async (username) => {
    if (!window.confirm(`Yakin menonaktifkan user "${username}"?`)) return
    try {
      await api.delete(`/admin/users/${username}`)
      setMsg(`User ${username} dinonaktifkan.`)
      fetchData()
    } catch (e) { setMsg('Gagal menonaktifkan user') }
    setTimeout(() => setMsg(''), 5000)
  }

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

  const viewUserEmails = async (username) => {
    try {
      const r = await api.get(`/admin/user-emails/${username}`)
      setUserEmails(r.data)
      setSelectedUser(username)
    } catch (e) { setMsg('Gagal memuat email user') }
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
      ? `/inbox?mailbox_id=${encodeURIComponent(mailboxId)}&mailbox=${encodeURIComponent(email)}`
      : `/mailbox-login?mailbox_id=${encodeURIComponent(mailboxId)}&email=${encodeURIComponent(email)}`
    if (newWindow) {
      window.open(target, '_blank', 'noopener,noreferrer')
      return
    }
    navigate(target)
  }

  const filteredUsers = users.filter((u) => {
    if (roleFilter !== 'all' && u.role !== roleFilter) return false
    return u.username.includes(search) || (u.email || '').includes(search)
  })
  const openReports = reports.filter((r) => r.status === 'open')
  const filteredReports = filterCategory === 'all' ? reports : reports.filter((r) => r.category === filterCategory)

  if (selectedUser) {
    return (
      <AdminShell>
        <div className={styles.page}>
          <button className={styles.backBtn} onClick={() => { setSelectedUser(null); setUserEmails([]) }}>
            ← Kembali ke Users
          </button>
          <h2 className={styles.userDetailTitle}>Email milik: {selectedUser}</h2>
          <div className={styles.section}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Email ID</th>
                  <th>Subject</th>
                  <th>Sender</th>
                  <th>Label</th>
                  <th>Score</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {userEmails.map((e) => (
                  <tr key={e.email_id}>
                    <td className={styles.mono}>{e.email_id?.slice(0, 16)}...</td>
                    <td className={styles.detailCell}>{e.subject || '-'}</td>
                    <td className={styles.detailCell}>{e.sender || '-'}</td>
                    <td>{e.label}</td>
                    <td>{e.fused_score?.toFixed(3)}</td>
                    <td>{e.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </AdminShell>
    )
  }

  // System health mock data (no backend endpoint yet)
  const systemServices = [
    { name: 'Classifier API', icon: <Cpu size={15} />, status: 'healthy' },
    { name: 'SMTP Receiver', icon: <Mail size={15} />, status: 'healthy' },
    { name: 'Worker', icon: <Zap size={15} />, status: 'healthy' },
    { name: 'Redis', icon: <Database size={15} />, status: 'healthy' },
    { name: 'PostgreSQL', icon: <Database size={15} />, status: 'healthy' },
    { name: 'SpamAssassin', icon: <Shield size={15} />, status: 'warning' },
  ]

  const statusMeta = {
    healthy: { label: 'Healthy', color: '#059669', bg: '#ECFDF5', icon: <CheckCircle2 size={13} /> },
    warning: { label: 'Warning', color: '#D97706', bg: '#FFFBEB', icon: <AlertTriangle size={13} /> },
    down:    { label: 'Down',    color: '#DC2626', bg: '#FEF2F2', icon: <XCircle size={13} /> },
  }

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

        {tab === 'overview' && (
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
                      <button className={styles.mboBtn} onClick={() => setSearchParams({ tab: 'email' })}>
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
                      <button className={styles.sectionCardLink} onClick={() => setSearchParams({ tab: 'activity' })}>
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

                {/* Recent Activity */}
                <div className={styles.sectionCard}>
                  <div className={styles.sectionCardHeader}>
                    <Activity size={16} className={styles.sectionCardIcon} />
                    <span>Recent Activity</span>
                    <button className={styles.sectionCardLink} onClick={() => setSearchParams({ tab: 'activity' })}>
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
                    <button className={styles.qaBtn} onClick={() => setSearchParams({ tab: 'email' })}>
                      <Mail size={16} />
                      <span>{isSuper ? 'Manage Mailboxes' : 'Review Quarantine'}</span>
                    </button>
                    <button className={styles.qaBtn} onClick={() => setSearchParams({ tab: 'users' })}>
                      <Users size={16} />
                      <span>{isSuper ? 'Manage Users' : 'Add Whitelist'}</span>
                    </button>
                    <button className={styles.qaBtn} onClick={() => setSearchParams({ tab: 'reports' })}>
                      <FileText size={16} />
                      <span>{isSuper ? 'View Reports' : 'Export Report'}</span>
                    </button>
                    <button className={styles.qaBtn} onClick={() => setSearchParams({ tab: 'settings' })}>
                      <Settings size={16} />
                      <span>{isSuper ? 'Settings' : 'Manage Rules'}</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === 'users' && (
          <div className={styles.section}>
            {/* Toolbar: search + role filter + add */}
            <div className={styles.sectionHeader}>
              <input className={styles.searchInput} placeholder="Cari username atau email..." value={search} onChange={(e) => setSearch(e.target.value)} />
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                {['all', ...ROLES].map((r) => (
                  <button
                    key={r}
                    className={styles.filterChip}
                    style={{ background: roleFilter === r ? '#1a73e8' : 'transparent', color: roleFilter === r ? '#fff' : 'var(--text-muted)' }}
                    onClick={() => setRoleFilter(r)}
                  >
                    {r === 'all' ? 'Semua' : ROLE_LABELS[r]}
                  </button>
                ))}
              </div>
              <button className={styles.addBtn} onClick={() => setShowAdd(true)}><Plus size={16} /> Tambah User</button>
            </div>

            {/* Add user form */}
            {showAdd && (
              <div className={styles.addForm}>
                <input placeholder="Email (contoh: user@company.com)" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} />
                <select value={newRole} onChange={(e) => setNewRole(e.target.value)}>
                  {ROLES.map((role) => (
                    <option key={role} value={role}>{ROLE_LABELS[role]}</option>
                  ))}
                </select>
                <button className={styles.saveBtn} onClick={handleAddUser}><Check size={16} /> Simpan</button>
                <button className={styles.cancelBtn} onClick={() => setShowAdd(false)}><X size={16} /></button>
              </div>
            )}

            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Aksi</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((u) => (
                  <tr key={u.username}>
                    <td className={styles.usernameCell}>{u.username}</td>
                    <td className={styles.mono}>{u.email || '-'}</td>
                    <td>{roleBadge(u.role)}</td>
                    <td>
                      <span className={`${styles.statusDot} ${u.is_active ? styles.active : styles.inactive}`} />
                      {u.is_active ? 'Aktif' : 'Nonaktif'}
                    </td>
                    <td>
                      <div className={styles.actionGroup}>
                        <button className={styles.actionBtn} onClick={() => viewUserEmails(u.username)} title="Lihat email user">Email</button>
                        <button className={styles.actionBtn} onClick={() => { setEditUser(u); setEditRole(u.role); setEditPassword('') }} title="Edit user">Edit</button>
                        <button className={styles.actionBtn} onClick={() => handleToggleUser(u.username, u.is_active)}>
                          {u.is_active ? 'Nonaktif' : 'Aktif'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Edit user modal overlay */}
            {editUser && (
              <div className={styles.overlay} onClick={() => setEditUser(null)}>
                <div className={styles.editModal} onClick={(e) => e.stopPropagation()}>
                  <div className={styles.editModalHeader}>
                    <h3><Users size={18} /> Edit User: {editUser.username}</h3>
                    <button className={styles.cancelBtn} onClick={() => { setEditUser(null); setEditRole(''); setEditPassword('') }}><X size={16} /></button>
                  </div>
                  <div className={styles.editModalBody}>
                    <div className={styles.fieldRow}>
                      <div className={styles.fieldLeft}>
                        <label className={styles.fieldLabel}>Role</label>
                        <span className={styles.fieldHint}>Saat ini: {editUser.role}</span>
                      </div>
                      <div className={styles.fieldRight}>
                        <select value={editRole} onChange={(e) => setEditRole(e.target.value)} className={styles.editSelect}>
                          {ROLES.map((role) => (
                            <option key={role} value={role}>{ROLE_LABELS[role]}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className={styles.fieldRow}>
                      <div className={styles.fieldLeft}>
                        <label className={styles.fieldLabel}>Reset Password</label>
                        <span className={styles.fieldHint}>Kosongi jika tidak ingin mengubah</span>
                      </div>
                      <div className={styles.fieldRight}>
                        <input type="password" className={styles.input} placeholder="Password baru" value={editPassword} onChange={(e) => setEditPassword(e.target.value)} />
                      </div>
                    </div>
                    <div className={styles.fieldRow}>
                      <div className={styles.fieldLeft}>
                        <label className={styles.fieldLabel}>Status</label>
                        <span className={styles.fieldHint}>{editUser.is_active ? 'Aktif' : 'Nonaktif'}</span>
                      </div>
                      <div className={styles.fieldRight}>
                        <button className={styles.actionBtn} onClick={() => handleToggleUser(editUser.username, editUser.is_active)}>
                          {editUser.is_active ? 'Nonaktifkan' : 'Aktifkan'}
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className={styles.editModalFooter}>
                    <button className={styles.cancelBtn} onClick={() => { setEditUser(null); setEditRole(''); setEditPassword('') }}>Batal</button>
                    <button className={styles.saveBtn} onClick={handleEditUser} disabled={editRole === editUser.role && !editPassword}>
                      <Check size={16} /> Simpan Perubahan
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'reports' && (
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

                    {/* Expanded detail */}
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

        {tab === 'email' && (
          <>
            <div className={styles.mailboxHero}>
              <div className={styles.mailboxHeroIcon}><AtSign size={24} /></div>
              <div>
                <h2>{mailDomain}</h2>
                <p>Default domain email perusahaan. Semua mailbox baru dibuat dengan domain ini.</p>
              </div>
              <button className={styles.addBtn} onClick={() => { setCreateMailboxOpen(true); setMailboxError('') }}>
                <Plus size={16} /> Add mailboxes
              </button>
            </div>

            <div className={styles.section}>
              <div className={styles.sectionHeader}>
                <div className={styles.sectionTitle}>
                  <Shield size={18} />
                  <div>
                    <strong>Manage mailboxes</strong>
                    <span>{mailboxes.length} email aktif dari domain @{mailDomain}</span>
                  </div>
                </div>
                <button className={styles.addBtn} onClick={() => { setCreateMailboxOpen(true); setMailboxError('') }}>
                  <Plus size={16} /> Add mailboxes
                </button>
              </div>
              {mailboxes.length === 0 ? (
                <div className={styles.emptyState}>Belum ada mailbox. Tambahkan email dengan domain @{mailDomain}.</div>
              ) : (
                <div className={styles.mailboxTable}>
                  <div className={styles.mailboxTableHead}>
                    <span>Mailbox</span>
                    <span>Status</span>
                    <span>Usage</span>
                    <span>Aksi</span>
                  </div>
                  {mailboxRows.map((row) => (
                    <div key={row.id || row.email} className={styles.mailboxTableRow}>
                      <div className={styles.mailboxInfoCell}>
                        <div className={styles.mailboxIcon}><Mail size={18} /></div>
                        <div className={styles.mailboxInfo}>
                          <strong>{row.email}</strong>
                          <span>ID: {row.id} · {row.sender_name || 'Sender name belum diatur'}</span>
                        </div>
                        <button
                          className={styles.copyBtn}
                          onClick={() => navigator.clipboard?.writeText(row.email)}
                          title="Salin email"
                        >
                          <Copy size={15} />
                        </button>
                      </div>
                      <div className={styles.statusOk}><Check size={14} /> Active</div>
                      <div className={styles.usageText}>0% Used<br /><span>0 KB / 1.00 GB</span></div>
                      <div className={styles.mailboxActions}>
                        <button className={styles.webmailBtn} onClick={() => openMailbox(row.email)} title={`Buka inbox ${row.email}`}>
                          Webmail <ChevronRight size={15} />
                        </button>
                        <button className={styles.iconAction} onClick={() => openMailbox(row.email, true)} title={`Open in new window ${row.email}`}>
                          <ExternalLink size={17} />
                        </button>
                        <button className={styles.iconDanger} onClick={() => removeMailbox(row)} title="Hapus mailbox">
                          <Trash2 size={17} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {createMailboxOpen && (
              <div className={styles.mailboxModalOverlay} onClick={() => setCreateMailboxOpen(false)}>
                <div className={styles.mailboxModal} onClick={(e) => e.stopPropagation()}>
                  <div className={styles.mailboxModalHeader}>
                    <div>
                      <h2>Create mailbox</h2>
                      <p>Start sending and receiving emails</p>
                    </div>
                    <button className={styles.modalCloseBtn} onClick={() => setCreateMailboxOpen(false)}><X size={20} /></button>
                  </div>

                  <label className={styles.modalLabel}>New email address</label>
                  <div className={styles.splitEmailInput}>
                    <input
                      value={mailboxInput}
                      onChange={(e) => { setMailboxInput(e.target.value); setMailboxError('') }}
                      placeholder="New email address"
                      autoFocus
                    />
                    <span>@{mailDomain}</span>
                  </div>

                  <label className={styles.modalLabel}>Sender name</label>
                  <input
                    className={styles.modalInput}
                    value={mailboxSenderName}
                    onChange={(e) => setMailboxSenderName(e.target.value)}
                    placeholder="Opsional, contoh: Support Zenime"
                  />

                  <label className={styles.modalLabel}>Password</label>
                  <div className={styles.passwordInput}>
                    <input
                      type={showMailboxPassword ? 'text' : 'password'}
                      value={mailboxPassword}
                      onChange={(e) => { setMailboxPassword(e.target.value); setMailboxError('') }}
                      placeholder="Password"
                    />
                    <button type="button" onClick={() => navigator.clipboard?.writeText(mailboxPassword)} title="Copy password"><Copy size={18} /></button>
                    <button type="button" onClick={() => setShowMailboxPassword((v) => !v)} title="Lihat password">
                      {showMailboxPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>

                  <div className={styles.passwordRules}>
                    <span className={passwordChecks.number ? styles.ruleOk : ''}>One number</span>
                    <span className={passwordChecks.symbol ? styles.ruleOk : ''}>One symbol</span>
                    <span className={passwordChecks.lower ? styles.ruleOk : ''}>One lowercase letter</span>
                    <span className={passwordChecks.upper ? styles.ruleOk : ''}>One uppercase letter</span>
                    <span className={passwordChecks.length ? styles.ruleOk : ''}>At least 8 characters</span>
                    <span className={passwordChecks.latin ? styles.ruleOk : ''}>Only latin letters</span>
                  </div>

                  {mailboxError && <div className={styles.formError}>{mailboxError}</div>}
                  <div className={styles.mailboxModalActions}>
                    <button className={styles.cancelBtn} onClick={() => setCreateMailboxOpen(false)}>Batal</button>
                    <button className={styles.saveBtn} disabled={!mailboxInput.trim() || !passwordValid} onClick={handleAddMailbox}>
                      Create
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {tab === 'settings' && (
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <div className={styles.sectionTitle}>
                <Settings size={18} />
                <div>
                  <strong>Pengaturan</strong>
                  <span>Konfigurasi dasar panel admin dan domain email</span>
                </div>
              </div>
            </div>
            <div className={styles.settingsList}>
              <div className={styles.settingRow}>
                <span>Domain email organisasi</span>
                <strong>@{mailDomain}</strong>
              </div>
              <div className={styles.domainEditor}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}>Edit domain default mailbox</label>
                  <span className={styles.fieldHint}>Default dari .env: @{DEFAULT_MAIL_DOMAIN}. Mailbox baru wajib memakai domain aktif ini.</span>
                </div>
                <div className={styles.domainInputGroup}>
                  <input
                    className={styles.mailboxInput}
                    value={domainDraft}
                    onChange={(e) => {
                      setDomainDraft(e.target.value)
                      setDomainError('')
                    }}
                    placeholder="zenime.my.id"
                  />
                  <button className={styles.saveBtn} onClick={handleSaveDomain}>
                    <Save size={16} /> Simpan Domain
                  </button>
                </div>
                {domainError && <div className={styles.formError}>{domainError}</div>}
              </div>
              <div className={styles.settingRow}>
                <span>Role aktif</span>
                <strong>{ROLE_LABELS[me?.user?.role] || me?.user?.role}</strong>
              </div>
              <div className={styles.settingRow}>
                <span>Login admin</span>
                <strong>{me?.user?.username}</strong>
              </div>
              <p className={styles.helperText}>
                Untuk production/VPS, domain email dapat disesuaikan dari environment build frontend melalui VITE_MAIL_DOMAIN.
              </p>
            </div>
          </div>
        )}
      </div>
    </AdminShell>
  )
}
