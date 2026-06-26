import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import GmailShell from '../components/layout/GmailShell'
import api from '../api/client'
import { useMe } from '../api/auth'
import { Users, Shield, Mail, Activity, Plus, X, Check, AlertCircle, MessageSquare, Reply, ChevronDown, ChevronUp, Flag, Filter } from 'lucide-react'
import styles from './AdminPage.module.css'

const CATEGORY_LABELS = { bug: 'Bug / Error', question: 'Pertanyaan', access: 'Akses', false_positive: 'False Positive', other: 'Lainnya' }
const CATEGORY_COLORS = { bug: '#ea4335', question: '#1a73e8', access: '#f29900', false_positive: '#34a853', other: '#5f6368' }
const PRIORITY_COLORS = { low: '#5f6368', normal: '#1a73e8', high: '#f29900', urgent: '#ea4335' }

export default function AdminPage() {
  const { data: me } = useMe()
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
  const [newRole, setNewRole] = useState('analyst')
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

  const fetchData = () => {
    api.get('/admin/users').then((r) => setUsers(r.data)).catch(() => {})
    api.get('/admin/stats').then((r) => setStats(r.data)).catch(() => {})
    api.get('/admin/audit-logs').then((r) => setLogs(r.data)).catch(() => {})
    api.get('/admin/reports').then((r) => setReports(r.data)).catch(() => {})
  }

  useEffect(() => { fetchData() }, [])

  const setTab = (t) => {
    // Prevent non-superadmin from accessing users tab
    if (t === 'users' && !isSuper) return
    setSearchParams({ tab: t })
  }

  const roleBadge = (role) => {
    const colors = { superadmin: '#c5221f', admin: '#f29900', analyst: '#1a73e8', user: '#137333' }
    return <span className={styles.roleBadge} style={{ background: colors[role] || '#5f6368' }}>{role}</span>
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

  const filteredUsers = users.filter((u) => {
    if (roleFilter !== 'all' && u.role !== roleFilter) return false
    return u.username.includes(search) || (u.email || '').includes(search)
  })
  const openReports = reports.filter((r) => r.status === 'open')
  const filteredReports = filterCategory === 'all' ? reports : reports.filter((r) => r.category === filterCategory)

  if (selectedUser) {
    return (
      <GmailShell>
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
      </GmailShell>
    )
  }

  return (
    <GmailShell>
      <div className={styles.page}>
        <div className={styles.header}>
          <h1><Shield size={22} /> Admin Panel</h1>
          <p>Kelola user, pantau aktivitas, dan atur whitelist email</p>
        </div>

        {msg && <div className={styles.msg}>{msg}</div>}

        <div className={styles.tabs}>
          <button className={`${styles.tab} ${tab === 'overview' ? styles.tabActive : ''}`} onClick={() => setTab('overview')}>
            <Activity size={16} /> Overview
          </button>
          {isSuper && (
            <button className={`${styles.tab} ${tab === 'users' ? styles.tabActive : ''}`} onClick={() => setTab('users')}>
              <Users size={16} /> Users
            </button>
          )}
          <button className={`${styles.tab} ${tab === 'reports' ? styles.tabActive : ''}`} onClick={() => setTab('reports')}>
            <AlertCircle size={16} /> Laporan {openReports.length > 0 && <span className={styles.reportBadge}>{openReports.length}</span>}
          </button>
          <button className={`${styles.tab} ${tab === 'activity' ? styles.tabActive : ''}`} onClick={() => setTab('activity')}>
            <Activity size={16} /> Aktivitas
          </button>
        </div>

        {tab === 'overview' && stats && (
          <>
            <div className={styles.statsGrid}>
              <div className={styles.statCard}>
                <Users size={28} />
                <div>
                  <span className={styles.statValue}>{stats.total_users}</span>
                  <span className={styles.statLabel}>Total Users</span>
                  <span className={styles.statSub}>{stats.active_users} aktif</span>
                </div>
              </div>
              <div className={styles.statCard}>
                <Mail size={28} />
                <div>
                  <span className={styles.statValue}>{stats.total_emails}</span>
                  <span className={styles.statLabel}>Total Email</span>
                  <span className={styles.statSub}>{stats.clean} CLEAN / {stats.warn} WARN / {stats.quarantine} QUARANTINE</span>
                </div>
              </div>
              <div className={styles.statCard}>
                <AlertCircle size={28} />
                <div>
                  <span className={styles.statValue}>{openReports.length}</span>
                  <span className={styles.statLabel}>Laporan Terbuka</span>
                  <span className={styles.statSub}>Dari total {reports.length} laporan</span>
                </div>
              </div>
              <div className={styles.statCard}>
                <Activity size={28} />
                <div>
                  <span className={styles.statValue}>{stats.warn + stats.quarantine}</span>
                  <span className={styles.statLabel}>Threat Detected</span>
                  <span className={styles.statSub}>{((stats.warn + stats.quarantine) / Math.max(stats.total_emails, 1) * 100).toFixed(1)}% dari total email</span>
                </div>
              </div>
            </div>

            {reports.length > 0 && (
              <div className={styles.recentSection}>
                <h3>Laporan Terbaru</h3>
                {reports.slice(0, 3).map((r) => (
                  <div key={r.id} className={styles.reportCard}>
                    <div className={styles.reportCardHeader}>
                      <strong>{r.username}</strong>
                      <span className={r.status === 'open' ? styles.reportOpen : styles.reportDone}>{r.status}</span>
                    </div>
                    <p className={styles.reportSubject}>{r.subject}</p>
                    <p className={styles.reportMessage}>{r.message}</p>
                    <span className={styles.reportDate}>{r.created_at?.split('.')[0]}</span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {tab === 'users' && (
          <div className={styles.section}>
            {/* Toolbar: search + role filter + add */}
            <div className={styles.sectionHeader}>
              <input className={styles.searchInput} placeholder="Cari username atau email..." value={search} onChange={(e) => setSearch(e.target.value)} />
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                {['all', 'superadmin', 'admin', 'analyst'].map((r) => (
                  <button
                    key={r}
                    className={styles.filterChip}
                    style={{ background: roleFilter === r ? '#1a73e8' : 'transparent', color: roleFilter === r ? '#fff' : 'var(--text-muted)' }}
                    onClick={() => setRoleFilter(r)}
                  >
                    {r === 'all' ? 'Semua' : r}
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
                  <option value="analyst">Analyst</option>
                  <option value="admin">Admin</option>
                  <option value="superadmin">Superadmin</option>
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
                          <option value="analyst">Analyst</option>
                          <option value="admin">Admin</option>
                          <option value="superadmin">Superadmin</option>
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
      </div>
    </GmailShell>
  )
}
