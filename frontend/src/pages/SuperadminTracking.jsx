import { useState, useEffect } from 'react'
import api from '../api/client'
import {
  Shield, ShieldAlert, ShieldCheck, Mail, Activity, Users, User,
  AlertTriangle, CheckCircle, XCircle, Clock, ExternalLink,
  Search, Filter, ChevronDown, ChevronUp, Eye, X,
  Server, Wifi, Globe, Lock, Unlock,
  Trash2, Edit3, CheckSquare, Square, RefreshCw,
  Save, AlertOctagon
} from 'lucide-react'
import styles from './SuperadminTracking.module.css'

const CATEGORY_COLORS = {
  CLEAN: '#34a853', WARN: '#f29900', QUARANTINE: '#ea4335',
  SPAM: '#ea4335', PHISHING: '#c5221f', MALWARE: '#9334e6'
}

export default function SuperadminTracking() {
  const [trackData, setTrackData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [roleFilter, setRoleFilter] = useState('all')
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedUser, setExpandedUser] = useState(null)
  const [userEmails, setUserEmails] = useState({})
  const [loadingEmails, setLoadingEmails] = useState({})
  const [selectedEmail, setSelectedEmail] = useState(null)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [actionLoading, setActionLoading] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)
  const [editingEmail, setEditingEmail] = useState(null)
  const [editForm, setEditForm] = useState({})

  useEffect(() => {
    setLoading(true)
    api.get('/admin/track')
      .then(r => setTrackData(r.data))
      .catch(() => setTrackData(null))
      .finally(() => setLoading(false))
  }, [])

  const reload = () => {
    setLoading(true)
    api.get('/admin/track')
      .then(r => setTrackData(r.data))
      .catch(() => setTrackData(null))
      .finally(() => setLoading(false))
  }

  const loadUserEmails = async (username) => {
    if (userEmails[username]) return
    setLoadingEmails(prev => ({ ...prev, [username]: true }))
    try {
      const r = await api.get(`/admin/user-emails/${username}`)
      setUserEmails(prev => ({ ...prev, [username]: r.data }))
    } catch {
      setUserEmails(prev => ({ ...prev, [username]: [] }))
    }
    setLoadingEmails(prev => ({ ...prev, [username]: false }))
  }

  const toggleUser = (username) => {
    if (expandedUser === username) {
      setExpandedUser(null)
      return
    }
    setExpandedUser(username)
    loadUserEmails(username)
  }

  const toggleSelectAll = (emails) => {
    if (selectedIds.size === emails.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(emails.map(e => e.email_id)))
    }
  }

  const toggleSelect = (emailId) => {
    const next = new Set(selectedIds)
    if (next.has(emailId)) next.delete(emailId)
    else next.add(emailId)
    setSelectedIds(next)
  }

  const doAction = async (action, emailId) => {
    setActionLoading(true)
    try {
      if (action === 'delete') {
        await api.delete(`/admin/emails/${emailId}`)
      } else if (action === 'release') {
        await api.put(`/admin/emails/${emailId}/release`)
      } else if (action === 'confirm_spam') {
        await api.put(`/admin/emails/${emailId}/confirm-spam`)
      }
      setUserEmails(prev => ({
        ...prev,
        [expandedUser]: (prev[expandedUser] || []).filter(e => e.email_id !== emailId)
      }))
      if (selectedIds.has(emailId)) {
        const next = new Set(selectedIds)
        next.delete(emailId)
        setSelectedIds(next)
      }
    } catch (e) {
      alert('Action failed: ' + (e.response?.data?.detail || e.message))
    }
    setActionLoading(false)
    setConfirmAction(null)
  }

  const doBatchAction = async (action) => {
    if (selectedIds.size === 0) return
    setActionLoading(true)
    try {
      await api.post('/admin/emails/batch', {
        email_ids: Array.from(selectedIds),
        action: action,
      })
      reload()
      setSelectedIds(new Set())
    } catch (e) {
      alert('Batch action failed: ' + (e.response?.data?.detail || e.message))
    }
    setActionLoading(false)
    setConfirmAction(null)
  }

  const openEditModal = (email) => {
    setEditingEmail(email.email_id)
    setEditForm({
      label: email.label || 'CLEAN',
      category: email.category || 'clean',
      status: email.status || 'pending',
      subject: email.subject || '',
      fused_score: email.fused_score || 0,
    })
  }

  const saveEdit = async () => {
    if (!editingEmail) return
    setActionLoading(true)
    try {
      await api.put(`/admin/emails/${editingEmail}/update`, editForm)
      setEditingEmail(null)
      if (expandedUser && userEmails[expandedUser]) {
        setUserEmails(prev => ({
          ...prev,
          [expandedUser]: (prev[expandedUser] || []).map(e =>
            e.email_id === editingEmail ? { ...e, ...editForm } : e
          )
        }))
      }
    } catch (e) {
      alert('Update failed: ' + (e.response?.data?.detail || e.message))
    }
    setActionLoading(false)
  }

  const emailActions = (email) => (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      <button
        className={styles.viewBtn}
        style={{ color: '#34a853', borderColor: '#34a853' }}
        onClick={() => setConfirmAction({ action: 'release', emailId: email.email_id, label: 'release this email' })}
        title="Release email"
      >
        <CheckCircle size={11} /> Release
      </button>
      <button
        className={styles.viewBtn}
        style={{ color: '#ea4335', borderColor: '#ea4335' }}
        onClick={() => setConfirmAction({ action: 'confirm_spam', emailId: email.email_id, label: 'confirm as spam' })}
        title="Confirm as spam"
      >
        <AlertOctagon size={11} /> Spam
      </button>
      <button
        className={styles.viewBtn}
        style={{ color: '#1a73e8', borderColor: '#1a73e8' }}
        onClick={() => openEditModal(email)}
        title="Edit email"
      >
        <Edit3 size={11} /> Edit
      </button>
      <button
        className={styles.viewBtn}
        style={{ color: '#c5221f', borderColor: '#c5221f' }}
        onClick={() => setConfirmAction({ action: 'delete', emailId: email.email_id, label: 'permanently delete this email' })}
        title="Delete permanently"
      >
        <Trash2 size={11} /> Delete
      </button>
    </div>
  )

  if (loading) {
    return <div className={styles.loadingState}>Loading tracking data...</div>
  }
  if (!trackData) {
    return <div className={styles.errorState}>Failed to load tracking data.</div>
  }

  const { total_emails, total_clean, total_warn, total_quarantine,
    health_status, health_message, health_threat_ratio,
    organizations, users, admins, suspicious_activities } = trackData

  const getHealthColor = () => {
    if (health_status === 'critical') return '#c5221f'
    if (health_status === 'warning') return '#f29900'
    return '#34a853'
  }
  const getHealthBg = () => {
    if (health_status === 'critical') return '#fce8e6'
    if (health_status === 'warning') return '#fef7e0'
    return '#e6f4ea'
  }

  const filteredUsers = (users || []).filter(u => {
    const matchRole = roleFilter === 'all' ||
      (roleFilter === 'admin' && (u.role === 'superadmin' || u.role === 'admin')) ||
      (roleFilter === 'user' && u.role === 'user')
    const matchSearch = !searchTerm ||
      u.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (u.email && u.email.toLowerCase().includes(searchTerm.toLowerCase()))
    return matchRole && matchSearch
  })

  const currentEmails = expandedUser ? (userEmails[expandedUser] || []) : []
  const allSelected = currentEmails.length > 0 && selectedIds.size === currentEmails.length

  return (
    <div className={styles.trackWrap}>
      {/* Health Status Banner */}
      <div className={styles.healthBanner} style={{ background: getHealthBg(), borderLeftColor: getHealthColor() }}>
        <div className={styles.healthBannerLeft}>
          {health_status === 'critical' ? <XCircle size={20} color={getHealthColor()} /> :
           health_status === 'warning' ? <AlertTriangle size={20} color={getHealthColor()} /> :
           <CheckCircle size={20} color={getHealthColor()} />}
          <div>
            <strong style={{ color: getHealthColor(), textTransform: 'uppercase' }}>{health_status}</strong>
            <span>{health_message}</span>
          </div>
        </div>
        <div className={styles.healthMetric}>
          <span>Threat Ratio</span>
          <strong>{(health_threat_ratio * 100).toFixed(1)}%</strong>
        </div>
      </div>

      {/* Stats Grid */}
      <div className={styles.statsGrid}>
        <div className={styles.statCard}>
          <Mail size={20} />
          <div>
            <span className={styles.statValue}>{total_emails ?? 0}</span>
            <span className={styles.statLabel}>Total Emails</span>
            <span className={styles.statSub}>All organizations</span>
          </div>
        </div>
        <div className={styles.statCard}>
          <ShieldCheck size={20} />
          <div>
            <span className={styles.statValue}>{total_clean ?? 0}</span>
            <span className={styles.statLabel}>Clean</span>
            <span className={styles.statSub}>Safe & delivered</span>
          </div>
        </div>
        <div className={styles.statCard}>
          <ShieldAlert size={20} />
          <div>
            <span className={styles.statValue}>{total_warn ?? 0}</span>
            <span className={styles.statLabel}>Spam/Warn</span>
            <span className={styles.statSub}>Suspicious flagged</span>
          </div>
        </div>
        <div className={styles.statCard}>
          <XCircle size={20} />
          <div>
            <span className={styles.statValue}>{total_quarantine ?? 0}</span>
            <span className={styles.statLabel}>Quarantined</span>
            <span className={styles.statSub}>Blocked threats</span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className={styles.filterBar}>
        <div className={styles.filterLeft}>
          <Filter size={14} />
          <span>Filter by role:</span>
          {['all', 'admin', 'user'].map(r => (
            <button
              key={r}
              className={`${styles.filterChip} ${roleFilter === r ? styles.filterChipActive : ''}`}
              onClick={() => setRoleFilter(r)}
            >
              {r === 'all' ? 'All' : r === 'admin' ? 'Admin' : 'User'}
            </button>
          ))}
        </div>
        <div className={styles.searchWrap}>
          <Search size={14} />
          <input
            type="text"
            placeholder="Search by username or email..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className={styles.searchInput}
          />
        </div>
      </div>

      {/* Organization Traffic */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <Mail size={16} />
          <strong>Organization Email Traffic</strong>
          <span className={styles.cardBadge}>{organizations?.length || 0} orgs</span>
        </div>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Organization</th>
              <th>Users</th>
              <th>Total</th>
              <th>Clean</th>
              <th>Warn</th>
              <th>Quarantine</th>
              <th>Threat %</th>
            </tr>
          </thead>
          <tbody>
            {organizations?.map(org => (
              <tr key={org.organization_id}>
                <td className={styles.nameCell}>{org.organization_name || 'Unknown'}</td>
                <td>{org.users}</td>
                <td>{org.total_emails}</td>
                <td><span className={styles.labelClean}>{org.clean}</span></td>
                <td><span className={styles.labelWarn}>{org.warn}</span></td>
                <td><span className={styles.labelQuar}>{org.quarantine}</span></td>
                <td>
                  <span className={`${styles.threatPct} ${
                    org.threat_ratio > 0.3 ? styles.threatHigh :
                    org.threat_ratio > 0.15 ? styles.threatMid : styles.threatLow
                  }`}>
                    {(org.threat_ratio * 100).toFixed(1)}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Per-User Email Tracking */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <Users size={16} />
          <strong>Per-User Email Tracking</strong>
          <span className={styles.cardBadge}>{filteredUsers.length} users</span>
          <button className={styles.viewBtn} onClick={reload} style={{ marginLeft: 8 }}>
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
        <table className={styles.table}>
          <thead>
            <tr>
              <th style={{ width: 30 }}></th>
              <th>User</th>
              <th>Role</th>
              <th>Organization</th>
              <th>Total</th>
              <th>Clean</th>
              <th>Warn</th>
              <th>Quarantine</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.map(u => (
              <tr key={u.username}>
                <td>
                  <button className={styles.expandBtn} onClick={() => toggleUser(u.username)}>
                    {expandedUser === u.username ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                </td>
                <td className={styles.nameCell}>
                  <div className={styles.userLabel}>
                    {u.role === 'user' ? <User size={14} /> : <Shield size={14} />}
                    <span>{u.username}</span>
                  </div>
                </td>
                <td><span className={styles.roleBadge}>{u.role}</span></td>
                <td className={styles.muted}>{u.organization_name || '-'}</td>
                <td>{u.total_emails}</td>
                <td><span className={styles.labelClean}>{u.clean}</span></td>
                <td><span className={styles.labelWarn}>{u.warn}</span></td>
                <td><span className={styles.labelQuar}>{u.quarantine}</span></td>
                <td>
                  <button className={styles.viewBtn} onClick={() => toggleUser(u.username)}>
                    <Eye size={13} /> Emails
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Expanded user email rows */}
        {expandedUser && (
          <div className={styles.expandedSection}>
            <div className={styles.expandedHeader}>
              <strong>Email details for: {expandedUser}</strong>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {selectedIds.size > 0 && (
                  <>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {selectedIds.size} selected
                    </span>
                    <button
                      className={styles.viewBtn}
                      style={{ color: '#34a853', borderColor: '#34a853' }}
                      onClick={() => setConfirmAction({ action: 'batch_release', label: `release ${selectedIds.size} emails` })}
                    >
                      <CheckCircle size={11} /> Release All
                    </button>
                    <button
                      className={styles.viewBtn}
                      style={{ color: '#ea4335', borderColor: '#ea4335' }}
                      onClick={() => setConfirmAction({ action: 'batch_delete', label: `permanently delete ${selectedIds.size} emails` })}
                    >
                      <Trash2 size={11} /> Delete All
                    </button>
                  </>
                )}
                <button className={styles.closeExpandBtn} onClick={() => { setExpandedUser(null); setSelectedIds(new Set()) }}>
                  <X size={14} />
                </button>
              </div>
            </div>
            {loadingEmails[expandedUser] ? (
              <div className={styles.loadingSmall}>Loading emails...</div>
            ) : (
              <>
                <table className={styles.innerTable}>
                  <thead>
                    <tr>
                      <th style={{ width: 30 }}>
                        <button className={styles.expandBtn} onClick={() => toggleSelectAll(currentEmails)}>
                          {allSelected ? <CheckSquare size={14} color="#1a73e8" /> : <Square size={14} />}
                        </button>
                      </th>
                      <th>Subject</th>
                      <th>Sender</th>
                      <th>Label</th>
                      <th>Score</th>
                      <th>Category</th>
                      <th>Received</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {currentEmails.slice(0, 50).map((e, i) => (
                      <tr key={e.email_id || i} style={{ background: selectedIds.has(e.email_id) ? '#f0f6ff' : undefined }}>
                        <td>
                          <button className={styles.expandBtn} onClick={() => toggleSelect(e.email_id)}>
                            {selectedIds.has(e.email_id) ? <CheckSquare size={14} color="#1a73e8" /> : <Square size={14} />}
                          </button>
                        </td>
                        <td className={styles.subjectCell}>{e.subject || '(no subject)'}</td>
                        <td className={styles.muted}>{e.sender || '-'}</td>
                        <td>
                          <span className={styles.labelPill} style={{
                            background: CATEGORY_COLORS[e.label] || '#6b7280',
                            color: '#fff'
                          }}>
                            {e.label || '-'}
                          </span>
                        </td>
                        <td className={styles.mono}>{(e.fused_score ?? 0).toFixed(2)}</td>
                        <td className={styles.muted}>{e.category || '-'}</td>
                        <td className={styles.mono}>{e.received_at ? e.received_at.split('T')[0] : '-'}</td>
                        <td>{emailActions(e)}</td>
                      </tr>
                    ))}
                    {currentEmails.length === 0 && (
                      <tr><td colSpan={8} className={styles.emptyCell}>No emails found for this user.</td></tr>
                    )}
                  </tbody>
                </table>
                {currentEmails.length > 50 && (
                  <div style={{ padding: '8px 16px', textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Showing 50 of {currentEmails.length} emails. Use the search filter to narrow down.
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* Admin Monitoring */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <ShieldAlert size={16} />
          <strong>Admin Monitoring</strong>
          <span className={styles.cardBadge}>{admins?.length || 0} admins</span>
        </div>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Admin</th>
              <th>Role</th>
              <th>Organization</th>
              <th>Recent Actions</th>
              <th>Suspicious Activity</th>
            </tr>
          </thead>
          <tbody>
            {admins?.map(admin => (
              <tr key={admin.username}>
                <td className={styles.nameCell}>{admin.username}</td>
                <td><span className={styles.roleBadge}>{admin.role}</span></td>
                <td className={styles.muted}>{admin.organization_name || 'Global'}</td>
                <td>
                  <div className={styles.actionList}>
                    {admin.recent_actions?.slice(0, 3).map((a, i) => (
                      <div key={i} className={styles.actionItem}>
                        <code className={styles.actionCode}>{a.action}</code>
                        <span className={styles.mono}>{a.created_at?.split('.')[0]}</span>
                      </div>
                    ))}
                  </div>
                </td>
                <td>
                  <div className={styles.actionList}>
                    {admin.suspicious_actions?.slice(0, 2).map((a, i) => (
                      <div key={i} className={styles.actionItem}>
                        <span className={styles.actionText}>{a.action}</span>
                        <span className={styles.ipCell}>
                          <Globe size={10} />
                          {a.ip_address || 'no-ip'}
                        </span>
                      </div>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Suspicious Activity Feed */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <Activity size={16} />
          <strong>Suspicious Activity Feed</strong>
          <span className={styles.cardBadge}>{suspicious_activities?.length || 0} events</span>
        </div>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>User</th>
              <th>Action</th>
              <th>IP Address</th>
              <th>IP Safety</th>
              <th>Details</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {suspicious_activities?.map((item, index) => (
              <tr key={index}>
                <td className={styles.nameCell}>{item.user}</td>
                <td><code className={styles.actionCode}>{item.action}</code></td>
                <td className={styles.mono}>{item.ip_address || '-'}</td>
                <td>
                  {item.ip_safe?.safe ? (
                    <span className={styles.ipSafe}><Lock size={12} /> Safe</span>
                  ) : (
                    <span className={styles.ipUnsafe}><Unlock size={12} /> {item.ip_safe?.reason || 'Unsafe'}</span>
                  )}
                </td>
                <td className={styles.detailCell}>{item.details || '-'}</td>
                <td className={styles.mono}>{item.created_at?.split('.')[0]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Email Detail Modal */}
      {selectedEmail && (
        <div className={styles.modalOverlay} onClick={() => setSelectedEmail(null)}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>Email Detail</h3>
              <button className={styles.modalClose} onClick={() => setSelectedEmail(null)}>
                <X size={18} />
              </button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.modalGrid}>
                <div className={styles.modalField}>
                  <label>Subject</label>
                  <span>{selectedEmail.subject || '(no subject)'}</span>
                </div>
                <div className={styles.modalField}>
                  <label>Sender</label>
                  <span className={styles.mono}>{selectedEmail.sender || '-'}</span>
                </div>
                <div className={styles.modalField}>
                  <label>Recipient</label>
                  <span className={styles.mono}>{selectedEmail.recipient || '-'}</span>
                </div>
                <div className={styles.modalField}>
                  <label>Label</label>
                  <span className={styles.labelPill} style={{
                    background: CATEGORY_COLORS[selectedEmail.label] || '#6b7280',
                    color: '#fff'
                  }}>{selectedEmail.label || '-'}</span>
                </div>
                <div className={styles.modalField}>
                  <label>Category</label>
                  <span>{selectedEmail.category || '-'}</span>
                </div>
                <div className={styles.modalField}>
                  <label>Status</label>
                  <span>{selectedEmail.status || '-'}</span>
                </div>
              </div>

              <div className={styles.modalSectionTitle}>
                <Wifi size={14} />
                <strong>IP Address & Delivery</strong>
              </div>
              <div className={styles.modalGrid}>
                <div className={styles.modalField}>
                  <label>Sender IP</label>
                  <span className={styles.mono}>{selectedEmail.sender_ip || 'N/A'}</span>
                </div>
                <div className={styles.modalField}>
                  <label>Sender IP Safety</label>
                  {selectedEmail.sender_ip_safe ? (
                    selectedEmail.sender_ip_safe.safe ? (
                      <span className={styles.ipSafe}><Lock size={12} /> Safe</span>
                    ) : (
                      <span className={styles.ipUnsafe}>
                        <Unlock size={12} /> {selectedEmail.sender_ip_safe.reason}
                      </span>
                    )
                  ) : '-'}
                </div>
                <div className={styles.modalField}>
                  <label>Receiver IP</label>
                  <span className={styles.mono}>{selectedEmail.receiver_ip || 'N/A'}</span>
                </div>
                <div className={styles.modalField}>
                  <label>Received Time</label>
                  <span className={styles.mono}>
                    <Clock size={12} />
                    {selectedEmail.received_at || '-'}
                  </span>
                </div>
                <div className={styles.modalField}>
                  <label>Created At</label>
                  <span className={styles.mono}>
                    <Clock size={12} />
                    {selectedEmail.created_at?.split('.')[0] || '-'}
                  </span>
                </div>
              </div>

              <div className={styles.modalSectionTitle}>
                <ShieldCheck size={14} />
                <strong>Security Scores & Authentication</strong>
              </div>
              <div className={styles.modalGrid}>
                <div className={styles.modalField}>
                  <label>Fused Score</label>
                  <span className={styles.mono}>{(selectedEmail.fused_score ?? 0).toFixed(2)}</span>
                </div>
                <div className={styles.modalField}>
                  <label>SA Score</label>
                  <span className={styles.mono}>{(selectedEmail.sa_score ?? 0).toFixed(2)}</span>
                </div>
                <div className={styles.modalField}>
                  <label>ML Probability</label>
                  <span className={styles.mono}>{(selectedEmail.ml_probability ?? 0).toFixed(2)}</span>
                </div>
                <div className={styles.modalField}>
                  <label>Anomaly Score</label>
                  <span className={styles.mono}>{(selectedEmail.anomaly_score ?? 0).toFixed(2)}</span>
                </div>
                <div className={styles.modalField}>
                  <label>SPF</label>
                  <span className={styles.mono}>{selectedEmail.spf_result || '-'}</span>
                </div>
                <div className={styles.modalField}>
                  <label>DKIM</label>
                  <span className={styles.mono}>{selectedEmail.dkim_result || '-'}</span>
                </div>
                <div className={styles.modalField}>
                  <label>DMARC</label>
                  <span className={styles.mono}>{selectedEmail.dmarc_result || '-'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Email Modal */}
      {editingEmail && (
        <div className={styles.modalOverlay} onClick={() => setEditingEmail(null)}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>Edit Email</h3>
              <button className={styles.modalClose} onClick={() => setEditingEmail(null)}>
                <X size={18} />
              </button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.modalGrid}>
                <div className={styles.modalField}>
                  <label>Label</label>
                  <select
                    value={editForm.label}
                    onChange={e => setEditForm(f => ({ ...f, label: e.target.value }))}
                    style={{ padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 4, fontSize: '0.82rem' }}
                  >
                    <option value="CLEAN">CLEAN</option>
                    <option value="WARN">WARN</option>
                    <option value="QUARANTINE">QUARANTINE</option>
                  </select>
                </div>
                <div className={styles.modalField}>
                  <label>Category</label>
                  <select
                    value={editForm.category}
                    onChange={e => setEditForm(f => ({ ...f, category: e.target.value }))}
                    style={{ padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 4, fontSize: '0.82rem' }}
                  >
                    <option value="clean">Clean</option>
                    <option value="spam">Spam</option>
                    <option value="phishing">Phishing</option>
                    <option value="malware">Malware</option>
                  </select>
                </div>
                <div className={styles.modalField}>
                  <label>Status</label>
                  <select
                    value={editForm.status}
                    onChange={e => setEditForm(f => ({ ...f, status: e.target.value }))}
                    style={{ padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 4, fontSize: '0.82rem' }}
                  >
                    <option value="pending">Pending</option>
                    <option value="released">Released</option>
                    <option value="confirmed_spam">Confirmed Spam</option>
                  </select>
                </div>
                <div className={styles.modalField}>
                  <label>Fused Score</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={editForm.fused_score}
                    onChange={e => setEditForm(f => ({ ...f, fused_score: parseFloat(e.target.value) || 0 }))}
                    style={{ padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 4, fontSize: '0.82rem' }}
                  />
                </div>
                <div className={styles.modalField} style={{ gridColumn: '1 / -1' }}>
                  <label>Subject</label>
                  <input
                    type="text"
                    value={editForm.subject}
                    onChange={e => setEditForm(f => ({ ...f, subject: e.target.value }))}
                    style={{ padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 4, fontSize: '0.82rem', width: '100%' }}
                  />
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
                <button className={styles.viewBtn} onClick={() => setEditingEmail(null)}>Cancel</button>
                <button
                  className={styles.viewBtn}
                  style={{ background: '#1a73e8', color: '#fff', borderColor: '#1a73e8' }}
                  onClick={saveEdit}
                  disabled={actionLoading}
                >
                  <Save size={13} /> Save Changes
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal */}
      {confirmAction && (
        <div className={styles.modalOverlay} onClick={() => setConfirmAction(null)}>
          <div className={styles.modal} onClick={e => e.stopPropagation()} style={{ width: 400 }}>
            <div className={styles.modalHeader}>
              <h3>Confirm Action</h3>
              <button className={styles.modalClose} onClick={() => setConfirmAction(null)}>
                <X size={18} />
              </button>
            </div>
            <div className={styles.modalBody}>
              <p style={{ fontSize: '0.85rem', color: 'var(--text)', margin: 0 }}>
                Are you sure you want to <strong>{confirmAction.label}</strong>?
              </p>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
                <button className={styles.viewBtn} onClick={() => setConfirmAction(null)}>Cancel</button>
                <button
                  className={styles.viewBtn}
                  style={{ background: '#c5221f', color: '#fff', borderColor: '#c5221f' }}
                  onClick={() => {
                    if (confirmAction.action === 'batch_delete') doBatchAction('delete')
                    else if (confirmAction.action === 'batch_release') doBatchAction('release')
                    else doAction(confirmAction.action, confirmAction.emailId)
                  }}
                  disabled={actionLoading}
                >
                  {actionLoading ? 'Processing...' : 'Confirm'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
