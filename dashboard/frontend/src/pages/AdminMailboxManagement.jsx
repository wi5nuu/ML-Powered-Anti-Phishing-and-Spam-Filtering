import { useState, useEffect } from 'react'
import api from '../api/client'
import {
  Mail, Plus, X, Check, Search, Filter,
  AtSign, User, Users, HardDrive, Shield,
  ChevronDown, ChevronUp, ExternalLink, AlertCircle,
  Edit3, Trash2, ToggleLeft, ToggleRight,
  KeyRound, Eye, EyeOff, Copy
} from 'lucide-react'
import styles from './AdminMailboxManagement.module.css'

export default function AdminMailboxManagement() {
  const [mailboxes, setMailboxes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [msg, setMsg] = useState('')
  const [msgType, setMsgType] = useState('success')
  const [sortBy, setSortBy] = useState('email')
  const [sortDir, setSortDir] = useState('asc')
  const [users, setUsers] = useState([])

  const [showAdd, setShowAdd] = useState(false)
  const [addForm, setAddForm] = useState({ email: '', domain: '', sender_name: '', password: '', assigned_to: '' })
  const [showAddPwd, setShowAddPwd] = useState(false)

  const [editTarget, setEditTarget] = useState(null)
  const [editForm, setEditForm] = useState({ sender_name: '', assigned_to: '' })

  const [pwdTarget, setPwdTarget] = useState(null)
  const [pwdValue, setPwdValue] = useState('')
  const [showPwd, setShowPwd] = useState(false)

  const [deleteTarget, setDeleteTarget] = useState(null)

  const fetchMailboxes = () => {
    setLoading(true)
    api.get('/admin/mailboxes')
      .then((r) => { setMailboxes(Array.isArray(r.data) ? r.data : []); setLoading(false) })
      .catch((err) => { setError(err.response?.data?.detail || err.message); setLoading(false) })
  }

  const fetchUsers = () => {
    api.get('/admin/users')
      .then((r) => { setUsers(Array.isArray(r.data) ? r.data : []) })
      .catch(() => {})
  }

  useEffect(() => { fetchMailboxes(); fetchUsers() }, [])

  const showMsg = (text, type = 'success') => {
    setMsg(text); setMsgType(type)
    setTimeout(() => setMsg(''), 5000)
  }

  const handleSort = (field) => {
    if (sortBy === field) { setSortDir(d => d === 'asc' ? 'desc' : 'asc') }
    else { setSortBy(field); setSortDir('asc') }
  }

  const sortIcon = (field) => {
    if (sortBy !== field) return null
    return sortDir === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
  }

  const handleAdd = async () => {
    if (!addForm.email || !addForm.password) return
    try {
      const email = `${addForm.email}${addForm.email.includes('@') ? '' : '@' + addForm.domain}`
      await api.post('/admin/mailboxes', {
        email,
        domain: addForm.domain,
        password: addForm.password,
        sender_name: addForm.sender_name,
        assigned_to: addForm.assigned_to,
      })
      showMsg('Mailbox berhasil dibuat')
      setShowAdd(false)
      setAddForm({ email: '', domain: '', sender_name: '', password: '', assigned_to: '' })
      fetchMailboxes()
    } catch (err) {
      showMsg(err.response?.data?.detail || 'Gagal membuat mailbox', 'error')
    }
  }

  const openEdit = (mb) => {
    setEditTarget(mb)
    setEditForm({ sender_name: mb.sender_name, assigned_to: mb.assigned_to || '' })
  }

  const handleEdit = async () => {
    if (!editTarget) return
    try {
      await api.put(`/admin/mailboxes/${editTarget.id}`, {
        sender_name: editForm.sender_name,
        assigned_to: editForm.assigned_to,
      })
      showMsg('Mailbox berhasil diperbarui')
      setEditTarget(null)
      fetchMailboxes()
    } catch (err) {
      showMsg(err.response?.data?.detail || 'Gagal memperbarui mailbox', 'error')
    }
  }

  const openPwd = (mb) => {
    setPwdTarget(mb)
    setPwdValue('')
    setShowPwd(false)
  }

  const handlePwd = async () => {
    if (!pwdTarget || pwdValue.length < 8) return
    try {
      await api.put(`/admin/mailboxes/${pwdTarget.id}/password`, { password: pwdValue })
      showMsg('Password berhasil diubah')
      setPwdTarget(null)
    } catch (err) {
      showMsg(err.response?.data?.detail || 'Gagal mengubah password', 'error')
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/admin/mailboxes/${deleteTarget.id}`)
      showMsg('Mailbox dinonaktifkan')
      setDeleteTarget(null)
      fetchMailboxes()
    } catch (err) {
      showMsg(err.response?.data?.detail || 'Gagal menonaktifkan mailbox', 'error')
    }
  }

  const handleToggleActive = async (mb) => {
    try {
      await api.put(`/admin/mailboxes/${mb.id}`, { is_active: !mb.is_active })
      showMsg(mb.is_active ? 'Mailbox dinonaktifkan' : 'Mailbox diaktifkan')
      fetchMailboxes()
    } catch (err) {
      showMsg(err.response?.data?.detail || 'Gagal mengubah status', 'error')
    }
  }

  const openWebmail = (mb) => {
    window.open(`/mail/${mb.id}/inbox`, '_blank', 'noopener')
  }

  const filtered = mailboxes.filter((mb) => {
    const q = search.toLowerCase()
    if (q && !mb.email.toLowerCase().includes(q) && !(mb.sender_name || '').toLowerCase().includes(q) && !(mb.assigned_to || '').toLowerCase().includes(q)) return false
    if (statusFilter === 'active' && !mb.is_active) return false
    if (statusFilter === 'inactive' && mb.is_active) return false
    return true
  })

  const sorted = [...filtered].sort((a, b) => {
    let cmp = 0
    const aVal = (a[sortBy] || '').toString().toLowerCase()
    const bVal = (b[sortBy] || '').toString().toLowerCase()
    if (sortBy === 'storage_bytes') {
      cmp = (a.storage_bytes || 0) - (b.storage_bytes || 0)
    } else {
      cmp = aVal.localeCompare(bVal)
    }
    return sortDir === 'asc' ? cmp : -cmp
  })

  const formatStorage = (bytes) => {
    if (!bytes) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB']
    let i = 0
    let val = bytes
    while (val >= 1024 && i < units.length - 1) { val /= 1024; i++ }
    return `${val.toFixed(1)} ${units[i]}`
  }

  const pwdChecks = {
    length: pwdValue.length >= 8,
    number: /\d/.test(pwdValue),
    symbol: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(pwdValue),
    lower: /[a-z]/.test(pwdValue),
    upper: /[A-Z]/.test(pwdValue),
  }
  const pwdValid = Object.values(pwdChecks).every(Boolean)

  const addPwdChecks = {
    length: addForm.password.length >= 8,
    number: /\d/.test(addForm.password),
    symbol: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(addForm.password),
    lower: /[a-z]/.test(addForm.password),
    upper: /[A-Z]/.test(addForm.password),
  }
  const addPwdValid = Object.values(addPwdChecks).every(Boolean)

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.loadingState}>
          <div className={styles.spinner} />
          <span>Memuat mailbox...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.page}>
        <div className={styles.errorState}>
          <AlertCircle size={28} />
          <h3>Gagal memuat data</h3>
          <p>{error}</p>
          <button className={styles.retryBtn} onClick={fetchMailboxes}>Coba Lagi</button>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h2 className={styles.title}>
            <Mail size={20} />
            Mailbox Management
          </h2>
          <p className={styles.subtitle}>
            {mailboxes.filter(m => m.is_active).length} aktif · {mailboxes.filter(m => !m.is_active).length} nonaktif
          </p>
        </div>
        <button className={styles.addBtn} onClick={() => setShowAdd(true)}>
          <Plus size={16} /> Add Mailbox
        </button>
      </div>

      {msg && (
        <div className={`${styles.msg} ${msgType === 'success' ? styles.msgSuccess : styles.msgError}`}>
          {msgType === 'success' ? <Check size={16} /> : <AlertCircle size={16} />}
          {msg}
        </div>
      )}

      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <Search size={16} className={styles.searchIcon} />
          <input className={styles.searchInput} placeholder="Cari email, sender name, atau assigned to..." value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className={styles.filterGroup}>
          <Filter size={15} className={styles.filterIcon} />
          {['all', 'active', 'inactive'].map((s) => (
            <button
              key={s}
              className={`${styles.filterChip} ${statusFilter === s ? styles.filterChipActive : ''}`}
              style={statusFilter === s ? { background: '#7C3AED', color: '#fff', borderColor: '#7C3AED' } : {}}
              onClick={() => setStatusFilter(s)}
            >
              {s === 'all' ? 'Semua' : s === 'active' ? 'Aktif' : 'Nonaktif'}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th><button className={styles.sortable} onClick={() => handleSort('email')}>Email {sortIcon('email')}</button></th>
              <th><button className={styles.sortable} onClick={() => handleSort('domain')}>Domain {sortIcon('domain')}</button></th>
              <th><button className={styles.sortable} onClick={() => handleSort('sender_name')}>Sender Name {sortIcon('sender_name')}</button></th>
              <th><button className={styles.sortable} onClick={() => handleSort('assigned_to')}>Assigned To {sortIcon('assigned_to')}</button></th>
              <th>Status</th>
              <th><button className={styles.sortable} onClick={() => handleSort('storage_bytes')}>Storage {sortIcon('storage_bytes')}</button></th>
              <th>Aksi</th>
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr><td colSpan={7} className={styles.emptyRow}>Tidak ada mailbox ditemukan</td></tr>
            ) : sorted.map((mb) => (
              <tr key={mb.id}>
                <td>
                  <div className={styles.emailCell}>
                    <div className={styles.avatarSmall} style={{ background: mb.is_active ? '#ECFDF5' : '#F3F4F6' }}>
                      <Mail size={14} color={mb.is_active ? '#059669' : '#9CA3AF'} />
                    </div>
                    <div className={styles.emailInfo}>
                      <strong>{mb.email}</strong>
                      <span>ID: {mb.id}</span>
                    </div>
                    <button className={styles.copyBtn} onClick={() => navigator.clipboard?.writeText(mb.email)} title="Salin email">
                      <Copy size={13} />
                    </button>
                  </div>
                </td>
                <td className={styles.mono}>@{mb.domain}</td>
                <td>{mb.sender_name || <span className={styles.muted}>-</span>}</td>
                <td>
                  {mb.assigned_to ? (
                    <span className={styles.assignBadge}><User size={12} /> {mb.assigned_to}</span>
                  ) : (
                    <span className={styles.muted}>-</span>
                  )}
                </td>
                <td>
                  <span className={`${styles.statusDot} ${mb.is_active ? styles.active : styles.inactive}`} />
                  {mb.is_active ? 'Aktif' : 'Nonaktif'}
                </td>
                <td>
                  <div className={styles.storageCell}>
                    <HardDrive size={13} />
                    <span>{formatStorage(mb.storage_bytes)}</span>
                    <div className={styles.storageBar}>
                      <div className={styles.storageFill} style={{ width: `${Math.min((mb.storage_bytes || 0) / (500 * 1024 * 1024) * 100, 100)}%` }} />
                    </div>
                  </div>
                </td>
                <td>
                  <div className={styles.actionGroup}>
                    <button className={styles.actionBtn} onClick={() => openWebmail(mb)} title="Buka Webmail">
                      <ExternalLink size={15} />
                    </button>
                    <button className={styles.actionBtn} onClick={() => openEdit(mb)} title="Edit">
                      <Edit3 size={15} />
                    </button>
                    <button className={styles.actionBtn} onClick={() => openPwd(mb)} title="Ubah Password">
                      <KeyRound size={15} />
                    </button>
                    <button
                      className={`${styles.actionBtn} ${!mb.is_active ? styles.actionSuccess : styles.actionDanger}`}
                      onClick={() => handleToggleActive(mb)}
                      title={mb.is_active ? 'Nonaktifkan' : 'Aktifkan'}
                    >
                      {mb.is_active ? <ToggleRight size={15} /> : <ToggleLeft size={15} />}
                    </button>
                    <button className={`${styles.actionBtn} ${styles.actionDanger}`} onClick={() => setDeleteTarget(mb)} title="Hapus">
                      <Trash2 size={15} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showAdd && (
        <div className={styles.overlay} onClick={() => setShowAdd(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3><Plus size={18} /> Add Mailbox</h3>
              <button className={styles.closeBtn} onClick={() => setShowAdd(false)}><X size={20} /></button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}><AtSign size={14} /> Email</label>
                </div>
                <div className={styles.fieldRight}>
                  <div className={styles.splitInput}>
                    <input className={styles.input} placeholder="username" value={addForm.email} onChange={(e) => setAddForm(f => ({ ...f, email: e.target.value }))} autoFocus />
                    <span className={styles.splitSep}>@</span>
                    <input className={styles.input} placeholder="domain.com" value={addForm.domain} onChange={(e) => setAddForm(f => ({ ...f, domain: e.target.value }))} />
                  </div>
                </div>
              </div>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}><User size={14} /> Sender Name</label>
                </div>
                <div className={styles.fieldRight}>
                  <input className={styles.input} placeholder="Opsional" value={addForm.sender_name} onChange={(e) => setAddForm(f => ({ ...f, sender_name: e.target.value }))} />
                </div>
              </div>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}><Users size={14} /> Assign To</label>
                </div>
                <div className={styles.fieldRight}>
                  <select className={styles.select} value={addForm.assigned_to} onChange={(e) => setAddForm(f => ({ ...f, assigned_to: e.target.value }))}>
                    <option value="">Tidak ada</option>
                    {users.map((u) => (
                      <option key={u.username} value={u.username}>{u.username} ({u.role})</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}><KeyRound size={14} /> Password</label>
                  <span className={styles.fieldHint}>Min. 8 karakter</span>
                </div>
                <div className={styles.fieldRight}>
                  <div className={styles.pwdWrap}>
                    <input className={styles.input} type={showAddPwd ? 'text' : 'password'} placeholder="Password" value={addForm.password} onChange={(e) => setAddForm(f => ({ ...f, password: e.target.value }))} />
                    <button className={styles.eyeBtn} onClick={() => setShowAddPwd(v => !v)}>{showAddPwd ? <EyeOff size={16} /> : <Eye size={16} />}</button>
                  </div>
                  <div className={styles.pwdRules}>
                    {Object.entries({ number: 'Angka', symbol: 'Simbol', lower: 'Huruf kecil', upper: 'Huruf kapital', length: '8 karakter' }).map(([k, v]) => (
                      <span key={k} className={addPwdChecks[k] ? styles.ruleOk : ''}>{v}</span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.cancelBtn} onClick={() => setShowAdd(false)}>Batal</button>
              <button className={styles.saveBtn} disabled={!addForm.email || !addForm.password || !addPwdValid} onClick={handleAdd}>
                <Check size={16} /> Create
              </button>
            </div>
          </div>
        </div>
      )}

      {editTarget && (
        <div className={styles.overlay} onClick={() => setEditTarget(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3><Edit3 size={18} /> Edit Mailbox</h3>
              <button className={styles.closeBtn} onClick={() => setEditTarget(null)}><X size={20} /></button>
            </div>
            <div className={styles.modalBody}>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: '0 0 8px' }}>
                <strong style={{ color: 'var(--text)' }}>{editTarget.email}</strong>
              </p>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}><User size={14} /> Sender Name</label>
                </div>
                <div className={styles.fieldRight}>
                  <input className={styles.input} value={editForm.sender_name} onChange={(e) => setEditForm(f => ({ ...f, sender_name: e.target.value }))} />
                </div>
              </div>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}><Users size={14} /> Assign To</label>
                </div>
                <div className={styles.fieldRight}>
                  <select className={styles.select} value={editForm.assigned_to} onChange={(e) => setEditForm(f => ({ ...f, assigned_to: e.target.value }))}>
                    <option value="">Tidak ada</option>
                    {users.map((u) => (
                      <option key={u.username} value={u.username}>{u.username} ({u.role})</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.cancelBtn} onClick={() => setEditTarget(null)}>Batal</button>
              <button className={styles.saveBtn} onClick={handleEdit}>
                <Check size={16} /> Simpan
              </button>
            </div>
          </div>
        </div>
      )}

      {pwdTarget && (
        <div className={styles.overlay} onClick={() => setPwdTarget(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3><KeyRound size={18} /> Ubah Password</h3>
              <button className={styles.closeBtn} onClick={() => setPwdTarget(null)}><X size={20} /></button>
            </div>
            <div className={styles.modalBody}>
              <p className={styles.pwdTargetLabel}>{pwdTarget.email}</p>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}><KeyRound size={14} /> Password Baru</label>
                  <span className={styles.fieldHint}>Min. 8 karakter</span>
                </div>
                <div className={styles.fieldRight}>
                  <div className={styles.pwdWrap}>
                    <input className={styles.input} type={showPwd ? 'text' : 'password'} placeholder="Password baru" value={pwdValue} onChange={(e) => setPwdValue(e.target.value)} autoFocus />
                    <button className={styles.eyeBtn} onClick={() => setShowPwd(v => !v)}>{showPwd ? <EyeOff size={16} /> : <Eye size={16} />}</button>
                  </div>
                  <div className={styles.pwdRules}>
                    {Object.entries({ number: 'Angka', symbol: 'Simbol', lower: 'Huruf kecil', upper: 'Huruf kapital', length: '8 karakter' }).map(([k, v]) => (
                      <span key={k} className={pwdChecks[k] ? styles.ruleOk : ''}>{v}</span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.cancelBtn} onClick={() => setPwdTarget(null)}>Batal</button>
              <button className={styles.saveBtn} disabled={!pwdValid} onClick={handlePwd}>
                <Check size={16} /> Update
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteTarget && (
        <div className={styles.overlay} onClick={() => setDeleteTarget(null)}>
          <div className={`${styles.modal} ${styles.confirmModal}`} onClick={(e) => e.stopPropagation()}>
            <AlertCircle size={36} className={styles.confirmIcon} />
            <h3>Nonaktifkan mailbox?</h3>
            <p>Mailbox <strong>{deleteTarget.email}</strong> akan dinonaktifkan dan tidak bisa login lagi. Data email tetap tersimpan.</p>
            <div className={styles.modalFooter}>
              <button className={styles.cancelBtn} onClick={() => setDeleteTarget(null)}>Batal</button>
              <button className={styles.deleteBtn} onClick={handleDelete}>
                <Trash2 size={16} /> Nonaktifkan
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
