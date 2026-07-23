import { useEffect, useMemo, useState } from 'react'
import api, { getApiErrorMessage } from '../api/client'
import { AlertCircle, Eye, EyeOff, Pencil, Plus, RefreshCw, Search, Shield, Trash2, X } from 'lucide-react'
import { getMailDomain } from '../utils/mailbox'
import styles from './AdminPage.module.css'

const EMPTY_FORM = { username: '', emailLocal: '', password: '', confirmPassword: '', is_active: true }

function localPart(email = '') {
  return String(email).split('@', 1)[0]
}

function LockedEmailInput({ value, onChange, domain }) {
  return (
    <div style={{ display: 'flex', alignItems: 'stretch', width: '100%' }}>
      <input
        className={styles.input}
        style={{ flex: 1, minWidth: 0, borderTopRightRadius: 0, borderBottomRightRadius: 0 }}
        value={value}
        onChange={(event) => onChange(event.target.value.replace(/@.*$/, '').toLowerCase())}
        placeholder="nama.admin"
        autoComplete="off"
        maxLength={64}
      />
      <span style={{ display: 'flex', alignItems: 'center', padding: '0 10px', border: '1px solid var(--border)', borderLeft: 0, borderRadius: '0 4px 4px 0', background: 'var(--bg)', color: 'var(--text-muted)', fontSize: '0.8125rem', whiteSpace: 'nowrap' }}>@{domain}</span>
    </div>
  )
}

export default function SuperadminUserManagement() {
  const [admins, setAdmins] = useState([])
  const [domain, setDomain] = useState(getMailDomain())
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [modalError, setModalError] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [saving, setSaving] = useState(false)

  const fetchAdmins = async () => {
    setLoading(true)
    setError('')
    try {
      const [{ data: userData }, { data: configData }] = await Promise.all([
        api.get('/admin/users'),
        api.get('/admin/config'),
      ])
      const rows = Array.isArray(userData) ? userData : userData?.users || []
      setAdmins(rows.filter((user) => user.role === 'admin'))
      if (configData?.mail_domain) setDomain(configData.mail_domain)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Gagal memuat data admin.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAdmins() }, [])

  const filtered = useMemo(() => admins.filter((admin) => {
    const query = search.trim().toLowerCase()
    return !query
      || (admin.username || '').toLowerCase().includes(query)
      || (admin.email || '').toLowerCase().includes(query)
  }), [admins, search])

  const flash = (message) => {
    setSuccess(message)
    window.setTimeout(() => setSuccess(''), 3500)
  }

  const closeModal = () => {
    setModal(null)
    setForm(EMPTY_FORM)
    setModalError('')
    setShowPassword(false)
  }

  const openCreate = () => {
    setForm(EMPTY_FORM)
    setModal({ type: 'create' })
    setModalError('')
  }

  const openEdit = (admin) => {
    setForm({ username: admin.username, emailLocal: localPart(admin.email), password: '', confirmPassword: '', is_active: admin.is_active !== false })
    setModal({ type: 'edit', admin })
    setModalError('')
  }

  const validate = (creating) => {
    if (creating && !form.username.trim()) return 'Username wajib diisi.'
    if (!form.emailLocal.trim()) return 'Email admin wajib diisi.'
    if (creating && form.password.length < 8) return 'Password minimal 8 karakter.'
    if (form.password && form.password.length < 8) return 'Password minimal 8 karakter.'
    if (form.password !== form.confirmPassword) return 'Konfirmasi password tidak sama.'
    return ''
  }

  const submit = async () => {
    const creating = modal.type === 'create'
    const validationError = validate(creating)
    if (validationError) {
      setModalError(validationError)
      return
    }
    const email = `${form.emailLocal.trim().toLowerCase()}@${domain}`
    setSaving(true)
    setModalError('')
    try {
      if (creating) {
        await api.post('/admin/users', {
          username: form.username.trim(),
          email,
          password: form.password,
          role: 'admin',
          is_active: true,
        })
        flash(`Admin ${form.username.trim()} berhasil ditambahkan.`)
      } else {
        const payload = { email, is_active: form.is_active }
        if (form.password) payload.password = form.password
        await api.put(`/admin/users/${encodeURIComponent(modal.admin.username)}`, payload)
        flash(`Admin ${modal.admin.username} berhasil diperbarui.`)
      }
      closeModal()
      await fetchAdmins()
    } catch (requestError) {
      setModalError(getApiErrorMessage(requestError, creating ? 'Gagal menambahkan admin.' : 'Gagal memperbarui admin.'))
    } finally {
      setSaving(false)
    }
  }

  const removeAdmin = async (admin) => {
    if (!window.confirm(`Hapus admin ${admin.username}? Tindakan ini tidak dapat dibatalkan.`)) return
    setError('')
    try {
      await api.delete(`/admin/users/${encodeURIComponent(admin.username)}/hard`)
      await fetchAdmins()
      flash(`Admin ${admin.username} berhasil dihapus.`)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Gagal menghapus admin.'))
    }
  }

  return (
    <div style={{ padding: '0 0 24px' }}>
      {success && <div className={styles.msg}>{success}</div>}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <div className={styles.sectionTitle}>
            <Shield size={16} />
            <div><strong>Manajemen Admin</strong><span>{filtered.length} admin terdaftar · domain @{domain}</span></div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ position: 'relative' }}>
              <Search size={13} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
              <input className={styles.searchInput} style={{ paddingLeft: 28 }} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Cari username atau email admin..." />
              {search && <button aria-label="Hapus pencarian" onClick={() => setSearch('')} style={{ position: 'absolute', right: 6, top: '50%', transform: 'translateY(-50%)', border: 0, background: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><X size={12} /></button>}
            </div>
            <button className={styles.actionBtn} onClick={fetchAdmins} disabled={loading} title="Muat ulang"><RefreshCw size={13} /></button>
            <button className={styles.addBtn} onClick={openCreate}><Plus size={14} /> Tambah Admin</button>
          </div>
        </div>

        {error && <div style={{ padding: '10px 16px', background: '#fce8e6', color: '#c5221f', fontSize: '0.8125rem', display: 'flex', alignItems: 'center', gap: 8 }}><AlertCircle size={14} /> {error}</div>}
        {loading ? (
          <div className={styles.emptyState}>Memuat admin...</div>
        ) : filtered.length === 0 ? (
          <div className={styles.emptyState}>{admins.length ? 'Admin tidak ditemukan.' : 'Belum ada admin.'}</div>
        ) : (
          <table className={styles.table}>
            <thead><tr><th>Username</th><th>Email</th><th>Cakupan</th><th>Status</th><th style={{ textAlign: 'right' }}>Aksi</th></tr></thead>
            <tbody>
              {filtered.map((admin) => (
                <tr key={admin.id}>
                  <td className={styles.usernameCell}>{admin.username}</td>
                  <td className={styles.mono}>{admin.email || '—'}</td>
                  <td>{admin.organization_name || 'Global'}</td>
                  <td><span className={styles.statusDot} style={{ background: admin.is_active !== false ? '#34a853' : '#ea4335' }} />{admin.is_active !== false ? 'Aktif' : 'Nonaktif'}</td>
                  <td><div className={styles.actionGroup} style={{ justifyContent: 'flex-end' }}><button className={styles.actionBtn} onClick={() => openEdit(admin)} title="Edit admin"><Pencil size={13} /></button><button className={`${styles.actionBtn} ${styles.dangerActionBtn}`} onClick={() => removeAdmin(admin)} title="Hapus admin"><Trash2 size={13} /></button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {modal && (
        <div className={styles.overlay} onClick={closeModal}>
          <div className={styles.editModal} onClick={(event) => event.stopPropagation()}>
            <div className={styles.editModalHeader}><h3><Shield size={16} />{modal.type === 'create' ? 'Tambah Admin' : `Edit ${modal.admin.username}`}</h3><button className={styles.modalCloseBtn} onClick={closeModal}><X size={16} /></button></div>
            <div className={styles.editModalBody}>
              {modalError && <div style={{ marginBottom: 12, padding: '8px 12px', background: '#fce8e6', color: '#c5221f', borderRadius: 6, fontSize: '0.8125rem', display: 'flex', alignItems: 'center', gap: 8 }}><AlertCircle size={13} /> {modalError}</div>}
              <div className={styles.fieldRow}><div className={styles.fieldLeft}><span className={styles.fieldLabel}>Username</span><span className={styles.fieldHint}>Identitas login admin</span></div><div className={styles.fieldRight} style={{ width: '58%' }}><input className={styles.input} style={{ width: '100%' }} value={form.username} disabled={modal.type === 'edit'} onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))} maxLength={64} /></div></div>
              <div className={styles.fieldRow}><div className={styles.fieldLeft}><span className={styles.fieldLabel}>Email</span><span className={styles.fieldHint}>Domain dikunci oleh konfigurasi .env</span></div><div className={styles.fieldRight} style={{ width: '58%' }}><LockedEmailInput value={form.emailLocal} domain={domain} onChange={(value) => setForm((current) => ({ ...current, emailLocal: value }))} /></div></div>
              <div className={styles.fieldRow}><div className={styles.fieldLeft}><span className={styles.fieldLabel}>Password</span><span className={styles.fieldHint}>{modal.type === 'edit' ? 'Kosongkan jika tidak diubah' : 'Minimal 8 karakter'}</span></div><div className={styles.fieldRight} style={{ width: '58%', position: 'relative' }}><input className={styles.input} style={{ width: '100%', paddingRight: 34 }} type={showPassword ? 'text' : 'password'} value={form.password} onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))} autoComplete="new-password" /><button type="button" onClick={() => setShowPassword((value) => !value)} aria-label="Tampilkan password" style={{ position: 'absolute', right: 7, border: 0, background: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>{showPassword ? <EyeOff size={15} /> : <Eye size={15} />}</button></div></div>
              <div className={styles.fieldRow}><div className={styles.fieldLeft}><span className={styles.fieldLabel}>Konfirmasi Password</span></div><div className={styles.fieldRight} style={{ width: '58%' }}><input className={styles.input} style={{ width: '100%' }} type={showPassword ? 'text' : 'password'} value={form.confirmPassword} onChange={(event) => setForm((current) => ({ ...current, confirmPassword: event.target.value }))} autoComplete="new-password" /></div></div>
              {modal.type === 'edit' && <div className={styles.fieldRow}><div className={styles.fieldLeft}><span className={styles.fieldLabel}>Status</span></div><div className={styles.fieldRight}><label className={styles.switchRow} style={{ marginTop: 0 }}><input type="checkbox" checked={form.is_active} onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))} /><span className={styles.fieldLabel}>{form.is_active ? 'Aktif' : 'Nonaktif'}</span></label></div></div>}
            </div>
            <div className={styles.editModalFooter}><button className={styles.cancelBtn} onClick={closeModal}>Batal</button><button className={styles.saveBtn} disabled={saving} onClick={submit}>{saving ? 'Menyimpan...' : (modal.type === 'create' ? 'Tambah Admin' : 'Simpan')}</button></div>
          </div>
        </div>
      )}
    </div>
  )
}
