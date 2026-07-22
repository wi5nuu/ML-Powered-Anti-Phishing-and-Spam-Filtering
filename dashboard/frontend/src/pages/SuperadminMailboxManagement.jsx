import { useEffect, useState } from 'react'
import { useTranslation } from '../i18n/context'
import api from '../api/client'
import {
  Users, Shield, RefreshCw, AlertCircle, Search,
  KeyRound, X, Eye, EyeOff, Copy, CheckCircle, ExternalLink, Inbox,
  Mail, ToggleLeft, ToggleRight, ArrowRight
} from 'lucide-react'
import styles from './AdminPage.module.css'

const PWD_EMPTY = { password: '', confirm: '' }

export default function SuperadminMailboxManagement() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState('users')

  const validatePassword = (pw) => {
    if (pw.length < 8)               return 'Password minimal 8 karakter.'
    if (!/[A-Z]/.test(pw))           return 'Password harus mengandung huruf besar.'
    if (!/[a-z]/.test(pw))           return 'Password harus mengandung huruf kecil.'
    if (!/[0-9]/.test(pw))           return 'Password harus mengandung angka.'
    if (!/[^A-Za-z0-9]/.test(pw))    return 'Password harus mengandung karakter spesial (contoh: !@#$%).'
    return null
  }

  // Data states
  const [users, setUsers] = useState([])
  const [admins, setAdmins] = useState([])
  const [usersLoading, setUsersLoading] = useState(false)
  const [adminsLoading, setAdminsLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [search, setSearch] = useState('')
  const [saving, setSaving] = useState(false)

  // Modal
  const [modal, setModal] = useState(null)
  const [pwdForm, setPwdForm] = useState(PWD_EMPTY)
  const [pwdShown, setPwdShown] = useState(null)
  const [pwdVisible, setPwdVisible] = useState(false)
  const [forwardEdit, setForwardEdit] = useState(null)
  const [forwardForm, setForwardForm] = useState({ forward_to: '', forward_enabled: false, forward_keep_copy: true })

  const openForwardEdit = (u) => {
    setForwardEdit(u)
    setForwardForm({
      forward_to: u.forward_to || '',
      forward_enabled: u.forward_enabled || false,
      forward_keep_copy: u.forward_keep_copy !== false,
    })
  }
  const closeForwardEdit = () => setForwardEdit(null)

  const goWebmail = (mbId) => {
    window.open(`/mail/${encodeURIComponent(mbId)}/login`, '_blank', 'noopener,noreferrer')
  }
  const goWebmailAuto = async (mbId) => {
    try {
      const { data } = await api.post(`/admin/mailboxes/${mbId}/autologin-token`)
      window.open(`/mail/${encodeURIComponent(mbId)}/login?autotoken=${encodeURIComponent(data.token)}`, '_blank', 'noopener,noreferrer')
    } catch {
      goWebmail(mbId)
    }
  }
  const goAdminAuto = async (adminUsername) => {
    try {
      const { data } = await api.post(`/admin/admins/${adminUsername}/autologin-token`)
      window.open(`/admin?tab=overview&autotoken=${encodeURIComponent(data.token)}&admin=${encodeURIComponent(data.admin_username)}`, '_blank', 'noopener,noreferrer')
    } catch {
      window.open('/admin', '_blank', 'noopener,noreferrer')
    }
  }
  const flash = (msg) => { setSuccess(msg); setTimeout(() => setSuccess(''), 3500) }

  const saveForward = async () => {
    if (!forwardEdit) return
    if (forwardForm.forward_enabled && !forwardForm.forward_to) {
      setError('Email tujuan forward harus diisi jika forward diaktifkan.')
      return
    }
    setSaving(true); setError('')
    try {
      const res = await api.put(`/admin/users/${forwardEdit.username}/forward`, {
        forward_to: forwardForm.forward_to,
        forward_enabled: forwardForm.forward_enabled,
        forward_keep_copy: forwardForm.forward_keep_copy,
      })
      setUsers(prev => prev.map(u => u.username === forwardEdit.username
        ? { ...u, forward_to: res.data.forward_to, forward_enabled: res.data.forward_enabled, forward_keep_copy: res.data.forward_keep_copy }
        : u))
      flash('Pengaturan forward berhasil disimpan!')
      setForwardEdit(null)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Gagal menyimpan pengaturan forward.')
    } finally { setSaving(false) }
  }

  const fetchUsers = () => {
    setUsersLoading(true); setError('')
    api.get('/admin/list-users-with-admin')
      .then(({ data }) => setUsers(Array.isArray(data) ? data : []))
      .catch((e) => { setUsers([]); setError(e?.response?.data?.detail || 'Gagal memuat daftar pengguna.') })
      .finally(() => setUsersLoading(false))
  }
  const fetchAdmins = () => {
    setAdminsLoading(true); setError('')
    api.get('/admin/list-admins-with-stats')
      .then(({ data }) => setAdmins(Array.isArray(data) ? data : []))
      .catch((e) => { setAdmins([]); setError(e?.response?.data?.detail || 'Gagal memuat daftar admin.') })
      .finally(() => setAdminsLoading(false))
  }

  useEffect(() => { if (activeTab === 'users') fetchUsers() }, [activeTab])
  useEffect(() => { if (activeTab === 'admins') fetchAdmins() }, [activeTab])

  const closeModal = () => { setModal(null); setError(''); setSaving(false) }

  // ── Actions ──────────────────────────────────────────────

  const openUserPwd = (user) => {
    setPwdForm(PWD_EMPTY)
    setModal({ type: 'userPwd', user })
  }

  const handleUserChangePwd = () => {
    const pwErr = validatePassword(pwdForm.password)
    if (pwErr) { setError(pwErr); return }
    if (pwdForm.password !== pwdForm.confirm) { setError('Konfirmasi password tidak cocok.'); return }
    setSaving(true); setError('')
    api.put(`/admin/users/${modal.user.username}`, { password: pwdForm.password })
      .then(() => {
        navigator.clipboard.writeText(pwdForm.password).catch(() => {})
        closeModal()
        flash('Password berhasil diubah dan disalin ke clipboard.')
      })
      .catch((e) => setError(e.response?.data?.detail || 'Gagal mengubah password.'))
      .finally(() => setSaving(false))
  }

  // ── Filters ──────────────────────────────────────────────

  const filteredUsers = users.filter(u =>
    !search.trim() ||
    u.username.toLowerCase().includes(search.toLowerCase()) ||
    (u.email || '').toLowerCase().includes(search.toLowerCase())
  )
  const filteredAdmins = admins.filter(a =>
    !search.trim() ||
    a.username.toLowerCase().includes(search.toLowerCase()) ||
    (a.email || '').toLowerCase().includes(search.toLowerCase())
  )

  const isUserPwd = modal?.type === 'userPwd'

  const ErrorBanner = () => error ? (
    <div style={{ marginBottom: 12, padding: '8px 12px', background: '#fce8e6', color: '#c5221f', borderRadius: 6, fontSize: '0.8125rem', display: 'flex', alignItems: 'center', gap: 8 }}>
      <AlertCircle size={13} /> {error}
    </div>
  ) : null

  return (
    <>
    <div className={`${styles.section} ${styles.mailboxSection}`}>
      <div className={styles.sectionHeader}>
        <div className={styles.sectionTitle}>
          <Users size={16} />
          <div>
            <strong>User & Admin Management</strong>
            <span>{activeTab === 'users' ? users.length + ' user terdaftar' : admins.length + ' admin terdaftar'}</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              className={styles.searchInput}
              style={{ paddingLeft: 28 }}
              placeholder="Cari nama atau email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <button onClick={activeTab === 'users' ? fetchUsers : fetchAdmins} disabled={usersLoading || adminsLoading} className={styles.actionBtn}><RefreshCw size={13} /></button>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', marginBottom: 16 }}>
        {['users', 'admins'].map((tab) => (
          <button
            key={tab}
            onClick={() => { setActiveTab(tab); setSearch('') }}
            style={{
              padding: '8px 18px', border: 'none', background: 'transparent', cursor: 'pointer',
              fontSize: '0.85rem', fontWeight: activeTab === tab ? 600 : 400,
              color: activeTab === tab ? '#1a73e8' : 'var(--text-muted)',
              borderBottom: activeTab === tab ? '2px solid #1a73e8' : '2px solid transparent',
              transition: 'all 0.15s', textTransform: 'uppercase', letterSpacing: '0.3px',
            }}
          >
            {tab === 'users' ? '👤 Users' : '🛡️ Admins'}
          </button>
        ))}
      </div>

      {success && (
        <div style={{ margin: '0 0 12px', padding: '8px 14px', background: '#f0fdf4', color: '#166534', borderRadius: 6, fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 6 }}>
          <CheckCircle size={14} /> {success}
        </div>
      )}
      {error && !modal && (
        <div style={{ margin: '0 0 12px', padding: '8px 14px', background: '#fce8e6', color: '#c5221f', borderRadius: 6, fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertCircle size={13} /> {error}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════
         TAB: USERS
         ═══════════════════════════════════════════════════════ */}
      {activeTab === 'users' && (
        usersLoading ? (
          <div className={styles.emptyState}>Memuat users...</div>
        ) : filteredUsers.length === 0 ? (
          <div className={styles.emptyState}>Tidak ada user ditemukan.</div>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Username</th>
                <th>Email</th>
                <th>Organisasi</th>
                <th>Admin</th>
                <th>Forward</th>
                <th style={{ textAlign: 'right' }}>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u) => (
                <tr key={u.username}>
                  <td style={{ fontWeight: 500 }}>{u.username}</td>
                  <td>{u.email || <span style={{ color: 'var(--text-muted)' }}>-</span>}</td>
                  <td>{u.organization || <span style={{ color: 'var(--text-muted)' }}>-</span>}</td>
                  <td>
                    {u.admins && u.admins.length > 0
                      ? u.admins.map((a) => (
                          <span key={a} style={{
                            display: 'inline-block', padding: '2px 8px', margin: '1px 3px',
                            background: '#e8f0fe', color: '#1a73e8', borderRadius: 10,
                            fontSize: '0.78rem', fontWeight: 500,
                          }}>{a}</span>
                        ))
                      : <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>Tidak ada admin</span>}
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {u.forward_enabled
                        ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, padding: '2px 7px', background: '#e6f4ea', color: '#1e7e34', borderRadius: 10, fontSize: '0.72rem', fontWeight: 600 }}>● Aktif</span>
                        : <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, padding: '2px 7px', background: '#f1f3f4', color: 'var(--text-muted)', borderRadius: 10, fontSize: '0.72rem' }}>○ Nonaktif</span>
                      }
                      <span style={{ fontSize: '0.78rem', color: u.forward_to ? 'inherit' : 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 140 }}>
                        {u.forward_to || 'Belum diatur'}
                      </span>
                      <button
                        onClick={() => openForwardEdit(u)}
                        className={styles.actionBtn}
                        title="Atur forward"
                        style={{ color: '#1a73e8', flexShrink: 0 }}
                      >
                        <ExternalLink size={12} />
                      </button>
                    </div>
                  </td>
                  <td>
                    <div className={styles.actionGroup} style={{ justifyContent: 'flex-end' }}>
                      {u.email && (
                        <button
                          onClick={() => window.open(`/mailbox-login?email=${encodeURIComponent(u.email)}`, '_blank')}
                          className={styles.actionBtn}
                          title="Login ke mailbox user"
                          style={{ color: '#2563EB' }}
                        >
                          <Inbox size={13} />
                        </button>
                      )}
                      <button onClick={() => openUserPwd(u)} className={styles.actionBtn} title="Show & Copy Password" style={{ color: '#1a73e8' }}>
                        <Eye size={13} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}

      {/* ═══════════════════════════════════════════════════════
         TAB: ADMINS
         ═══════════════════════════════════════════════════════ */}
      {activeTab === 'admins' && (
        adminsLoading ? (
          <div className={styles.emptyState}>Memuat admin...</div>
        ) : filteredAdmins.length === 0 ? (
          <div className={styles.emptyState}>Tidak ada admin ditemukan.</div>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Username</th>
                <th>Email</th>
                <th>Organisasi</th>
                <th>Mailbox</th>
                <th>User Dikelola</th>
                <th style={{ textAlign: 'right' }}>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {filteredAdmins.map((a) => (
                <tr key={a.username}>
                  <td style={{ fontWeight: 500 }}>{a.username}</td>
                  <td>{a.email || <span style={{ color: 'var(--text-muted)' }}>-</span>}</td>
                  <td>{a.organization || <span style={{ color: 'var(--text-muted)' }}>Global</span>}</td>
                  <td>
                    <span style={{ fontSize: '0.78rem' }}>
                      {a.email || <span style={{ color: 'var(--text-muted)' }}>-</span>}
                      <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>
                        ({a.mailboxes ? a.mailboxes.length : 0} mailboxes)
                      </span>
                    </span>
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>{a.user_count}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 2 }}>
                      {a.email_count ?? 0} email
                    </div>
                  </td>
                  <td>
                    <div className={styles.actionGroup} style={{ justifyContent: 'flex-end' }}>
                      {a.email && (
                        <button
                          onClick={() => window.open(`/mailbox-login?email=${encodeURIComponent(a.email)}`, '_blank')}
                          className={styles.actionBtn}
                          title="Login ke mailbox admin"
                          style={{ color: '#2563EB' }}
                        >
                          <Inbox size={13} />
                        </button>
                      )}
                      <button
                        onClick={() => goAdminAuto(a.username)}
                        className={styles.actionBtn}
                        title="Login as Admin (dashboard)"
                        style={{ color: '#059669' }}
                      >
                        <Shield size={13} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}
    </div>

    {/* ── MODAL: Ganti Password User ── */}
    {isUserPwd && (
      <div className={styles.overlay} onClick={closeModal}>
        <div className={styles.editModal} onClick={(e) => e.stopPropagation()}>
          <div className={styles.editModalHeader}>
            <h3><KeyRound size={16} /> Ganti Password — {modal.user.username}</h3>
            <button className={styles.modalCloseBtn} onClick={closeModal}><X size={16} /></button>
          </div>
          <div className={styles.editModalBody}>
            <ErrorBanner />

            {/* Info user */}
            <div style={{ marginBottom: 16, padding: 12, background: 'var(--bg)', borderRadius: 8, fontSize: '0.85rem' }}>
              <div style={{ marginBottom: 6 }}><strong>User:</strong> {modal.user.username}</div>
              <div style={{ marginBottom: 6 }}><strong>Email:</strong> {modal.user.email || '-'}</div>
              <div style={{ marginBottom: 6 }}><strong>Organisasi:</strong> {modal.user.organization || '-'}</div>
              <div>
                <strong>Admin:</strong>{' '}
                {modal.user.admins && modal.user.admins.length > 0
                  ? modal.user.admins.join(', ')
                  : <span style={{ color: 'var(--text-muted)' }}>-</span>}
              </div>
            </div>

            <div className={styles.fieldRow}>
              <div className={styles.fieldLeft}><span className={styles.fieldLabel}>Password Baru</span></div>
              <div className={styles.fieldRight}>
                <input className={styles.input} type="password" value={pwdForm.password}
                  onChange={(e) => setPwdForm(f => ({ ...f, password: e.target.value }))}
                  placeholder="Min. 8 karakter" autoComplete="new-password" />
              </div>
            </div>
            <div className={styles.fieldRow}>
              <div className={styles.fieldLeft}><span className={styles.fieldLabel}>Konfirmasi</span></div>
              <div className={styles.fieldRight}>
                <input className={styles.input} type="password" value={pwdForm.confirm}
                  onChange={(e) => setPwdForm(f => ({ ...f, confirm: e.target.value }))}
                  placeholder="Ulangi password" autoComplete="new-password" />
              </div>
            </div>
          </div>
          <div className={styles.editModalFooter}>
            <button onClick={closeModal} className={styles.cancelBtn}>Batal</button>
            <button onClick={handleUserChangePwd} disabled={saving} className={styles.saveBtn}>
              {saving ? 'Menyimpan...' : 'Simpan Password'}
            </button>
          </div>
        </div>
      </div>
    )}

    {/* ── MODAL: Tampilkan Password ── */}
    {pwdShown && (
      <div className={styles.overlay} onClick={() => setPwdShown(null)}>
        <div className={styles.editModal} onClick={(e) => e.stopPropagation()}>
          <div className={styles.editModalHeader}>
            <h3><Eye size={16} /> Password Baru — {pwdShown.username}</h3>
            <button className={styles.modalCloseBtn} onClick={() => setPwdShown(null)}><X size={16} /></button>
          </div>
          <div className={styles.editModalBody}>
            <p style={{ margin: '0 0 12px', fontSize: '0.8125rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
              Simpan password ini sekarang. Password tidak bisa ditampilkan lagi setelah modal ini ditutup.
            </p>
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Username</span>
              <div style={{ padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.875rem', fontWeight: 600, marginBottom: 10 }}>
                {pwdShown.username}
              </div>
            </div>
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Password</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ flex: 1, padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.875rem', fontFamily: 'monospace', letterSpacing: pwdVisible ? 0 : 2 }}>
                  {pwdVisible ? pwdShown.password : '•'.repeat(pwdShown.password.length)}
                </div>
                <button onClick={() => setPwdVisible(v => !v)} className={styles.actionBtn} title={pwdVisible ? 'Sembunyikan' : 'Tampilkan'} style={{ flexShrink: 0 }}>
                  {pwdVisible ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
                <button onClick={() => { navigator.clipboard.writeText(pwdShown.password); flash('Password disalin!') }} className={styles.actionBtn} title="Salin password" style={{ flexShrink: 0 }}>
                  <Copy size={14} />
                </button>
              </div>
            </div>
          </div>
          <div className={styles.editModalFooter}>
            <button onClick={() => setPwdShown(null)} className={styles.saveBtn}>Tutup</button>
          </div>
        </div>
      </div>
        )}

    {/* ── Forward Setting Modal ── */}
    {forwardEdit && (
      <div className={styles.editModalOverlay} onClick={closeForwardEdit}>
        <div className={styles.editModal} onClick={e => e.stopPropagation()} style={{ maxWidth: 480, width: '100%' }}>
          <div className={styles.editModalHeader}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Mail size={16} style={{ color: '#1a73e8' }} />
              <span>Pengaturan Forward Email</span>
            </div>
            <button onClick={closeForwardEdit} className={styles.closeBtn}><X size={16} /></button>
          </div>

          {/* User info */}
          <div style={{ padding: '12px 20px', background: '#f8f9fa', borderBottom: '1px solid var(--border)', fontSize: '0.82rem' }}>
            <div style={{ display: 'flex', gap: 16 }}>
              <div><span style={{ color: 'var(--text-muted)' }}>User:</span> <strong>{forwardEdit.username}</strong></div>
              <div><span style={{ color: 'var(--text-muted)' }}>Email:</span> {forwardEdit.email || '-'}</div>
              <div><span style={{ color: 'var(--text-muted)' }}>Org:</span> {forwardEdit.organization || '-'}</div>
            </div>
          </div>

          <div className={styles.editModalBody} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>

            {/* Aktifkan forward toggle */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 14px', background: forwardForm.forward_enabled ? '#e6f4ea' : '#f1f3f4', borderRadius: 8, cursor: 'pointer' }}
              onClick={() => setForwardForm(f => ({ ...f, forward_enabled: !f.forward_enabled }))}>
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>Aktifkan Forward</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>
                  Email bersih yang masuk akan diteruskan ke alamat tujuan
                </div>
              </div>
              {forwardForm.forward_enabled
                ? <ToggleRight size={28} style={{ color: '#1e7e34', flexShrink: 0 }} />
                : <ToggleLeft size={28} style={{ color: '#999', flexShrink: 0 }} />
              }
            </div>

            {/* Email tujuan */}
            <div>
              <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                Email Tujuan Forward <span style={{ color: '#c5221f' }}>*</span>
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{forwardEdit.email || forwardEdit.username}</span>
                <ArrowRight size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                <input
                  type="email"
                  value={forwardForm.forward_to}
                  onChange={e => setForwardForm(f => ({ ...f, forward_to: e.target.value }))}
                  placeholder="tujuan@domain.com"
                  className={styles.input}
                  style={{ flex: 1 }}
                  disabled={!forwardForm.forward_enabled}
                  onKeyDown={e => e.key === 'Enter' && saveForward()}
                  autoFocus
                />
              </div>
              {!forwardForm.forward_enabled && (
                <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 4 }}>Aktifkan forward terlebih dahulu untuk mengatur alamat tujuan.</p>
              )}
            </div>

            {/* Keep copy toggle */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: '#f8f9fa', borderRadius: 8, cursor: forwardForm.forward_enabled ? 'pointer' : 'not-allowed', opacity: forwardForm.forward_enabled ? 1 : 0.5 }}
              onClick={() => forwardForm.forward_enabled && setForwardForm(f => ({ ...f, forward_keep_copy: !f.forward_keep_copy }))}>
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>Simpan Salinan di Mailbox</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>
                  Email tetap tersimpan di mailbox user meskipun sudah diteruskan
                </div>
              </div>
              {forwardForm.forward_keep_copy
                ? <ToggleRight size={24} style={{ color: '#1a73e8', flexShrink: 0 }} />
                : <ToggleLeft size={24} style={{ color: '#999', flexShrink: 0 }} />
              }
            </div>

            {/* Summary */}
            {forwardForm.forward_enabled && forwardForm.forward_to && (
              <div style={{ padding: '10px 14px', background: '#e8f0fe', borderRadius: 8, fontSize: '0.78rem', color: '#1a73e8' }}>
                <strong>Ringkasan:</strong> Email masuk ke <strong>{forwardEdit.email || forwardEdit.username}</strong> akan diteruskan ke <strong>{forwardForm.forward_to}</strong>
                {forwardForm.forward_keep_copy ? ' dan salinan tetap disimpan di mailbox.' : ' tanpa menyimpan salinan.'}
              </div>
            )}

            {error && <div style={{ padding: '8px 12px', background: '#fce8e6', color: '#c5221f', borderRadius: 6, fontSize: '0.82rem' }}>{error}</div>}
          </div>

          <div className={styles.editModalFooter}>
            <button onClick={closeForwardEdit} className={styles.cancelBtn} disabled={saving}>Batal</button>
            <button onClick={saveForward} className={styles.saveBtn} disabled={saving}>
              {saving ? 'Menyimpan...' : 'Simpan Pengaturan'}
            </button>
          </div>
        </div>
      </div>
    )}
    </>


  )
}
