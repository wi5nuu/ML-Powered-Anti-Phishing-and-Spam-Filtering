import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import api from '../api/client'
import { Users, RefreshCw, AlertCircle, Plus, Pencil, Trash2, X, Eye, EyeOff, Search, ChevronDown, ChevronRight, Mail, Shield, Building, CheckCircle } from 'lucide-react'
import { useTranslation } from '../i18n/context'
import styles from './AdminPage.module.css'

const ROLE_COLORS = {
  superadmin: { bg: '#F3E8FF', color: '#7C3AED' },
  admin:      { bg: '#EFF6FF', color: '#2563EB' },
  user:       { bg: '#F0FDF4', color: '#16A34A' },
}

const EMPTY_FORM = { username: '', email: '', password: '', role: 'user', is_active: true, organization_id: '' }

export default function SuperadminUserManagement() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const [users,   setUsers]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')
  const [success, setSuccess] = useState('')
  const [modal,   setModal]   = useState(null)
  const [form,    setForm]    = useState(EMPTY_FORM)
  const [saving,  setSaving]  = useState(false)
  const [showPw,  setShowPw]  = useState(false)
  const [search,  setSearch]  = useState(() => searchParams.get('q') || '')
  const [roleFilter, setRoleFilter] = useState('all')
  const [expandedAdmin, setExpandedAdmin] = useState(null)
  const [organizations, setOrganizations] = useState([])

  const fetchUsers = () => {
    setLoading(true); setError('')
    api.get('/admin/users')
      .then(({ data }) => setUsers(Array.isArray(data) ? data : data?.users || []))
      .catch((e) => setError(e.response?.data?.detail || t('users.loadError')))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchUsers() }, [])

  const fetchOrgs = () => {
    api.get('/admin/organizations')
      .then(({ data }) => setOrganizations(Array.isArray(data) ? data : []))
      .catch(() => {})
  }

  useEffect(() => { fetchOrgs() }, [])

  const urlQ = searchParams.get('q') || ''
  useEffect(() => {
    if (urlQ && urlQ !== search) {
      setSearch(urlQ)
    }
  }, [urlQ])

  const flash = (msg) => { setSuccess(msg); setTimeout(() => setSuccess(''), 3500) }

  const openCreate = () => { setForm({ ...EMPTY_FORM }); setShowPw(false); setModal('create') }
  const openEdit   = (u) => {
    setForm({ username: u.username, email: u.email || '', password: '', role: u.role, is_active: u.is_active !== false })
    setShowPw(false); setModal({ type: 'edit', user: u })
  }
  const openDelete = (u) => setModal({ type: 'delete', user: u })
  const closeModal = () => { setModal(null); setError('') }

  const handleCreate = () => {
    if (!form.username.trim() || !form.password.trim()) { setError(t('users.validationRequired')); return }
    setSaving(true); setError('')
    api.post('/admin/users', { ...form, organization_id: form.organization_id ? Number(form.organization_id) : null })
      .then(() => { closeModal(); fetchUsers(); flash(t('users.created')) })
      .catch((e) => setError(e.response?.data?.detail || t('users.createError')))
      .finally(() => setSaving(false))
  }

  const handleEdit = () => {
    setSaving(true); setError('')
    const payload = {}
    if (form.email     !== modal.user.email)     payload.email     = form.email
    if (form.role      !== modal.user.role)      payload.role      = form.role
    if (form.is_active !== modal.user.is_active) payload.is_active = form.is_active
    if (form.password.trim())                    payload.password  = form.password
    if (!Object.keys(payload).length) { closeModal(); setSaving(false); return }
    api.put(`/admin/users/${modal.user.username}`, payload)
      .then(() => { closeModal(); fetchUsers(); flash(t('users.updated')) })
      .catch((e) => setError(e.response?.data?.detail || t('users.updateError')))
      .finally(() => setSaving(false))
  }

  const handleDelete = () => {
    setSaving(true); setError('')
    api.delete(`/admin/users/${modal.user.id}`)
      .then(() => { closeModal(); fetchUsers(); flash(t('users.deleted')) })
      .catch((e) => setError(e.response?.data?.detail || t('users.deleteError')))
      .finally(() => setSaving(false))
  }

  const [detailUser, setDetailUser] = useState(null)

  const openDetail = (u) => setDetailUser(u)
  const closeDetail = () => setDetailUser(null)

  // ── Onboarding ──
  const [showOnboard, setShowOnboard] = useState(false)
  const [onboard, setOnboard] = useState({
    company_name: '', admin_username: '', admin_email: '', admin_password: '', admin_confirm: '',
    users: [{ username: '', email: '', password: '' }],
  })
  const [onboardResult, setOnboardResult] = useState(null)
  const [onboardSaving, setOnboardSaving] = useState(false)

  const openOnboard = () => {
    setOnboard({ company_name: '', admin_username: '', admin_email: '', admin_password: '', admin_confirm: '', users: [{ username: '', email: '', password: '' }] })
    setOnboardResult(null); setOnboardSaving(false); setShowOnboard(true)
  }
  const closeOnboard = () => { setShowOnboard(false); setOnboardResult(null) }

  const addUserRow = () => setOnboard(o => ({ ...o, users: [...o.users, { username: '', email: '', password: '' }] }))
  const removeUserRow = (idx) => setOnboard(o => ({ ...o, users: o.users.filter((_, i) => i !== idx) }))
  const setUserField = (idx, field, val) => setOnboard(o => {
    const users = [...o.users]; users[idx] = { ...users[idx], [field]: val }; return { ...o, users }
  })

  const handleOnboard = () => {
    const errs = []
    if (!onboard.company_name.trim()) errs.push('Nama perusahaan harus diisi')
    if (!onboard.admin_username.trim()) errs.push('Username admin harus diisi')
    if (!onboard.admin_email.trim() || !onboard.admin_email.includes('@')) errs.push('Email admin tidak valid')
    if (!onboard.admin_password.trim() || onboard.admin_password.length < 8) errs.push('Password admin minimal 8 karakter')
    if (onboard.admin_password !== onboard.admin_confirm) errs.push('Konfirmasi password admin tidak cocok')
    const validUsers = onboard.users.filter(u => u.username.trim() && u.email.trim() && u.password.trim())
    if (validUsers.length === 0) errs.push('Minimal 1 user harus diisi lengkap')
    if (errs.length) { setError(errs.join('. ')); return }

    setOnboardSaving(true); setError('')
    api.post('/admin/onboard-company', {
      company_name: onboard.company_name.trim(),
      admin_username: onboard.admin_username.trim(),
      admin_email: onboard.admin_email.trim().toLowerCase(),
      admin_password: onboard.admin_password,
      users: validUsers.map(u => ({ username: u.username.trim(), email: u.email.trim().toLowerCase(), password: u.password })),
    })
      .then(({ data }) => { setOnboardResult(data); fetchUsers(); fetchOrgs() })
      .catch((e) => setError(e.response?.data?.detail || 'Gagal onboard perusahaan'))
      .finally(() => setOnboardSaving(false))
  }

  const isCreate = modal === 'create'
  const isEdit   = modal?.type === 'edit'
  const isDelete = modal?.type === 'delete'

  // ── Group users by org for admin expansion ──
  const admins = users.filter(u => u.role === 'admin' || u.role === 'superadmin')
  const regularUsers = users.filter(u => u.role === 'user')
  const usersByOrg = {}
  regularUsers.forEach(u => {
    const oid = u.organization_id || '__none__'
    if (!usersByOrg[oid]) usersByOrg[oid] = []
    usersByOrg[oid].push(u)
  })

  const filtered = users.filter((u) => {
    if (roleFilter === 'user' && u.role !== 'user') return false
    if (roleFilter === 'admin' && u.role !== 'admin' && u.role !== 'superadmin') return false
    if (!search.trim()) return true
    const q = search.toLowerCase()
    return (u.username || '').toLowerCase().includes(q)
      || (u.email || '').toLowerCase().includes(q)
      || (u.role || '').toLowerCase().includes(q)
      || (u.organization_name || '').toLowerCase().includes(q)
  })

  const toggleAdminExpand = (username) => {
    setExpandedAdmin(expandedAdmin === username ? null : username)
  }

  return (
    <div style={{ padding: '0 0 24px' }}>
      {success && <div className={styles.msg}>{success}</div>}

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <div className={styles.sectionTitle}>
            <Users size={16} />
            <div>
              <strong>{t('users.title')}</strong>
              <span>{t('users.count', { count: filtered.length })}</span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ position: 'relative' }}>
              <Search size={13} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
              <input
                className={styles.searchInput}
                style={{ paddingLeft: 28 }}
                placeholder={t('users.searchPlaceholder')}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              {search && (
                <button style={{ position: 'absolute', right: 6, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0 }} onClick={() => setSearch('')}>
                  <X size={12} />
                </button>
              )}
            </div>
            <button onClick={fetchUsers} disabled={loading} className={styles.actionBtn}>
              <RefreshCw size={13} />
            </button>
            <button onClick={openCreate} className={styles.addBtn}>
              <Plus size={14} /> {t('users.add')}
            </button>
            <button onClick={openOnboard} style={{ padding: '5px 12px', borderRadius: 6, border: '1px solid #059669', background: 'transparent', color: '#059669', fontSize: '0.78rem', fontWeight: 500, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap' }}>
              <Building size={13} /> Onboard Perusahaan
            </button>
          </div>
        </div>

        {/* ── Role Filter Pills ── */}
        <div style={{ display: 'flex', gap: 6, padding: '8px 16px 0' }}>
          {[
            { key: 'all', label: 'Semua' },
            { key: 'user', label: 'User' },
            { key: 'admin', label: 'Admin' },
          ].map((f) => (
            <button
              key={f.key}
              onClick={() => { setRoleFilter(f.key); setExpandedAdmin(null) }}
              style={{
                padding: '4px 14px', borderRadius: 20, border: '1px solid var(--border)',
                background: roleFilter === f.key ? '#1a73e8' : 'transparent',
                color: roleFilter === f.key ? '#fff' : 'var(--text-muted)',
                fontSize: '0.78rem', fontWeight: 500, cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {f.key === 'admin' && <Shield size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} />}
              {f.key === 'user' && <Users size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} />}
              {f.label}
            </button>
          ))}
        </div>

        {error && !modal && (
          <div style={{ padding: '10px 16px', background: '#fce8e6', color: '#c5221f', fontSize: '0.8125rem', display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {loading ? (
          <div className={styles.emptyState}>{t('users.loading')}</div>
        ) : filtered.length === 0 ? (
          <div className={styles.emptyState}>{users.length === 0 ? t('users.noUsers') : t('users.noMatch')}</div>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th style={{ width: 30 }}></th>
                <th>{t('users.username')}</th>
                <th>{t('users.email')}</th>
                <th>Organisasi</th>
                <th>{t('users.role')}</th>
                <th>{t('users.status')}</th>
                <th style={{ textAlign: 'right' }}>{t('users.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => {
                const rc = ROLE_COLORS[u.role] || ROLE_COLORS.user
                const isAdminRow = (u.role === 'admin' || u.role === 'superadmin')
                const isExpanded = expandedAdmin === u.username
                const orgUsers = isAdminRow ? usersByOrg[u.organization_id || '__none__'] || [] : []
                return (
                  <tr
                    key={u.id}
                    onClick={(e) => {
                      if (e.target.closest('button, a')) return
                      openDetail(u)
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      {isAdminRow && orgUsers.length > 0 && (
                        <button
                          onClick={() => toggleAdminExpand(u.username)}
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0 }}
                          title="Lihat user yang di-handle"
                        >
                          {isExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                        </button>
                      )}
                    </td>
                    <td className={styles.usernameCell}>
                      {u.username}
                      {isAdminRow && <span style={{ marginLeft: 4, fontSize: '0.65rem', color: '#7C3AED', background: '#F3E8FF', padding: '1px 6px', borderRadius: 4 }}>{orgUsers.length} users</span>}
                    </td>
                    <td className={styles.mono}>
                      {u.email || '\u2014'}
                      {isAdminRow && u.role === 'admin' && u.email && (
                        <button
                          onClick={() => openEdit(u)}
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#2563EB', padding: '0 4px', verticalAlign: 'middle' }}
                          title="Ganti email admin"
                        >
                          <Pencil size={10} />
                        </button>
                      )}
                    </td>
                    <td style={{ fontSize: '0.78rem', color: u.organization_name ? 'var(--text)' : 'var(--text-muted)' }}>
                      {u.organization_name || '\u2014'}
                    </td>
                    <td>
                      <span className={styles.roleBadge} style={{ background: rc.bg, color: rc.color }}>
                        {u.role}
                      </span>
                    </td>
                    <td>
                      <span className={styles.statusDot} style={{ background: u.is_active !== false ? '#34a853' : '#ea4335' }} />
                      {u.is_active !== false ? t('users.active') : t('users.inactive')}
                    </td>
                    <td>
                      <div className={styles.actionGroup} style={{ justifyContent: 'flex-end' }}>
                        <button onClick={() => openEdit(u)} className={styles.actionBtn} title={t('users.edit')}>
                          <Pencil size={13} />
                        </button>
                        {u.role !== 'superadmin' && (
                          <button onClick={() => openDelete(u)} className={`${styles.actionBtn} ${styles.dangerActionBtn}`} title={t('users.delete')}>
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}

        {/* ── User Detail Panel ── */}
        {detailUser && (
          <div style={{ margin: '8px 16px 0', padding: '16px 20px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {detailUser.role === 'admin' || detailUser.role === 'superadmin'
                  ? <Shield size={18} style={{ color: '#2563EB' }} />
                  : <Users size={18} style={{ color: '#16A34A' }} />}
                <strong style={{ fontSize: '1rem' }}>{detailUser.username}</strong>
                <span className={styles.roleBadge} style={{ background: ROLE_COLORS[detailUser.role]?.bg || '#F0FDF4', color: ROLE_COLORS[detailUser.role]?.color || '#16A34A', fontSize: '0.7rem' }}>
                  {detailUser.role}
                </span>
                <span className={styles.statusDot} style={{ background: detailUser.is_active !== false ? '#34a853' : '#ea4335' }} />
                <span style={{ fontSize: '0.78rem', color: detailUser.is_active !== false ? '#34a853' : '#ea4335' }}>
                  {detailUser.is_active !== false ? 'Aktif' : 'Nonaktif'}
                </span>
              </div>
              <button onClick={closeDetail} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 2 }}>
                <X size={14} />
              </button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 24px', fontSize: '0.8125rem' }}>
              <div><span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem', marginBottom: 2 }}>Email</span><span>{detailUser.email || '\u2014'}</span></div>
              <div><span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem', marginBottom: 2 }}>Organisasi</span><span>{detailUser.organization_name || '\u2014'}</span></div>
              {detailUser.role === 'user' && (
                <div>
                  <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem', marginBottom: 2 }}>Admin</span>
                  <span>{(admins.filter(a => a.organization_id === detailUser.organization_id && a.organization_id != null).map(a => a.username).join(', ')) || 'Tidak ada admin'}</span>
                </div>
              )}
              {detailUser.role === 'admin' && (
                <div>
                  <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem', marginBottom: 2 }}>User Di-handle</span>
                  <span>{(usersByOrg[detailUser.organization_id || '__none__'] || []).length} user</span>
                </div>
              )}
              <div><span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem', marginBottom: 2 }}>ID</span><span style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{detailUser.id}</span></div>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
              <button onClick={() => { closeDetail(); openEdit(detailUser) }} className={styles.actionBtn} title="Edit">
                <Pencil size={13} /> Edit
              </button>
              {detailUser.role !== 'superadmin' && (
                <button onClick={() => { closeDetail(); openDelete(detailUser) }} className={`${styles.actionBtn} ${styles.dangerActionBtn}`} title="Hapus">
                  <Trash2 size={13} /> Hapus
                </button>
              )}
            </div>
          </div>
        )}

        {/* ── Expanded admin user lists ── */}
        {expandedAdmin && (
          <div style={{ margin: '8px 16px 0', padding: '12px 16px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8 }}>
            {(() => {
              const admin = filtered.find(u => u.username === expandedAdmin)
              if (!admin) return null
              const orgUsers = usersByOrg[admin.organization_id || '__none__'] || []
              return (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                    <Shield size={14} style={{ color: '#2563EB' }} />
                    <strong style={{ fontSize: '0.875rem' }}>{admin.username}</strong>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      — {orgUsers.length} user di-handle
                    </span>
                    <button
                      onClick={() => setExpandedAdmin(null)}
                      style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 2 }}
                    >
                      <X size={12} />
                    </button>
                  </div>
                  {orgUsers.length === 0 ? (
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Tidak ada user.</div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {orgUsers.map((usr) => (
                        <div key={usr.username} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 8px', borderRadius: 6, background: 'rgba(0,0,0,0.02)' }}>
                          <Mail size={11} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                          <span style={{ fontSize: '0.78rem', fontWeight: 500, minWidth: 140 }}>{usr.username}</span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{usr.email || '\u2014'}</span>
                          <span className={styles.statusDot} style={{ background: usr.is_active !== false ? '#34a853' : '#ea4335', flexShrink: 0 }} />
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{usr.is_active !== false ? 'Aktif' : 'Nonaktif'}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )
            })()}
          </div>
        )}
      </div>

      {(isCreate || isEdit || isDelete) && (
        <div className={styles.overlay} onClick={closeModal}>
          <div className={styles.editModal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.editModalHeader}>
              <h3>
                <Users size={16} />
                {isCreate ? t('users.add') : isEdit ? t('users.editTitle') : t('users.deleteTitle')}
              </h3>
              <button className={styles.modalCloseBtn} onClick={closeModal}><X size={16} /></button>
            </div>

            <div className={styles.editModalBody}>
              {error && (
                <div style={{ marginBottom: 12, padding: '8px 12px', background: '#fce8e6', color: '#c5221f', borderRadius: 6, fontSize: '0.8125rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <AlertCircle size={13} /> {error}
                </div>
              )}

              {isDelete ? (
                <>
                  <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875rem', lineHeight: 1.6 }}>
                    {t('users.confirmDelete')} <strong style={{ color: 'var(--text)' }}>{modal.user.username}</strong>? {t('users.confirmDeleteIrreversible')}
                  </p>
                  {modal.user.organization_name && (
                    <p style={{ margin: '8px 0 0', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      Organisasi: <strong>{modal.user.organization_name}</strong>
                    </p>
                  )}
                </>
              ) : (
                <>
                  {/* ── Detail info header ── */}
                  {isEdit && (
                    <div style={{ marginBottom: 16, padding: '10px 14px', background: 'rgba(26,115,232,0.05)', border: '1px solid rgba(26,115,232,0.15)', borderRadius: 8, fontSize: '0.8125rem' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 20px' }}>
                        <div><span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', display: 'block' }}>Username</span><strong>{modal.user.username}</strong></div>
                        <div><span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', display: 'block' }}>Role</span><span className={styles.roleBadge} style={{ background: ROLE_COLORS[modal.user.role]?.bg || '#F0FDF4', color: ROLE_COLORS[modal.user.role]?.color || '#16A34A', fontSize: '0.7rem', padding: '1px 8px', display: 'inline-block' }}>{modal.user.role}</span></div>
                        <div><span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', display: 'block' }}>Email</span><span>{modal.user.email || '\u2014'}</span></div>
                        <div><span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', display: 'block' }}>Organisasi</span><span>{modal.user.organization_name || '\u2014'}</span></div>
                        {modal.user.role === 'user' && (
                          <div><span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', display: 'block' }}>Admin</span><span>{(admins.filter(a => a.organization_id === modal.user.organization_id && a.organization_id != null).map(a => a.username).join(', ')) || 'Tidak ada admin'}</span></div>
                        )}
                        {modal.user.role === 'admin' && (
                          <div><span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', display: 'block' }}>User Di-handle</span><span>{(usersByOrg[modal.user.organization_id || '__none__'] || []).length} user</span></div>
                        )}
                        <div><span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', display: 'block' }}>Status</span><span style={{ color: modal.user.is_active !== false ? '#34a853' : '#ea4335' }}>{modal.user.is_active !== false ? 'Aktif' : 'Nonaktif'}</span></div>
                      </div>
                    </div>
                  )}
                  {isCreate && (
                    <div className={styles.fieldRow}>
                      <div className={styles.fieldLeft}>
                        <span className={styles.fieldLabel}>{t('users.username')}</span>
                        <span className={styles.fieldHint}>{t('users.usernameHint')}</span>
                      </div>
                      <div className={styles.fieldRight}>
                        <input className={styles.input} value={form.username} onChange={(e) => setForm(f => ({ ...f, username: e.target.value }))} placeholder={t('users.usernamePlaceholder')} />
                      </div>
                    </div>
                  )}
                  <div className={styles.fieldRow}>
                    <div className={styles.fieldLeft}>
                      <span className={styles.fieldLabel}>{t('users.email')}</span>
                      {isEdit && modal.user.role === 'admin' && (
                        <span className={styles.fieldHint} style={{ color: '#2563EB' }}>Email admin dapat diubah</span>
                      )}
                    </div>
                    <div className={styles.fieldRight}>
                      <input className={styles.input} type="email" value={form.email} onChange={(e) => setForm(f => ({ ...f, email: e.target.value }))} placeholder={t('users.emailPlaceholder')} />
                    </div>
                  </div>
                  <div className={styles.fieldRow}>
                    <div className={styles.fieldLeft}>
                      <span className={styles.fieldLabel}>{t('users.password')}</span>
                      {isEdit && <span className={styles.fieldHint}>{t('users.passwordHint')}</span>}
                    </div>
                    <div className={styles.fieldRight}>
                      <div className={styles.passwordInput}>
                        <input type={showPw ? 'text' : 'password'} value={form.password} onChange={(e) => setForm(f => ({ ...f, password: e.target.value }))} placeholder={isEdit ? t('users.passwordUnchanged') : t('users.passwordPlaceholder')} autoComplete="new-password" />
                        <button type="button" onClick={() => setShowPw(v => !v)}>
                          {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                      </div>
                    </div>
                  </div>
                  {isCreate && organizations.length > 0 && (
                    <div className={styles.fieldRow}>
                      <div className={styles.fieldLeft}>
                        <span className={styles.fieldLabel}>Organisasi</span>
                        {form.role === 'superadmin'
                          ? <span className={styles.fieldHint} style={{ color: '#7C3AED' }}>Superadmin tidak perlu organisasi</span>
                          : <span className={styles.fieldHint}>Wajib untuk {form.role}</span>}
                      </div>
                      <div className={styles.fieldRight}>
                        {form.role === 'superadmin' ? (
                          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', padding: '6px 0', display: 'block' }}>— (tidak ada)</span>
                        ) : (
                          <select className={styles.editSelect} value={form.organization_id} onChange={(e) => setForm(f => ({ ...f, organization_id: e.target.value }))}>
                            <option value="">Pilih organisasi...</option>
                            {organizations.map((o) => (
                              <option key={o.id} value={o.id}>{o.name}</option>
                            ))}
                          </select>
                        )}
                      </div>
                    </div>
                  )}
                  <div className={styles.fieldRow}>
                    <div className={styles.fieldLeft}>
                      <span className={styles.fieldLabel}>{t('users.role')}</span>
                    </div>
                    <div className={styles.fieldRight}>
                      <select className={styles.editSelect} value={form.role} onChange={(e) => setForm(f => ({ ...f, role: e.target.value, organization_id: e.target.value === 'superadmin' ? '' : f.organization_id }))}>
                        <option value="user">{t('role.user')}</option>
                        <option value="admin">{t('role.admin')}</option>
                        <option value="superadmin">{t('role.superadmin')}</option>
                      </select>
                    </div>
                  </div>
                  <div className={styles.fieldRow}>
                    <div className={styles.fieldLeft}>
                      <span className={styles.fieldLabel}>{t('users.status')}</span>
                    </div>
                    <div className={styles.fieldRight}>
                      <label className={styles.switchRow} style={{ marginTop: 0 }}>
                        <input type="checkbox" checked={form.is_active} onChange={(e) => setForm(f => ({ ...f, is_active: e.target.checked }))} />
                        <span className={styles.fieldLabel}>{form.is_active ? t('users.active') : t('users.inactive')}</span>
                      </label>
                    </div>
                  </div>
                </>
              )}
            </div>

            <div className={styles.editModalFooter}>
              <button onClick={closeModal} className={styles.cancelBtn}>{t('btn.cancel')}</button>
              {isDelete
                ? <button onClick={handleDelete} disabled={saving} className={styles.saveBtn} style={{ background: '#dc2626' }}>
                    {saving ? t('users.deleting') : t('users.delete')}
                  </button>
                : <button onClick={isCreate ? handleCreate : handleEdit} disabled={saving} className={styles.saveBtn}>
                    {saving ? t('common.saving') : isCreate ? t('users.create') : t('btn.save')}
                  </button>
              }
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Onboard Perusahaan ── */}
      {showOnboard && (
        <div className={styles.overlay} onClick={closeOnboard}>
          <div className={styles.editModal} onClick={(e) => e.stopPropagation()} style={{ maxWidth: 600 }}>
            <div className={styles.editModalHeader}>
              <h3><Building size={16} /> Onboard Perusahaan Baru</h3>
              <button className={styles.modalCloseBtn} onClick={closeOnboard}><X size={16} /></button>
            </div>
            <div className={styles.editModalBody} style={{ maxHeight: '70vh', overflowY: 'auto' }}>
              {error && showOnboard && (
                <div style={{ marginBottom: 12, padding: '8px 12px', background: '#fce8e6', color: '#c5221f', borderRadius: 6, fontSize: '0.8125rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <AlertCircle size={13} /> {error}
                </div>
              )}

              {onboardResult ? (
                /* ── Hasil ── */
                <div>
                  <div style={{ textAlign: 'center', padding: '16px 0' }}>
                    <CheckCircle size={40} style={{ color: '#34a853' }} />
                    <h3 style={{ margin: '8px 0 4px' }}>Onboard Berhasil!</h3>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', margin: 0 }}>{onboardResult.company}</p>
                  </div>
                  <div style={{ fontSize: '0.8125rem', display: 'grid', gap: 8 }}>
                    <div style={{ padding: '8px 12px', background: 'rgba(37,99,235,0.05)', borderRadius: 6, border: '1px solid rgba(37,99,235,0.15)' }}>
                      <strong>Admin:</strong> {onboardResult.admin}
                    </div>
                    <div style={{ padding: '8px 12px', background: 'rgba(52,168,83,0.05)', borderRadius: 6, border: '1px solid rgba(52,168,83,0.15)' }}>
                      <strong>Mailbox:</strong>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                        {onboardResult.mailboxes?.map(m => <span key={m} style={{ fontSize: '0.75rem', background: '#E8F5E9', color: '#2e7d32', padding: '2px 8px', borderRadius: 4 }}>{m}</span>)}
                      </div>
                    </div>
                    <div style={{ padding: '8px 12px', background: 'rgba(139,92,246,0.05)', borderRadius: 6, border: '1px solid rgba(139,92,246,0.15)' }}>
                      <strong>User ({onboardResult.users?.length || 0}):</strong>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                        {onboardResult.users?.map(u => <span key={u.username} style={{ fontSize: '0.75rem', background: '#F3E8FF', color: '#7C3AED', padding: '2px 8px', borderRadius: 4 }}>{u.username}</span>)}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                /* ── Form ── */
                <>
                  <div style={{ marginBottom: 14, padding: '8px 12px', background: 'rgba(5,150,105,0.08)', border: '1px solid rgba(5,150,105,0.2)', borderRadius: 6, fontSize: '0.75rem', color: '#065f46' }}>
                    <Building size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                    Form ini akan membuat: Perusahaan + Admin + 3 Mailbox standar + User secara otomatis.
                  </div>

                  <div className={styles.fieldRow}>
                    <div className={styles.fieldLeft}>
                      <span className={styles.fieldLabel}>Nama Perusahaan</span>
                    </div>
                    <div className={styles.fieldRight}>
                      <input className={styles.input} value={onboard.company_name} onChange={(e) => setOnboard(o => ({ ...o, company_name: e.target.value }))} placeholder="PT Maju Bersama" />
                    </div>
                  </div>

                  <h4 style={{ margin: '16px 0 8px', fontSize: '0.8125rem', color: '#2563EB', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Shield size={14} /> Data Admin
                  </h4>
                  <div className={styles.fieldRow}>
                    <div className={styles.fieldLeft}><span className={styles.fieldLabel}>Username Admin</span></div>
                    <div className={styles.fieldRight}><input className={styles.input} value={onboard.admin_username} onChange={(e) => setOnboard(o => ({ ...o, admin_username: e.target.value }))} placeholder="admin_perusahaan" /></div>
                  </div>
                  <div className={styles.fieldRow}>
                    <div className={styles.fieldLeft}><span className={styles.fieldLabel}>Email Admin</span></div>
                    <div className={styles.fieldRight}><input className={styles.input} type="email" value={onboard.admin_email} onChange={(e) => setOnboard(o => ({ ...o, admin_email: e.target.value }))} placeholder="admin@perusahaan.com" /></div>
                  </div>
                  <div className={styles.fieldRow}>
                    <div className={styles.fieldLeft}><span className={styles.fieldLabel}>Password Admin</span></div>
                    <div className={styles.fieldRight}><input className={styles.input} type="password" value={onboard.admin_password} onChange={(e) => setOnboard(o => ({ ...o, admin_password: e.target.value }))} placeholder="Min. 8 karakter" /></div>
                  </div>
                  <div className={styles.fieldRow}>
                    <div className={styles.fieldLeft}><span className={styles.fieldLabel}>Konfirmasi Password</span></div>
                    <div className={styles.fieldRight}><input className={styles.input} type="password" value={onboard.admin_confirm} onChange={(e) => setOnboard(o => ({ ...o, admin_confirm: e.target.value }))} placeholder="Ulangi password" /></div>
                  </div>

                  <h4 style={{ margin: '16px 0 8px', fontSize: '0.8125rem', color: '#16A34A', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Users size={14} /> Daftar User
                  </h4>
                  {onboard.users.map((u, i) => (
                    <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'flex-end', marginBottom: 6 }}>
                      <div style={{ flex: 1 }}>
                        <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', display: 'block', marginBottom: 2 }}>Username</span>
                        <input className={styles.input} style={{ fontSize: '0.78rem', padding: '5px 8px' }} value={u.username} onChange={(e) => setUserField(i, 'username', e.target.value)} placeholder="user1" />
                      </div>
                      <div style={{ flex: 1.5 }}>
                        <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', display: 'block', marginBottom: 2 }}>Email</span>
                        <input className={styles.input} style={{ fontSize: '0.78rem', padding: '5px 8px' }} type="email" value={u.email} onChange={(e) => setUserField(i, 'email', e.target.value)} placeholder="user1@perusahaan.com" />
                      </div>
                      <div style={{ flex: 1 }}>
                        <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', display: 'block', marginBottom: 2 }}>Password</span>
                        <input className={styles.input} style={{ fontSize: '0.78rem', padding: '5px 8px' }} type="password" value={u.password} onChange={(e) => setUserField(i, 'password', e.target.value)} placeholder="password" />
                      </div>
                      <button onClick={() => removeUserRow(i)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc2626', padding: '4px', flexShrink: 0 }} title="Hapus user"><X size={14} /></button>
                    </div>
                  ))}
                  <button onClick={addUserRow} style={{ background: 'none', border: '1px dashed var(--border)', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', color: '#16A34A', fontSize: '0.78rem', width: '100%', marginTop: 4 }}>
                    <Plus size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Tambah User
                  </button>
                </>
              )}
            </div>
            <div className={styles.editModalFooter}>
              {onboardResult ? (
                <button onClick={closeOnboard} className={styles.saveBtn}>Selesai</button>
              ) : (
                <>
                  <button onClick={closeOnboard} className={styles.cancelBtn}>Batal</button>
                  <button onClick={handleOnboard} disabled={onboardSaving} className={styles.saveBtn} style={{ background: '#059669' }}>
                    {onboardSaving ? 'Memproses...' : 'Buat Perusahaan'}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
