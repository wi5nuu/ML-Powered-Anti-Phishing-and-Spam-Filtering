import { useState, useEffect, useCallback } from 'react'
import api from '../api/client'
import {
  Users, Plus, X, Check, Search, Filter,
  Shield, User, Mail, Calendar,
  ChevronDown, ChevronUp, AlertCircle,
  Edit3, Trash2, ToggleLeft, ToggleRight,
  KeyRound, Eye, EyeOff, Inbox
} from 'lucide-react'
import styles from './AdminUserManagement.module.css'

const ROLE_LABELS = { superadmin: 'Superadmin', admin: 'Admin', user: 'User' }
const ROLE_COLORS = { superadmin: '#7C3AED', admin: '#2563EB', user: '#059669' }
const ROLE_BG = { superadmin: '#F3E8FF', admin: '#EFF6FF', user: '#ECFDF5' }

export default function AdminUserManagement() {
  const [users, setUsers] = useState([])
  const [mailboxes, setMailboxes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [roleFilter, setRoleFilter] = useState('all')
  const [showAdd, setShowAdd] = useState(false)
  const [editUser, setEditUser] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [msg, setMsg] = useState('')
  const [msgType, setMsgType] = useState('success')
  const [sortBy, setSortBy] = useState('username')
  const [sortDir, setSortDir] = useState('asc')
  const [selectedUser, setSelectedUser] = useState(null)
  const [userEmails, setUserEmails] = useState([])

  const [addForm, setAddForm] = useState({ username: '', email: '', password: '' })
  const [editForm, setEditForm] = useState({ password: '', is_active: true, assigned_mailbox: '' })
  const [showPwd, setShowPwd] = useState(false)
  const [showEditPwd, setShowEditPwd] = useState(false)

  const fetchUsers = useCallback(() => {
    setLoading(true)
    api.get('/admin/users')
      .then((r) => { setUsers(Array.isArray(r.data) ? r.data : []); setLoading(false) })
      .catch((err) => { setError(err.response?.data?.detail || err.message); setLoading(false) })
  }, [])

  const fetchMailboxes = useCallback(() => {
    api.get('/admin/mailboxes')
      .then((r) => { setMailboxes(Array.isArray(r.data) ? r.data : []) })
      .catch(() => {})
  }, [])

  useEffect(() => { fetchUsers(); fetchMailboxes() }, [fetchUsers, fetchMailboxes])

  const showMsg = (text, type = 'success') => {
    setMsg(text); setMsgType(type)
    setTimeout(() => setMsg(''), 5000)
  }

  const handleSort = (field) => {
    if (sortBy === field) { setSortDir(d => d === 'asc' ? 'desc' : 'asc') }
    else { setSortBy(field); setSortDir('asc') }
  }

  const getAssignedMailbox = (username) => {
    return mailboxes.find((m) => m.assigned_to === username)
  }

  const filteredUsers = users
    .filter((u) => {
      if (statusFilter !== 'all') {
        if (statusFilter === 'active' && !u.is_active) return false
        if (statusFilter === 'inactive' && u.is_active) return false
      }
      if (roleFilter !== 'all' && u.role !== roleFilter) return false
      const q = search.toLowerCase()
      return u.username.toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q)
    })
    .sort((a, b) => {
      const aVal = (a[sortBy] || '').toString().toLowerCase()
      const bVal = (b[sortBy] || '').toString().toLowerCase()
      return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
    })

  const handleAddUser = async () => {
    if (!addForm.username || !addForm.password) {
      showMsg('Username dan password harus diisi', 'error'); return
    }
    if (!addForm.email.includes('@')) {
      showMsg('Email tidak valid', 'error'); return
    }
    try {
      await api.post('/admin/users', {
        username: addForm.username,
        email: addForm.email,
        password: addForm.password,
        role: 'user',
      })
      showMsg(`User ${addForm.username} berhasil ditambahkan`)
      setAddForm({ username: '', email: '', password: '' })
      setShowAdd(false)
      fetchUsers()
    } catch (e) {
      showMsg('Gagal: ' + (e.response?.data?.detail || 'unknown error'), 'error')
    }
  }

  const handleEditUser = async () => {
    if (!editUser) return
    const payload = {}
    if (editForm.password) payload.password = editForm.password
    if (editForm.is_active !== editUser.is_active) payload.is_active = editForm.is_active
    try {
      if (Object.keys(payload).length > 0) {
        await api.put(`/admin/users/${editUser.username}`, payload)
      }
      const currentMailbox = getAssignedMailbox(editUser.username)
      if (editForm.assigned_mailbox !== (currentMailbox?.email || '')) {
        if (currentMailbox) {
          await api.put(`/admin/mailboxes/${currentMailbox.id}`, { assigned_to: '' })
        }
        if (editForm.assigned_mailbox) {
          const newMbx = mailboxes.find((m) => m.email === editForm.assigned_mailbox)
          if (newMbx) {
            await api.put(`/admin/mailboxes/${newMbx.id}`, { assigned_to: editUser.username })
          }
        }
        fetchMailboxes()
      }
      showMsg(`User ${editUser.username} berhasil diperbarui`)
      setEditUser(null)
      fetchUsers()
    } catch (e) {
      showMsg('Gagal: ' + (e.response?.data?.detail || 'error'), 'error')
    }
  }

  const handleToggleActive = async (user) => {
    try {
      await api.put(`/admin/users/${user.username}`, { is_active: !user.is_active })
      showMsg(`User ${user.username} ${user.is_active ? 'dinonaktifkan' : 'diaktifkan'}`)
      fetchUsers()
    } catch (e) {
      showMsg('Gagal update status', 'error')
    }
  }

  const handleDeleteUser = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/admin/users/${deleteTarget.username}`)
      showMsg(`User ${deleteTarget.username} dinonaktifkan`)
      setDeleteTarget(null)
      fetchUsers()
    } catch (e) {
      showMsg('Gagal menonaktifkan user', 'error')
    }
  }

  const viewUserEmails = async (username) => {
    try {
      const r = await api.get(`/admin/user-emails/${username}`)
      setUserEmails(r.data)
      setSelectedUser(username)
    } catch (e) {
      showMsg('Gagal memuat email user', 'error')
    }
  }

  const SortIcon = ({ field }) => {
    if (sortBy !== field) return null
    return sortDir === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
  }

  const availableMailboxes = mailboxes.filter((m) => {
    if (!m.is_active) return false
    if (!m.assigned_to) return true
    if (editUser && m.assigned_to === editUser.username) return true
    return false
  })

  // User email detail view
  if (selectedUser) {
    return (
      <div className={styles.page}>
        <button
          className={styles.retryBtn}
          onClick={() => { setSelectedUser(null); setUserEmails([]) }}
          style={{ alignSelf: 'flex-start' }}
        >
          ← Kembali ke Pengguna
        </button>
        <h3 className={styles.title}>
          <Mail size={18} /> Email milik: {selectedUser}
        </h3>
        <div className={styles.tableWrap}>
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
              {userEmails.length === 0 ? (
                <tr><td colSpan={6} className={styles.emptyRow}>Tidak ada email ditemukan</td></tr>
              ) : (
                userEmails.map((e) => (
                  <tr key={e.email_id}>
                    <td className={styles.mono}>{e.email_id?.slice(0, 16)}...</td>
                    <td>{e.subject || '-'}</td>
                    <td>{e.sender || '-'}</td>
                    <td><span className={styles.roleBadge} style={{ background: '#F3F4F6', color: '#374151' }}>{e.label}</span></td>
                    <td className={styles.mono}>{e.fused_score?.toFixed(3)}</td>
                    <td><span className={`${styles.statusDot} ${e.status === 'pending' ? styles.active : styles.inactive}`} />{e.status}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className={styles.loadingState}>
        <div className={styles.spinner} />
        <span>Memuat data pengguna...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.errorState}>
        <AlertCircle size={32} />
        <h3>Gagal Memuat Data</h3>
        <p>{error}</p>
        <button className={styles.retryBtn} onClick={fetchUsers}>Coba Lagi</button>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}><Users size={22} /> Manajemen Pengguna</h1>
          <p className={styles.subtitle}>Kelola pengguna dalam organisasi Anda. Total: {users.length} pengguna</p>
        </div>
        <button className={styles.addBtn} onClick={() => setShowAdd(true)}>
          <Plus size={16} /> Tambah Pengguna
        </button>
      </div>

      {/* Message */}
      {msg && (
        <div className={`${styles.msg} ${msgType === 'error' ? styles.msgError : styles.msgSuccess}`}>
          {msgType === 'error' ? <AlertCircle size={16} /> : <Check size={16} />}
          <span>{msg}</span>
        </div>
      )}

      {/* Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <Search size={16} className={styles.searchIcon} />
          <input
            className={styles.searchInput}
            placeholder="Cari username atau email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className={styles.filterGroup}>
          <Filter size={15} className={styles.filterIcon} />
          <button
            className={`${styles.filterChip} ${roleFilter === 'all' ? styles.filterChipActive : ''}`}
            style={roleFilter === 'all' ? { background: '#1a73e8', color: '#fff', borderColor: 'transparent' } : {}}
            onClick={() => setRoleFilter('all')}
          >
            Semua
          </button>
          <button
            className={`${styles.filterChip} ${roleFilter === 'admin' ? styles.filterChipActive : ''}`}
            style={roleFilter === 'admin' ? { background: '#2563EB', color: '#fff', borderColor: 'transparent' } : {}}
            onClick={() => setRoleFilter('admin')}
          >
            Admin
          </button>
          <button
            className={`${styles.filterChip} ${roleFilter === 'user' ? styles.filterChipActive : ''}`}
            style={roleFilter === 'user' ? { background: '#059669', color: '#fff', borderColor: 'transparent' } : {}}
            onClick={() => setRoleFilter('user')}
          >
            User
          </button>
        </div>
      </div>

      {/* Users Table */}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.sortable} onClick={() => handleSort('username')}>
                Username <SortIcon field="username" />
              </th>
              <th className={styles.sortable} onClick={() => handleSort('email')}>
                Email <SortIcon field="email" />
              </th>
              <th>Role</th>
              <th>Status</th>
              <th>Mailbox</th>
              <th>Aksi</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={6} className={styles.emptyRow}>Tidak ada pengguna ditemukan</td>
              </tr>
            ) : (
              filteredUsers.map((u) => {
                const mailbox = getAssignedMailbox(u.username)
                return (
                  <tr key={u.username}>
                    <td>
                      <div className={styles.usernameCell}>
                        <div className={styles.avatarSmall} style={{ background: ROLE_BG[u.role] || '#F3F4F6', color: ROLE_COLORS[u.role] || '#374151' }}>
                          {u.username.slice(0, 2).toUpperCase()}
                        </div>
                        <span className={styles.usernameTxt}>{u.username}</span>
                      </div>
                    </td>
                    <td className={styles.mono}>{u.email || '—'}</td>
                    <td>
                      <span className={styles.roleBadge} style={{ background: ROLE_BG[u.role] || '#F3F4F6', color: ROLE_COLORS[u.role] || '#374151' }}>
                        {ROLE_LABELS[u.role] || u.role}
                      </span>
                    </td>
                    <td>
                      <span className={`${styles.statusDot} ${u.is_active ? styles.active : styles.inactive}`} />
                      {u.is_active ? 'Aktif' : 'Nonaktif'}
                    </td>
                    <td>
                      {mailbox ? (
                        <span className={styles.assignedMailbox}>{mailbox.email}</span>
                      ) : (
                        <span className={styles.assignedNone}>Belum ada</span>
                      )}
                    </td>
                    <td>
                      <div className={styles.actionGroup}>
                        <button
                          className={styles.actionBtn}
                          onClick={() => viewUserEmails(u.username)}
                          title="Lihat email pengguna"
                        >
                          <Inbox size={14} />
                        </button>
                        <button
                          className={styles.actionBtn}
                          onClick={() => {
                            const currentMbx = getAssignedMailbox(u.username)
                            setEditUser(u)
                            setEditForm({
                              password: '',
                              is_active: u.is_active,
                              assigned_mailbox: currentMbx?.email || '',
                            })
                          }}
                          title="Edit pengguna"
                        >
                          <Edit3 size={14} />
                        </button>
                        <button
                          className={styles.actionBtn}
                          onClick={() => handleToggleActive(u)}
                          title={u.is_active ? 'Nonaktifkan' : 'Aktifkan'}
                        >
                          {u.is_active ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
                        </button>
                        <button
                          className={`${styles.actionBtn} ${styles.actionDanger}`}
                          onClick={() => setDeleteTarget(u)}
                          title="Nonaktifkan pengguna"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* ── Add User Modal ── */}
      {showAdd && (
        <div className={styles.overlay} onClick={() => setShowAdd(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3><Plus size={18} /> Tambah Pengguna Baru</h3>
              <button className={styles.closeBtn} onClick={() => setShowAdd(false)}><X size={18} /></button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}><User size={14} /> Username</label>
                </div>
                <div className={styles.fieldRight}>
                  <input className={styles.input} placeholder="username" value={addForm.username}
                    onChange={(e) => setAddForm({ ...addForm, username: e.target.value })} />
                </div>
              </div>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}><Mail size={14} /> Email</label>
                </div>
                <div className={styles.fieldRight}>
                  <input className={styles.input} type="email" placeholder="user@company.com" value={addForm.email}
                    onChange={(e) => setAddForm({ ...addForm, email: e.target.value })} />
                </div>
              </div>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}><KeyRound size={14} /> Password</label>
                </div>
                <div className={styles.fieldRight}>
                  <div className={styles.pwdWrap}>
                    <input className={styles.input} type={showPwd ? 'text' : 'password'} placeholder="Min. 4 karakter" value={addForm.password}
                      onChange={(e) => setAddForm({ ...addForm, password: e.target.value })} />
                    <button className={styles.eyeBtn} onClick={() => setShowPwd(v => !v)}>
                      {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.cancelBtn} onClick={() => setShowAdd(false)}>Batal</button>
              <button className={styles.saveBtn} onClick={handleAddUser}><Check size={16} /> Simpan</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Edit User Modal ── */}
      {editUser && (
        <div className={styles.overlay} onClick={() => setEditUser(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3><Edit3 size={18} /> Edit Pengguna: {editUser.username}</h3>
              <button className={styles.closeBtn} onClick={() => setEditUser(null)}><X size={18} /></button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}><KeyRound size={14} /> Reset Password</label>
                  <span className={styles.fieldHint}>Kosongi jika tidak ingin mengubah</span>
                </div>
                <div className={styles.fieldRight}>
                  <div className={styles.pwdWrap}>
                    <input className={styles.input} type={showEditPwd ? 'text' : 'password'} placeholder="Password baru" value={editForm.password}
                      onChange={(e) => setEditForm({ ...editForm, password: e.target.value })} />
                    <button className={styles.eyeBtn} onClick={() => setShowEditPwd(v => !v)}>
                      {showEditPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
              </div>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}><Inbox size={14} /> Assign Mailbox</label>
                  <span className={styles.fieldHint}>
                    {editForm.assigned_mailbox ? `Saat ini: ${editForm.assigned_mailbox}` : 'Belum ada mailbox'}
                  </span>
                </div>
                <div className={styles.fieldRight}>
                  <select className={styles.select} value={editForm.assigned_mailbox}
                    onChange={(e) => setEditForm({ ...editForm, assigned_mailbox: e.target.value })}>
                    <option value="">— Tidak ada —</option>
                    {availableMailboxes.map((m) => (
                      <option key={m.id} value={m.email}>{m.email}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}>Status Akun</label>
                  <span className={styles.fieldHint}>{editUser.is_active ? 'Aktif' : 'Nonaktif'}</span>
                </div>
                <div className={styles.fieldRight}>
                  <button className={`${styles.statusBtn} ${editForm.is_active ? styles.statusActive : styles.statusInactive}`}
                    onClick={() => setEditForm({ ...editForm, is_active: !editForm.is_active })}>
                    {editForm.is_active ? 'Aktif' : 'Nonaktif'}
                  </button>
                </div>
              </div>
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.cancelBtn} onClick={() => setEditUser(null)}>Batal</button>
              <button className={styles.saveBtn} onClick={handleEditUser}
                disabled={!editForm.password && editForm.is_active === editUser.is_active && editForm.assigned_mailbox === (getAssignedMailbox(editUser.username)?.email || '')}>
                <Check size={16} /> Simpan Perubahan
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete Confirmation ── */}
      {deleteTarget && (
        <div className={styles.overlay} onClick={() => setDeleteTarget(null)}>
          <div className={`${styles.modal} ${styles.confirmModal}`} onClick={(e) => e.stopPropagation()}>
            <div className={styles.confirmIcon}>
              <AlertCircle size={32} />
            </div>
            <h3>Nonaktifkan Pengguna</h3>
            <p>Yakin ingin menonaktifkan pengguna <strong>{deleteTarget.username}</strong>?</p>
            <p className={styles.confirmHint}>Pengguna tidak akan bisa login sampai diaktifkan kembali.</p>
            <div className={styles.modalFooter} style={{ justifyContent: 'center' }}>
              <button className={styles.cancelBtn} onClick={() => setDeleteTarget(null)}>Batal</button>
              <button className={styles.deleteBtn} onClick={handleDeleteUser}>
                <Trash2 size={16} /> Nonaktifkan
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
