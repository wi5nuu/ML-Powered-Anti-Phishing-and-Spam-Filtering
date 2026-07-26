import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from '../i18n/context'
import AdminShell from '../components/layout/AdminShell'
import api from '../api/client'
import { useMe } from '../api/auth'
import { Shield, Mail, Activity, Check, AlertCircle, Reply, ChevronDown, Flag, Settings, Save, CheckCircle2, AlertTriangle, ShieldAlert, FileText, RefreshCw } from 'lucide-react'
import SuperadminDashboardOverview from './SuperadminDashboardOverview'
import SuperadminUserManagement from './SuperadminUserManagement'
import SuperadminSystemHealth from './SuperadminSystemHealth'
import SuperadminUserAnalytics from './SuperadminUserAnalytics'
import AdminMailboxManagement from './AdminMailboxManagement'
import AdminQuarantineReview from './AdminQuarantineReview'
import AdminDetectionLogs from './AdminDetectionLogs'
import AdminProfileSettings from './AdminProfileSettings'
import AuditLogEmbed from './AuditLogEmbed'
import ThreatReportPage from './ThreatReportPage'
import ExportModal from '../components/common/ExportModal'
import { DEFAULT_MAIL_DOMAIN, getMailboxSession, getMailDomain, getMailboxes, setMailDomain, setMailboxDirectory, setMailboxes } from '../utils/mailbox'
import styles from './AdminPage.module.css'
import trackStyles from './ThreatReportPage.module.css'

const CATEGORY_COLORS = { bug: '#ea4335', question: '#1a73e8', access: '#f29900', false_positive: '#34a853', other: '#5f6368' }
const PRIORITY_COLORS = { low: '#5f6368', normal: '#1a73e8', high: '#f29900', urgent: '#ea4335' }
const SUPERADMIN_TABS = new Set(['overview', 'track', 'users', 'email', 'analytics', 'threat', 'activity', 'reports', 'health', 'settings'])
const ADMIN_TABS = new Set(['overview', 'email', 'analytics', 'review', 'logs', 'reports', 'settings'])

export default function AdminPage() {
  const { data: me } = useMe()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { t } = useTranslation()
  const tab = searchParams.get('tab') || 'overview'
  const isSuper = me?.user?.role === 'superadmin'
  const isAdmin = me?.user?.role === 'admin'
  // Keep direct/query-string navigation within the tabs available to each role.
  useEffect(() => {
    if (!me) return
    const allowedTabs = isSuper ? SUPERADMIN_TABS : isAdmin ? ADMIN_TABS : new Set()
    if (!allowedTabs.has(tab)) {
      setSearchParams({ tab: 'overview' }, { replace: true })
    }
  }, [tab, isSuper, isAdmin, me, setSearchParams])

  const [reports, setReports] = useState([])
  const [trackData, setTrackData] = useState(null)
  const [msg, setMsg] = useState('')
  const [expandedReport, setExpandedReport] = useState(null)
  const [replyText, setReplyText] = useState('')
  const [filterCategory, setFilterCategory] = useState('all')
  const [filterMailbox, setFilterMailbox] = useState('all')
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
  const [exportOpen, setExportOpen] = useState(false)

  const fetchData = () => {
    api.get('/admin/reports').then((r) => setReports(r.data)).catch(() => {})
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
      // Do not present cached/local mailbox entries as if they came from the server.
      setMailboxRows([])
      setMailboxState([])
    }
  }

  // Keep dashboard values synchronized with the database.
  useEffect(() => {
    fetchData()
    fetchMailboxes()
    const interval = window.setInterval(() => {
      fetchData()
      fetchMailboxes()
    }, 10000)
    return () => window.clearInterval(interval)
  }, [])

  // Fetch superadmin-only track data once role is known
  useEffect(() => {
    if (isSuper) {
      api.get('/admin/track').then((r) => setTrackData(r.data)).catch(() => setTrackData(null))
      api.get('/settings').then((r) => {
        const persisted = String(r.data?.organization_domain || '').trim()
        if (persisted) {
          setMailDomainState(persisted)
          setDomainDraft(persisted)
          setMailDomain(persisted)
        }
      }).catch(() => {})
    }
  }, [isSuper])

  const handleResolveReport = async (id) => {
    try {
      await api.put(`/admin/reports/${id}`, { status: 'resolved' })
      fetchData()
    } catch (e) { setMsg(t('msg.reportUpdateError')) }
  }

  const handleReplyReport = async (id) => {
    if (!replyText.trim()) return
    try {
      await api.put(`/admin/reports/${id}`, { admin_reply: replyText.trim() })
      setReplyText('')
      setExpandedReport(null)
      fetchData()
    } catch (e) { setMsg(t('msg.reportReplyError')) }
  }

  const handleStatusChange = async (id, status) => {
    try {
      await api.put(`/admin/reports/${id}`, { status })
      fetchData()
    } catch (e) { setMsg(t('msg.statusUpdateError')) }
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
      setMailboxError(t('mailbox.validEmail'))
      return
    }
    if (!passwordValid) {
      setMailboxError(t('mailbox.passwordRequirements'))
      return
    }
    if (mailboxes.includes(email)) {
      setMailboxError(t('mailbox.emailExists'))
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
      setMsg(t('msg.mailboxCreated').replace('{email}', email))
      setTimeout(() => setMsg(''), 4000)
    } catch (e) {
      setMailboxError(e.response?.data?.detail || t('msg.mailboxAddError'))
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
      setMsg(t('msg.mailboxDeleted').replace('{email}', row.email))
      setTimeout(() => setMsg(''), 4000)
    } catch (e) {
      setMsg(e.response?.data?.detail || t('msg.mailboxDeleteError'))
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
      setMsg(t('msg.passwordUpdated').replace('{email}', passwordMailbox.email))
      setPasswordMailbox(null)
      setPasswordDraft('')
      setTimeout(() => setMsg(''), 4000)
    } catch (e) {
      setMailboxError(e.response?.data?.detail || t('msg.passwordUpdateError'))
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
      setMailboxError(t('mailbox.invalidTarget'))
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
      setMsg(t('msg.forwarderCreated').replace('{email}', forwarderMailbox.email))
      setForwarderMailbox(null)
      setForwarderTarget('')
      setMailboxError('')
      setTimeout(() => setMsg(''), 4000)
    } catch (e) {
      setMailboxError(e.response?.data?.detail || t('msg.forwarderSaveError'))
    }
  }

  const handleSaveDomain = () => {
    const clean = domainDraft.trim().toLowerCase().replace(/^@+/, '')
    setDomainError('')
    if (!/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(clean)) {
      setDomainError(t('mailbox.validDomain'))
      return
    }
    const existingOutsideDomain = mailboxes.filter((email) => !email.endsWith(`@${clean}`))
    if (existingOutsideDomain.length > 0) {
      setDomainError(t('mailbox.domainConflict').replace('{list}', existingOutsideDomain.join(', ')))
      return
    }
    api.post('/settings', { organization_domain: clean })
      .then(() => {
        const saved = setMailDomain(clean)
        setMailDomainState(saved)
        setDomainDraft(saved)
        setMsg(t('msg.domainUpdated').replace('{domain}', saved))
        setTimeout(() => setMsg(''), 4000)
      })
      .catch((error) => {
        setDomainError(error.response?.data?.detail || t('msg.settings.saveError'))
      })
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

  const reportMailboxes = [...new Set(reports.map((report) => report.mailbox_email).filter(Boolean))].sort()
  const filteredReports = reports.filter((report) => (
    (filterCategory === 'all' || report.category === filterCategory) &&
    (filterMailbox === 'all' || report.mailbox_email === filterMailbox)
  ))

  return (
    <AdminShell>
      <div className={styles.page}>
        {msg && <div className={styles.msg}>{msg}</div>}

        {tab === 'overview' && (
          <SuperadminDashboardOverview isSuperadmin={isSuper} />
        )}

        {tab === 'users' && isSuper && (
          <SuperadminUserManagement />
        )}

        {tab === 'reports' && (
          <div className={trackStyles.wrap}>
            <div className={trackStyles.header}>
              <div>
                <h1 className={trackStyles.title}><AlertCircle size={20} /> {t('emailReport.title')}</h1>
                <p className={trackStyles.lastUpdated}>{t('emailReport.subtitle')}</p>
              </div>
              <div className={trackStyles.headerActions}>
                <select
                  value={filterMailbox}
                  onChange={(event) => setFilterMailbox(event.target.value)}
                  aria-label={t('emailReport.mailbox')}
                  style={{ padding: '6px 30px 6px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)', fontFamily: 'inherit', fontSize: '0.78rem' }}
                >
                  <option value="all">{t('emailReport.allMailboxes')}</option>
                  {reportMailboxes.map((email) => <option key={email} value={email}>{email}</option>)}
                </select>
                {['all', 'question', 'bug', 'false_positive', 'access', 'other'].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setFilterCategory(cat)}
                    style={{
                      padding: '4px 12px', borderRadius: 20, border: '1px solid #dadce0', cursor: 'pointer',
                      fontSize: '0.78rem', fontWeight: 500,
                      background: filterCategory === cat ? (CATEGORY_COLORS[cat] || '#1a73e8') : '#fff',
                      color: filterCategory === cat ? '#fff' : 'var(--text-muted)',
                      transition: 'all 0.15s',
                    }}
                  >
                    {cat === 'all' ? t('report.filterAll') : t('category.' + cat)}
                  </button>
                ))}
              </div>
            </div>
            {filteredReports.length === 0 ? (
              <div style={{ padding: '48px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                {t('report.empty')}
              </div>
            ) : (
              <div className={trackStyles.panel}>
                <h3 className={trackStyles.panelTitle}><FileText size={15} /> {filteredReports.length} {t('report.count')}</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {filteredReports.map((r) => (
                    <div key={r.id} style={{ border: '1px solid #e0e0e0', borderRadius: 10, background: '#fff', overflow: 'hidden' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', borderBottom: expandedReport === r.id ? '1px solid #f0f0f0' : 'none', cursor: 'pointer' }}
                        onClick={() => setExpandedReport(expandedReport === r.id ? null : r.id)}>
                        <strong style={{ fontSize: '0.88rem' }}>{r.mailbox_email || r.username}</strong>
                        <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: '0.72rem', fontWeight: 600, background: CATEGORY_COLORS[r.category] || '#5f6368', color: '#fff' }}>
                          {t('category.' + r.category)}
                        </span>
                        <span style={{ fontSize: '0.75rem', color: PRIORITY_COLORS[r.priority] || '#5f6368', display: 'flex', alignItems: 'center', gap: 3 }}>
                          <Flag size={11} /> {r.priority}
                        </span>
                        <span style={{ marginLeft: 'auto', padding: '2px 8px', borderRadius: 4, fontSize: '0.72rem', fontWeight: 600,
                          background: r.status === 'open' ? '#fce8e6' : r.status === 'in_progress' ? '#fef9e7' : '#e8f5e9',
                          color: r.status === 'open' ? '#c5221f' : r.status === 'in_progress' ? '#856404' : '#137333' }}>
                          {r.status === 'open' ? t('report.statusOpen') : r.status === 'in_progress' ? t('report.statusProgress') : t('report.statusResolved')}
                        </span>
                        <ChevronDown size={15} style={{ color: 'var(--text-muted)', transform: expandedReport === r.id ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
                      </div>
                      <div style={{ padding: '0 16px 12px', paddingTop: 8 }}>
                        <p style={{ margin: '0 0 4px', fontSize: '0.82rem', fontWeight: 600 }}>{r.subject}</p>
                        <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-muted)' }}>{r.message}</p>
                      </div>
                      {expandedReport === r.id && (
                        <div style={{ padding: '12px 16px', borderTop: '1px solid #f0f0f0', background: '#fafafa' }}>
                          {r.admin_reply && (
                            <div style={{ marginBottom: 10, padding: '8px 12px', background: '#e8f0fe', borderRadius: 8 }}>
                              <strong style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{t('report.adminReply')}</strong>
                              <p style={{ margin: '4px 0 0', fontSize: '0.8125rem', color: 'var(--text)' }}>{r.admin_reply}</p>
                            </div>
                          )}
                          <textarea
                            style={{ width: '100%', borderRadius: 8, border: '1px solid #dadce0', padding: '8px 12px', fontSize: '0.85rem', resize: 'vertical', fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box' }}
                            placeholder={t('report.replyPlaceholder')}
                            value={expandedReport === r.id ? replyText : ''}
                            onChange={(e) => setReplyText(e.target.value)}
                            rows={3}
                          />
                          <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                            <button className={trackStyles.btnRefresh} onClick={() => handleReplyReport(r.id)} disabled={!replyText.trim()}>
                              <Reply size={13} /> {t('report.sendReply')}
                            </button>
                            {r.status !== 'resolved' && (
                              <>
                                <button className={trackStyles.btnRefresh} onClick={() => handleStatusChange(r.id, 'in_progress')}>
                                  <Activity size={13} /> {t('report.process')}
                                </button>
                                <button className={trackStyles.btnRefresh} onClick={() => handleResolveReport(r.id)}>
                                  <Check size={13} /> {t('report.resolve')}
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {tab === 'activity' && isSuper && (
          <AuditLogEmbed />
        )}

        {tab === 'track' && (
          <div className={trackStyles.wrap}>
            {/* Header */}
            <div className={trackStyles.header}>
              <div>
                <h1 className={trackStyles.title}><Shield size={20} /> Monitoring</h1>
                <p className={trackStyles.lastUpdated}>Monitoring aktivitas admin dan email mencurigakan dari mailbox aktif.</p>
              </div>
              <div className={trackStyles.headerActions}>
                <button className={trackStyles.btnRefresh} onClick={() => api.get('/admin/track').then((r) => setTrackData(r.data)).catch(() => {})}>
                  <RefreshCw size={14} /> {t('tracking.refresh')}
                </button>
              </div>
            </div>

            {!trackData ? (
              <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.9rem' }}>{t('tracking.loading')}</div>
            ) : (
              <>
                {/* Summary cards */}
                <div className={trackStyles.summaryGrid}>
                  <div className={`${trackStyles.summaryCard} ${trackStyles.cardBlue}`}>
                    <div className={trackStyles.cardIcon}><Mail size={18} /></div>
                    <div className={trackStyles.cardContent}>
                      <div className={trackStyles.cardValue}>{trackData.total_emails ?? 0}</div>
                      <div className={trackStyles.cardLabel}>{t('tracking.totalEmail')}</div>
                      <div className={trackStyles.cardSubtext}>{t('tracking.allUsers')}</div>
                    </div>
                  </div>
                  <div className={`${trackStyles.summaryCard} ${trackStyles.cardGreen}`}>
                    <div className={trackStyles.cardIcon}><CheckCircle2 size={18} /></div>
                    <div className={trackStyles.cardContent}>
                      <div className={trackStyles.cardValue}>{trackData.total_clean ?? 0}</div>
                      <div className={trackStyles.cardLabel}>{t('tracking.clean')}</div>
                      <div className={trackStyles.cardSubtext}>{t('tracking.deliveredSafe')}</div>
                    </div>
                  </div>
                  <div className={`${trackStyles.summaryCard} ${trackStyles.cardYellow}`}>
                    <div className={trackStyles.cardIcon}><AlertTriangle size={18} /></div>
                    <div className={trackStyles.cardContent}>
                      <div className={trackStyles.cardValue}>{trackData.total_warn ?? 0}</div>
                      <div className={trackStyles.cardLabel}>{t('tracking.spamWarn')}</div>
                      <div className={trackStyles.cardSubtext}>{t('tracking.suspicious')}</div>
                    </div>
                  </div>
                  <div className={`${trackStyles.summaryCard} ${trackStyles.cardRed}`}>
                    <div className={trackStyles.cardIcon}><ShieldAlert size={18} /></div>
                    <div className={trackStyles.cardContent}>
                      <div className={trackStyles.cardValue}>{trackData.total_quarantine ?? 0}</div>
                      <div className={trackStyles.cardLabel}>{t('tracking.quarantine')}</div>
                      <div className={trackStyles.cardSubtext}>{t('tracking.blockedThreats')}</div>
                    </div>
                  </div>
                </div>

                {/* Admin Monitoring */}
                <div className={trackStyles.panel}>
                  <h3 className={trackStyles.panelTitle}><Shield size={15} /> {t('tracking.adminMonitoringTitle')}</h3>
                  <p className={trackStyles.periodNote}>{t('tracking.adminMonitoringSub')}</p>
                  <div className={trackStyles.tableWrap}>
                    <table className={trackStyles.table}>
                      <thead><tr>
                        <th>Admin</th><th>Aktivitas Terbaru</th><th>Email Mencurigakan</th>
                      </tr></thead>
                      <tbody>
                        {(trackData.admins || []).filter((admin) => admin.role === 'admin').map((admin) => {
                          return (
                            <tr key={admin.username}>
                              <td className={trackStyles.tdBold}>{admin.username}</td>
                              <td>
                                {admin.recent_actions?.length ? admin.recent_actions.slice(0, 3).map((a, i) => (
                                  <div key={i} style={{ fontSize:'0.75rem', color:'var(--text-muted)', lineHeight:'1.6', marginBottom: 6 }}>
                                    <strong style={{ color:'var(--text)' }}>{String(a.action || '-').replaceAll('_', ' ')}</strong>
                                    <div>{a.details || '-'}</div>
                                    <div style={{ color:'var(--text)' }}>{a.created_at?.split('.')[0]}</div>
                                  </div>
                                )) : <span className={trackStyles.tdMuted}>Belum ada aktivitas admin.</span>}
                              </td>
                              <td>
                                {admin.suspicious_actions?.length ? admin.suspicious_actions.slice(0, 2).map((a, i) => (
                                  <div key={i} style={{ fontSize:'0.75rem', lineHeight:'1.6', marginBottom: 6 }}>
                                    <strong style={{ color:'#c5221f' }}>{String(a.action || '-').replaceAll('_', ' ')}</strong>
                                    <div>{a.details || '-'}</div>
                                    <div className={trackStyles.tdMuted}>{a.created_at?.split('.')[0]}</div>
                                  </div>
                                )) : <span className={trackStyles.tdMuted}>Tidak ada email mencurigakan.</span>}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Suspicious Activity Feed */}
                <div className={trackStyles.panel}>
                  <h3 className={trackStyles.panelTitle}><AlertCircle size={15} /> Suspicious Email Feed</h3>
                  <p className={trackStyles.periodNote}>Email WARN dan QUARANTINE terbaru dari mailbox aktif.</p>
                  <div className={trackStyles.tableWrap}>
                    <table className={trackStyles.table}>
                      <thead><tr>
                        <th>Mailbox</th><th>Status</th><th>Detail</th><th>Waktu</th>
                      </tr></thead>
                      <tbody>
                        {trackData.suspicious_activities?.length ? trackData.suspicious_activities.map((item, index) => (
                          <tr key={item.email_id || index}>
                            <td className={trackStyles.tdBold}>{item.user}</td>
                            <td>
                              <span style={{ display:'inline-block', padding:'2px 8px', borderRadius:'4px', fontSize:'0.72rem', fontWeight:600, background:'#fce8e6', color:'#c5221f' }}>
                                {item.action}
                              </span>
                            </td>
                            <td className={trackStyles.tdEllipsis}>{item.details || '—'}</td>
                            <td style={{ fontFamily:'monospace', fontSize:'0.75rem', whiteSpace:'nowrap' }}>{item.created_at?.split('.')[0]}</td>
                          </tr>
                        )) : (
                          <tr>
                            <td colSpan={4} className={trackStyles.tdMuted} style={{ textAlign: 'center', padding: '28px 16px' }}>
                              Tidak ada email mencurigakan pada mailbox aktif.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {tab === 'email' && isSuper && (
          <AdminMailboxManagement />
        )}
        {tab === 'email' && !isSuper && (
          <AdminMailboxManagement />
        )}

        {tab === 'threat' && (
          <ThreatReportPage />
        )}

        {tab === 'analytics' && (isSuper || isAdmin) && (
          <SuperadminUserAnalytics onExport={() => setExportOpen(true)} />
        )}

        {tab === 'review' && !isSuper && (
          <AdminQuarantineReview />
        )}

        {tab === 'review' && isSuper && (
          <AdminQuarantineReview />
        )}

        {tab === 'logs' && !isSuper && (
          <AdminDetectionLogs />
        )}

        {tab === 'logs' && isSuper && (
          <AdminDetectionLogs />
        )}

        {tab === 'health' && isSuper && (
          <SuperadminSystemHealth />
        )}

        {tab === 'settings' && isSuper && (
          <div className={trackStyles.wrap}>
            <div className={trackStyles.header}>
              <div>
                <h1 className={trackStyles.title}><Settings size={20} /> {t('settings.title')}</h1>
                <p className={trackStyles.lastUpdated}>{t('settings.subtitle')}</p>
              </div>
            </div>
            <AdminProfileSettings superadminOnly />
            <div className={trackStyles.panel}>
              <h3 className={trackStyles.panelTitle}><Mail size={15} /> {t('settings.emailConfig')}</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid #f0f0f0' }}>
                  <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>{t('settings.orgDomain')}</span>
                  <strong style={{ fontSize: '0.875rem' }}>@{mailDomain}</strong>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)' }}>{t('settings.editDomainLabel')}</label>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{t('settings.editDomainHint').replace('{default}', DEFAULT_MAIL_DOMAIN)}</span>
                  <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                    <input
                      style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: '1px solid #dadce0', fontSize: '0.875rem', outline: 'none', fontFamily: 'inherit' }}
                      value={domainDraft}
                      onChange={(e) => { setDomainDraft(e.target.value); setDomainError('') }}
                      placeholder={t('settings.domainPlaceholder')}
                    />
                    <button className={trackStyles.btnRefresh} onClick={handleSaveDomain}>
                      <Save size={14} /> {t('settings.saveDomain')}
                    </button>
                  </div>
                  {domainError && <div style={{ color: '#c5221f', fontSize: '0.8rem', marginTop: 2 }}>{domainError}</div>}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderTop: '1px solid #f0f0f0' }}>
                  <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>{t('settings.adminLogin')}</span>
                  <strong style={{ fontSize: '0.875rem' }}>{me?.user?.username}</strong>
                </div>
                <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                  {t('settings.prodNote')}
                </p>
              </div>
            </div>
          </div>
        )}
        {tab === 'settings' && !isSuper && <AdminProfileSettings />}
      </div>
      <ExportModal open={exportOpen} onClose={() => setExportOpen(false)} userRole={me?.user?.role} />
    </AdminShell>
  )
}
