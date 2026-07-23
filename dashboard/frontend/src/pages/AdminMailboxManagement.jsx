import { useEffect, useMemo, useState } from 'react'
import api, { getApiErrorMessage } from '../api/client'
import { useMe } from '../api/auth'
import {
  AlertCircle, ArrowRight, CheckCircle2, ExternalLink, Eye, EyeOff,
  Forward, KeyRound, Mail, MailCheck, Plus, RefreshCw, Search,
  Power, PowerOff, ShieldCheck, Trash2, UserCog, X,
} from 'lucide-react'
import { getMailDomain } from '../utils/mailbox'
import ConfirmDialog from '../components/common/ConfirmDialog'
import base from './AdminPage.module.css'
import styles from './AdminMailboxManagement.module.css'

const EMPTY_CREATE = { localPart: '', senderName: '', password: '', confirmPassword: '', assignedTo: '' }

function validateStrongPassword(password) {
  if (password.length < 8) return 'Password minimal 8 karakter.'
  if (!/[A-Z]/.test(password)) return 'Password harus mengandung huruf besar.'
  if (!/[a-z]/.test(password)) return 'Password harus mengandung huruf kecil.'
  if (!/[0-9]/.test(password)) return 'Password harus mengandung angka.'
  if (!/[^A-Za-z0-9]/.test(password)) return 'Password harus mengandung karakter spesial.'
  return ''
}

function LockedAddress({ value, onChange, domain, autoFocus = false }) {
  return (
    <div className={styles.lockedAddress}>
      <input className={base.input} value={value} onChange={(event) => onChange(event.target.value.replace(/@.*$/, '').toLowerCase())} placeholder="inbox" autoFocus={autoFocus} autoComplete="off" />
      <span>@{domain}</span>
    </div>
  )
}

export default function AdminMailboxManagement() {
  const { data: me } = useMe()
  const isSuperadmin = me?.user?.role === 'superadmin'
  const [mailboxes, setMailboxes] = useState([])
  const [admins, setAdmins] = useState([])
  const [domain, setDomain] = useState(getMailDomain())
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState(EMPTY_CREATE)
  const [passwordMailbox, setPasswordMailbox] = useState(null)
  const [passwordForm, setPasswordForm] = useState({ password: '', confirmPassword: '' })
  const [forwardMailbox, setForwardMailbox] = useState(null)
  const [forwardForm, setForwardForm] = useState({ enabled: false, target: '', keepCopy: true })
  const [managerMailbox, setManagerMailbox] = useState(null)
  const [managerUsername, setManagerUsername] = useState('')
  const [modalError, setModalError] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [saving, setSaving] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)
  const [actionSaving, setActionSaving] = useState(false)

  const fetchMailboxes = async () => {
    setLoading(true)
    setError('')
    try {
      const requests = [api.get('/admin/mailboxes'), api.get('/admin/config')]
      if (isSuperadmin) requests.push(api.get('/admin/users'))
      const [mailboxResponse, configResponse, adminResponse] = await Promise.all(requests)
      setMailboxes(Array.isArray(mailboxResponse.data) ? mailboxResponse.data : [])
      if (configResponse.data?.mail_domain) setDomain(configResponse.data.mail_domain)
      if (adminResponse) {
        const rows = Array.isArray(adminResponse.data) ? adminResponse.data : adminResponse.data?.users || []
        setAdmins(rows.filter((admin) => admin.role === 'admin' && admin.is_active !== false))
      }
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Gagal memuat mailbox.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchMailboxes() }, [isSuperadmin])

  const filtered = useMemo(() => mailboxes.filter((mailbox) => {
    const query = search.trim().toLowerCase()
    return !query || [mailbox.email, mailbox.sender_name, mailbox.assigned_to, mailbox.forward_to]
      .some((value) => (value || '').toLowerCase().includes(query))
  }), [mailboxes, search])

  const activeCount = mailboxes.filter((mailbox) => mailbox.is_active).length
  const forwardedCount = mailboxes.filter((mailbox) => mailbox.forward_enabled).length

  const flash = (message) => {
    setSuccess(message)
    window.setTimeout(() => setSuccess(''), 3500)
  }

  const closeModal = () => {
    setCreateOpen(false)
    setPasswordMailbox(null)
    setForwardMailbox(null)
    setManagerMailbox(null)
    setCreateForm(EMPTY_CREATE)
    setPasswordForm({ password: '', confirmPassword: '' })
    setForwardForm({ enabled: false, target: '', keepCopy: true })
    setManagerUsername('')
    setModalError('')
    setShowPassword(false)
  }

  const openCreate = () => {
    const defaultManager = isSuperadmin && admins.length === 1 ? admins[0].username : ''
    setCreateForm({ ...EMPTY_CREATE, assignedTo: defaultManager })
    setCreateOpen(true)
    setModalError('')
  }

  const submitCreate = async () => {
    const localPart = createForm.localPart.trim().toLowerCase()
    if (!localPart || !/^[a-z0-9._%+-]+$/.test(localPart)) return setModalError('Nama mailbox tidak valid.')
    if (isSuperadmin && !createForm.assignedTo) return setModalError('Pilih admin pengelola mailbox.')
    const passwordError = validateStrongPassword(createForm.password)
    if (passwordError) return setModalError(passwordError)
    if (createForm.password !== createForm.confirmPassword) return setModalError('Konfirmasi password tidak sama.')

    setSaving(true)
    setModalError('')
    const email = `${localPart}@${domain}`
    try {
      await api.post('/admin/mailboxes', {
        email,
        domain,
        password: createForm.password,
        sender_name: createForm.senderName.trim(),
        ...(isSuperadmin ? { assigned_to: createForm.assignedTo } : {}),
      })
      closeModal()
      await fetchMailboxes()
      flash(`Mailbox ${email} berhasil ditambahkan.`)
    } catch (requestError) {
      setModalError(getApiErrorMessage(requestError, 'Gagal menambahkan mailbox.'))
    } finally { setSaving(false) }
  }

  const submitPassword = async () => {
    const passwordError = validateStrongPassword(passwordForm.password)
    if (passwordError) return setModalError(passwordError)
    if (passwordForm.password !== passwordForm.confirmPassword) return setModalError('Konfirmasi password tidak sama.')
    setSaving(true)
    setModalError('')
    try {
      await api.post(`/admin/mailboxes/${passwordMailbox.id}/change-password`, { password: passwordForm.password })
      const email = passwordMailbox.email
      closeModal()
      flash(`Password ${email} berhasil diperbarui.`)
    } catch (requestError) {
      setModalError(getApiErrorMessage(requestError, 'Gagal memperbarui password mailbox.'))
    } finally { setSaving(false) }
  }

  const openWebmail = async (mailbox) => {
    try {
      const { data } = await api.post(`/admin/mailboxes/${mailbox.id}/autologin-token`)
      window.open(`/mail/${encodeURIComponent(mailbox.id)}/login?autotoken=${encodeURIComponent(data.token)}`, '_blank', 'noopener,noreferrer')
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Mailbox tidak dapat dibuka.'))
    }
  }

  const openForward = (mailbox) => {
    setForwardMailbox(mailbox)
    setForwardForm({ enabled: Boolean(mailbox.forward_enabled), target: mailbox.forward_to || '', keepCopy: mailbox.forward_keep_copy !== false })
    setModalError('')
  }

  const submitForward = async () => {
    const target = forwardForm.target.trim().toLowerCase()
    if (forwardForm.enabled && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(target)) return setModalError('Alamat tujuan forward tidak valid.')
    setSaving(true)
    setModalError('')
    try {
      await api.put(`/admin/mailboxes/${forwardMailbox.id}/forwarder`, { target, enabled: forwardForm.enabled, keep_copy: forwardForm.keepCopy })
      const email = forwardMailbox.email
      closeModal()
      await fetchMailboxes()
      flash(`Forward email ${email} berhasil diperbarui.`)
    } catch (requestError) {
      setModalError(getApiErrorMessage(requestError, 'Gagal menyimpan forward email.'))
    } finally { setSaving(false) }
  }

  const openManager = (mailbox) => {
    setManagerMailbox(mailbox)
    setManagerUsername(mailbox.assigned_to || '')
    setModalError('')
  }

  const submitManager = async () => {
    if (!managerUsername) return setModalError('Pilih admin pengelola mailbox.')
    setSaving(true)
    setModalError('')
    try {
      await api.put(`/admin/mailboxes/${managerMailbox.id}`, { assigned_to: managerUsername })
      const email = managerMailbox.email
      closeModal()
      await fetchMailboxes()
      flash(`Pengelola ${email} berhasil dipindahkan ke ${managerUsername}.`)
    } catch (requestError) {
      setModalError(getApiErrorMessage(requestError, 'Gagal mengganti admin pengelola.'))
    } finally { setSaving(false) }
  }

  const applyMailboxAction = async () => {
    if (!confirmAction) return
    const { type, mailbox } = confirmAction
    setActionSaving(true)
    setError('')
    try {
      if (type === 'delete') {
        await api.delete(`/admin/mailboxes/${mailbox.id}`)
      } else {
        await api.put(`/admin/mailboxes/${mailbox.id}`, { is_active: type === 'activate' })
      }
      setConfirmAction(null)
      await fetchMailboxes()
      const messages = {
        disable: `Mailbox ${mailbox.email} dinonaktifkan.`,
        activate: `Mailbox ${mailbox.email} diaktifkan kembali.`,
        delete: `Mailbox ${mailbox.email} dan seluruh data emailnya dihapus permanen.`,
      }
      flash(messages[type])
    } catch (requestError) {
      const fallback = type === 'delete'
        ? 'Gagal menghapus mailbox secara permanen.'
        : type === 'activate' ? 'Gagal mengaktifkan mailbox.' : 'Gagal menonaktifkan mailbox.'
      setError(getApiErrorMessage(requestError, fallback))
    } finally { setActionSaving(false) }
  }

  const confirmation = confirmAction ? {
    disable: {
      title: 'Nonaktifkan mailbox?',
      message: 'Mailbox tidak dapat menerima, mengirim, atau diakses sampai diaktifkan kembali. Semua data email tetap tersimpan.',
      confirmText: 'Nonaktifkan',
      icon: PowerOff,
      tone: 'info',
    },
    activate: {
      title: 'Aktifkan kembali mailbox?',
      message: 'Mailbox akan kembali dapat menerima, mengirim, dan diakses oleh admin pengelola.',
      confirmText: 'Aktifkan',
      icon: Power,
      tone: 'info',
    },
    delete: {
      title: 'Hapus mailbox permanen?',
      message: 'Mailbox beserta seluruh email masuk, terkirim, balasan, forward, draf, lampiran, feedback, dan riwayat email akan dihapus permanen. Tindakan ini tidak dapat dibatalkan.',
      confirmText: 'Hapus permanen',
      icon: Trash2,
      tone: 'danger',
    },
  }[confirmAction.type] : null

  const modalOpen = createOpen || passwordMailbox || forwardMailbox || managerMailbox
  const currentPassword = createOpen ? createForm.password : passwordForm.password
  const currentConfirm = createOpen ? createForm.confirmPassword : passwordForm.confirmPassword
  const updatePassword = (value) => createOpen ? setCreateForm((form) => ({ ...form, password: value })) : setPasswordForm((form) => ({ ...form, password: value }))
  const updateConfirm = (value) => createOpen ? setCreateForm((form) => ({ ...form, confirmPassword: value })) : setPasswordForm((form) => ({ ...form, confirmPassword: value }))

  const modalTitle = createOpen ? 'Tambah Email' : forwardMailbox ? 'Atur Forward Email' : managerMailbox ? 'Admin Pengelola' : 'Ubah Password'
  const submitModal = createOpen ? submitCreate : forwardMailbox ? submitForward : managerMailbox ? submitManager : submitPassword
  const submitLabel = createOpen ? 'Tambah Email' : forwardMailbox ? 'Simpan Forward' : managerMailbox ? 'Simpan Pengelola' : 'Simpan Password'

  return (
    <div className={styles.page}>
      {success && <div className={styles.success}><CheckCircle2 size={17} />{success}</div>}
      <div className={styles.summaryGrid}>
        <div className={styles.summaryCard}><span className={styles.summaryIcon}><Mail size={20} /></span><div><strong>{mailboxes.length}</strong><span>Total mailbox</span></div></div>
        <div className={styles.summaryCard}><span className={`${styles.summaryIcon} ${styles.green}`}><MailCheck size={20} /></span><div><strong>{activeCount}</strong><span>Mailbox aktif</span></div></div>
        <div className={styles.summaryCard}><span className={`${styles.summaryIcon} ${styles.violet}`}><Forward size={20} /></span><div><strong>{forwardedCount}</strong><span>Forward aktif</span></div></div>
      </div>

      <section className={styles.panel}>
        <header className={styles.panelHeader}>
          <div className={styles.heading}><span className={styles.headingIcon}><ShieldCheck size={20} /></span><div><h2>Manajemen Email</h2><p>{isSuperadmin ? 'Atur mailbox dan admin pengelola' : 'Mailbox yang Anda kelola'} · domain @{domain}</p></div></div>
          <div className={styles.tools}>
            <label className={styles.search}><Search size={17} /><input placeholder="Cari alamat, nama, atau admin..." value={search} onChange={(event) => setSearch(event.target.value)} />{search && <button type="button" aria-label="Hapus pencarian" onClick={() => setSearch('')}><X size={15} /></button>}</label>
            <button className={styles.iconButton} onClick={fetchMailboxes} disabled={loading} title="Muat ulang"><RefreshCw size={17} /></button>
            <button className={styles.primaryButton} onClick={openCreate}><Plus size={18} />Tambah Email</button>
          </div>
        </header>

        {error && <div className={styles.error}><AlertCircle size={16} />{error}</div>}
        <div className={styles.tableWrap}>
          {loading ? <div className={styles.empty}>Memuat mailbox...</div> : filtered.length === 0 ? (
            <div className={styles.empty}><Mail size={34} /><strong>{mailboxes.length ? 'Mailbox tidak ditemukan' : 'Belum ada mailbox'}</strong><span>{mailboxes.length ? 'Coba gunakan kata pencarian lain.' : 'Tambahkan mailbox pertama untuk mulai menerima email.'}</span></div>
          ) : (
            <table className={styles.table}>
              <thead><tr><th>Alamat Email</th><th>Nama Pengirim</th>{isSuperadmin && <th>Admin Pengelola</th>}<th>Forward</th><th>Status</th><th className={styles.actionsHeading}>Aksi</th></tr></thead>
              <tbody>{filtered.map((mailbox) => (
                <tr key={mailbox.id}>
                  <td><div className={styles.emailCell}><span>{(mailbox.email || '?')[0].toUpperCase()}</span><div><strong>{mailbox.email}</strong><small>@{mailbox.domain || domain}</small></div></div></td>
                  <td>{mailbox.sender_name || <span className={styles.muted}>Belum diatur</span>}</td>
                  {isSuperadmin && <td><button className={styles.managerBadge} onClick={() => openManager(mailbox)} title="Ganti admin pengelola"><UserCog size={15} />{mailbox.assigned_to || 'Belum ditetapkan'}</button></td>}
                  <td>{mailbox.forward_enabled ? <span className={styles.forwardBadge}><ArrowRight size={14} />{mailbox.forward_to}</span> : <span className={styles.neutralBadge}>Nonaktif</span>}</td>
                  <td><span className={mailbox.is_active ? styles.activeBadge : styles.inactiveBadge}><i />{mailbox.is_active ? 'Aktif' : 'Nonaktif'}</span></td>
                  <td><div className={styles.actions}>
                    {mailbox.is_active && <button title="Buka webmail" onClick={() => openWebmail(mailbox)}><ExternalLink size={16} /></button>}
                    {mailbox.is_active && <button title="Atur forward" onClick={() => openForward(mailbox)}><Forward size={16} /></button>}
                    {isSuperadmin && mailbox.is_active && <button title="Ganti admin pengelola" onClick={() => openManager(mailbox)}><UserCog size={16} /></button>}
                    {mailbox.is_active && <button title="Ubah password" onClick={() => { setPasswordMailbox(mailbox); setModalError('') }}><KeyRound size={16} /></button>}
                    {mailbox.is_active ? (
                      <button className={styles.warning} title="Nonaktifkan mailbox" aria-label={`Nonaktifkan ${mailbox.email}`} onClick={() => setConfirmAction({ type: 'disable', mailbox })}><PowerOff size={16} /></button>
                    ) : (
                      <button className={styles.activate} title="Aktifkan kembali" aria-label={`Aktifkan ${mailbox.email}`} onClick={() => setConfirmAction({ type: 'activate', mailbox })}><Power size={16} /></button>
                    )}
                    <button className={styles.danger} title="Hapus permanen" aria-label={`Hapus permanen ${mailbox.email}`} onClick={() => setConfirmAction({ type: 'delete', mailbox })}><Trash2 size={16} /></button>
                  </div></td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
      </section>

      {modalOpen && <div className={base.overlay} onClick={closeModal}>
        <div className={`${base.editModal} ${styles.modal}`} onClick={(event) => event.stopPropagation()}>
          <div className={base.editModalHeader}><h3>{managerMailbox ? <UserCog size={17} /> : forwardMailbox ? <Forward size={17} /> : passwordMailbox ? <KeyRound size={17} /> : <Mail size={17} />}{modalTitle}</h3><button className={base.modalCloseBtn} onClick={closeModal}><X size={17} /></button></div>
          <div className={base.editModalBody}>
            {modalError && <div className={styles.modalError}><AlertCircle size={15} />{modalError}</div>}
            {createOpen && <>
              <div className={base.fieldRow}><div className={base.fieldLeft}><span className={base.fieldLabel}>Alamat Email</span><span className={base.fieldHint}>Domain dikunci oleh konfigurasi .env</span></div><div className={styles.fieldControl}><LockedAddress value={createForm.localPart} domain={domain} autoFocus onChange={(value) => setCreateForm((form) => ({ ...form, localPart: value }))} /></div></div>
              <div className={base.fieldRow}><div className={base.fieldLeft}><span className={base.fieldLabel}>Nama Pengirim</span><span className={base.fieldHint}>Nama pada email keluar</span></div><div className={styles.fieldControl}><input className={base.input} value={createForm.senderName} onChange={(event) => setCreateForm((form) => ({ ...form, senderName: event.target.value }))} /></div></div>
              {isSuperadmin && <div className={base.fieldRow}><div className={base.fieldLeft}><span className={base.fieldLabel}>Admin Pengelola</span><span className={base.fieldHint}>Hanya admin ini yang dapat mengakses mailbox</span></div><div className={styles.fieldControl}><select className={base.input} value={createForm.assignedTo} onChange={(event) => setCreateForm((form) => ({ ...form, assignedTo: event.target.value }))}><option value="">Pilih admin</option>{admins.map((admin) => <option key={admin.username} value={admin.username}>{admin.username}</option>)}</select></div></div>}
            </>}
            {!createOpen && <div className={styles.mailboxContext}><Mail size={15} /><span>Mailbox</span><strong>{(forwardMailbox || passwordMailbox || managerMailbox).email}</strong></div>}
            {managerMailbox ? <div className={base.fieldRow}><div className={base.fieldLeft}><span className={base.fieldLabel}>Admin Pengelola</span><span className={base.fieldHint}>Akses admin lama langsung dicabut setelah disimpan</span></div><div className={styles.fieldControl}><select className={base.input} value={managerUsername} onChange={(event) => setManagerUsername(event.target.value)}><option value="">Pilih admin</option>{admins.map((admin) => <option key={admin.username} value={admin.username}>{admin.username}</option>)}</select></div></div> : forwardMailbox ? <>
              <div className={base.fieldRow}><div className={base.fieldLeft}><span className={base.fieldLabel}>Aktifkan Forward</span><span className={base.fieldHint}>Teruskan email masuk</span></div><label className={base.switchRow}><input type="checkbox" checked={forwardForm.enabled} onChange={(event) => setForwardForm((form) => ({ ...form, enabled: event.target.checked }))} /><span>{forwardForm.enabled ? 'Aktif' : 'Nonaktif'}</span></label></div>
              <div className={base.fieldRow}><div className={base.fieldLeft}><span className={base.fieldLabel}>Email Tujuan</span><span className={base.fieldHint}>Alamat penerima forward</span></div><div className={styles.fieldControl}><input className={base.input} type="email" value={forwardForm.target} disabled={!forwardForm.enabled} onChange={(event) => setForwardForm((form) => ({ ...form, target: event.target.value }))} placeholder="tujuan@domain.com" /></div></div>
              <div className={base.fieldRow}><div className={base.fieldLeft}><span className={base.fieldLabel}>Simpan Salinan</span><span className={base.fieldHint}>Tetap simpan di mailbox ini</span></div><label className={base.switchRow}><input type="checkbox" checked={forwardForm.keepCopy} disabled={!forwardForm.enabled} onChange={(event) => setForwardForm((form) => ({ ...form, keepCopy: event.target.checked }))} /><span>{forwardForm.keepCopy ? 'Ya' : 'Tidak'}</span></label></div>
            </> : <>
              <div className={base.fieldRow}><div className={base.fieldLeft}><span className={base.fieldLabel}>Password</span><span className={base.fieldHint}>8+ karakter, huruf besar/kecil, angka, simbol</span></div><div className={`${styles.fieldControl} ${styles.passwordField}`}><input className={base.input} type={showPassword ? 'text' : 'password'} value={currentPassword} onChange={(event) => updatePassword(event.target.value)} autoComplete="new-password" /><button type="button" aria-label="Tampilkan password" onClick={() => setShowPassword((value) => !value)}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></div></div>
              <div className={base.fieldRow}><div className={base.fieldLeft}><span className={base.fieldLabel}>Konfirmasi Password</span></div><div className={styles.fieldControl}><input className={base.input} type={showPassword ? 'text' : 'password'} value={currentConfirm} onChange={(event) => updateConfirm(event.target.value)} autoComplete="new-password" /></div></div>
            </>}
          </div>
          <div className={base.editModalFooter}><button onClick={closeModal} className={base.cancelBtn}>Batal</button><button onClick={submitModal} disabled={saving} className={base.saveBtn}>{saving ? 'Menyimpan...' : submitLabel}</button></div>
        </div>
      </div>}
      <ConfirmDialog
        open={Boolean(confirmAction)}
        title={confirmation?.title}
        message={confirmation?.message}
        detail={confirmAction?.mailbox?.email}
        confirmText={confirmation?.confirmText}
        cancelText="Batal"
        busy={actionSaving}
        icon={confirmation?.icon}
        tone={confirmation?.tone}
        onConfirm={applyMailboxAction}
        onCancel={() => !actionSaving && setConfirmAction(null)}
      />
    </div>
  )
}
