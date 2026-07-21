import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from '../i18n/context'
import api from '../api/client'
import { Users, RefreshCw, AlertCircle, Pencil, X, Search } from 'lucide-react'
import styles from './AdminPage.module.css'

const ROLE_COLORS = {
  superadmin: { bg: '#F3E8FF', color: '#7C3AED' },
  admin:      { bg: '#EFF6FF', color: '#2563EB' },
  user:       { bg: '#F0FDF4', color: '#16A34A' },
}

export default function AdminUserManagement() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const [users,   setUsers]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')
  const [success, setSuccess] = useState('')
  const [modal,   setModal]   = useState(null)
  const [form,    setForm]    = useState({ email: '', is_active: true })
  const [saving,  setSaving]  = useState(false)
  const [search,  setSearch]  = useState(() => searchParams.get('q') || '')

  const fetchUsers = () => {
    setLoading(true); setError('')
    api.get('/admin/users')
      .then(({ data }) => setUsers(Array.isArray(data) ? data : data?.users || []))
      .catch((e) => setError(e.response?.data?.detail || t('users.loadError')))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchUsers() }, [])

  // Sync URL q param to local search state (for global search autocomplete)
  const urlQ = searchParams.get('q') || ''
  useEffect(() => {
    if (urlQ && urlQ !== search) {
      setSearch(urlQ)
    }
  }, [urlQ])

  const flash = (msg) => { setSuccess(msg); setTimeout(() => setSuccess(''), 3500) }

  const openEdit   = (u) => { setForm({ email: u.email || '', is_active: u.is_active !== false }); setModal({ user: u }); setError('') }
  const closeModal = () => { setModal(null); setError('') }

  const handleEdit = () => {
    setSaving(true); setError('')
    const payload = {}
    if (form.email     !== modal.user.email)     payload.email     = form.email
    if (form.is_active !== modal.user.is_active) payload.is_active = form.is_active
    if (!Object.keys(payload).length) { closeModal(); setSaving(false); return }
    api.patch(`/admin/users/${modal.user.id}`, payload)
      .then(() => { closeModal(); fetchUsers(); flash(t('users.updated')) })
      .catch((e) => setError(e.response?.data?.detail || t('users.updateError')))
      .finally(() => setSaving(false))
  }

  const filtered = users.filter((u) => {
    if (!search.trim()) return true
    const q = search.toLowerCase()
    return (u.username || '').toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q)
  })

  return (
    <div style={{ padding: '0 0 24px' }}>
      {success && <div className={styles.msg}>{success}</div>}

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <div className={styles.sectionTitle}>
            <Users size={16} />
            <div>
              <strong>{t('users.title')}</strong>
              <span>{filtered.length} {t('users.count')}</span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div className={styles.searchWrap} style={{ position: 'relative' }}>
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
          </div>
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
                <th>{t('users.username')}</th>
                <th>{t('users.email')}</th>
                <th>{t('users.role')}</th>
                <th>{t('users.status')}</th>
                <th style={{ textAlign: 'right' }}>{t('users.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => {
                const rc = ROLE_COLORS[u.role] || ROLE_COLORS.user
                return (
                  <tr key={u.id}>
                    <td className={styles.usernameCell}>{u.username}</td>
                    <td className={styles.mono}>{u.email || '—'}</td>
                    <td>
                      <span className={styles.roleBadge} style={{ background: rc.bg, color: rc.color }}>
                        {u.role}
                      </span>
                    </td>
                    <td>
                      <span className={styles.statusDot} style={{ background: u.is_active !== false ? '#34a853' : '#ea4335' }} />
                      {u.is_active !== false ? t('label.active') : t('label.inactive')}
                    </td>
                    <td>
                      <div className={styles.actionGroup} style={{ justifyContent: 'flex-end' }}>
                        <button onClick={() => openEdit(u)} className={styles.actionBtn} title={t('common.edit')}>
                          <Pencil size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {modal && (
        <div className={styles.overlay} onClick={closeModal}>
          <div className={styles.editModal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.editModalHeader}>
              <h3><Users size={16} />{t('users.editTitle', { username: modal.user.username })}</h3>
              <button className={styles.modalCloseBtn} onClick={closeModal}><X size={16} /></button>
            </div>
            <div className={styles.editModalBody}>
              {error && (
                <div style={{ marginBottom: 12, padding: '8px 12px', background: '#fce8e6', color: '#c5221f', borderRadius: 6, fontSize: '0.8125rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <AlertCircle size={13} /> {error}
                </div>
              )}
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <span className={styles.fieldLabel}>{t('users.email')}</span>
                </div>
                <div className={styles.fieldRight}>
                  <input className={styles.input} type="email" value={form.email} onChange={(e) => setForm(f => ({ ...f, email: e.target.value }))} placeholder="email@domain.com" />
                </div>
              </div>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <span className={styles.fieldLabel}>{t('users.status')}</span>
                </div>
                <div className={styles.fieldRight}>
                  <label className={styles.switchRow} style={{ marginTop: 0 }}>
                    <input type="checkbox" checked={form.is_active} onChange={(e) => setForm(f => ({ ...f, is_active: e.target.checked }))} />
                    <span className={styles.fieldLabel}>{form.is_active ? t('label.active') : t('label.inactive')}</span>
                  </label>
                </div>
              </div>
            </div>
            <div className={styles.editModalFooter}>
              <button onClick={closeModal} className={styles.cancelBtn}>{t('btn.cancel')}</button>
              <button onClick={handleEdit} disabled={saving} className={styles.saveBtn}>
                {saving ? t('common.saving') : t('btn.save')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
