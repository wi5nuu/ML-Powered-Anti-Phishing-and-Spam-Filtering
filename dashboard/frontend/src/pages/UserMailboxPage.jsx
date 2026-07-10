import { useEffect, useState } from 'react'
import { Inbox, Mail, ArrowRight, RefreshCw, ShieldCheck, AlertCircle, Plus, Eye, EyeOff, X } from 'lucide-react'
import api from '../api/client'
import UserDashboardShell from '../components/layout/UserDashboardShell'
import { getMailDomain, setMailboxDirectory } from '../utils/mailbox'
import styles from './UserMailboxPage.module.css'

export default function UserMailboxPage() {
  const [mailboxes, setMailboxes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [addEmailOpen, setAddEmailOpen] = useState(false)
  const [addEmailAddress, setAddEmailAddress] = useState('')
  const [addEmailPassword, setAddEmailPassword] = useState('')
  const [showAddEmailPassword, setShowAddEmailPassword] = useState(false)
  const [mailDomain] = useState(() => getMailDomain())

  const fetchMailboxes = async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await api.get('/user/mailboxes')
      const rows = Array.isArray(data) ? data : []
      setMailboxes(rows)
      setMailboxDirectory(rows)
    } catch (e) {
      setError(e.response?.data?.detail || 'Gagal memuat mailbox.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchMailboxes()
  }, [])

  const openInbox = (mailbox) => {
    const mailboxId = mailbox?.id || mailbox?.email
    if (!mailboxId) return
    window.open(`/mail/${encodeURIComponent(mailboxId)}/inbox`, '_blank', 'noopener,noreferrer')
  }

  const handleAddEmail = async () => {
    const localPart = addEmailAddress.trim().toLowerCase().replace(/@.*$/, '')
    const email = `${localPart}@${mailDomain}`
    if (!/^[a-z0-9._%+-]+$/i.test(localPart)) {
      setError('Masukkan nama email yang valid.')
      return
    }
    if (!addEmailPassword) {
      setError('Masukkan password email.')
      return
    }
    setError('')
    try {
      await api.post('/mailboxes/claim', {
        email,
        password: addEmailPassword,
      })
      await fetchMailboxes()
      setAddEmailAddress('')
      setAddEmailPassword('')
      setShowAddEmailPassword(false)
      setAddEmailOpen(false)
    } catch (e) {
      setError(e.response?.data?.detail || 'Gagal menambahkan email.')
    }
  }

  return (
    <UserDashboardShell>
      <div className={styles.wrap}>
        <section className={styles.hero}>
          <div className={styles.heroIcon}>
            <Mail size={24} />
          </div>
          <div>
            <h1>Mailbox</h1>
            <p>Pilih alamat email yang ingin dibuka. Setiap akun dapat memiliki lebih dari satu mailbox.</p>
          </div>
          <div className={styles.heroActions}>
            <button className={styles.secondaryBtn} onClick={fetchMailboxes} disabled={loading}>
              <RefreshCw size={16} />
              Refresh
            </button>
            <button className={styles.primaryBtn} onClick={() => { setAddEmailOpen(true); setError('') }}>
              <Plus size={16} />
              Add Email
            </button>
          </div>
        </section>

        {error && !addEmailOpen && (
          <div className={styles.errorBox}>
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <h2>Daftar mailbox</h2>
              <span>{loading ? 'Memuat mailbox...' : `${mailboxes.length} mailbox aktif`}</span>
            </div>
            <button className={styles.primaryBtn} onClick={() => { setAddEmailOpen(true); setError('') }}>
              <Plus size={16} />
              Add Email
            </button>
          </div>

          {loading ? (
            <div className={styles.emptyState}>Memuat mailbox...</div>
          ) : mailboxes.length === 0 ? (
            <div className={styles.emptyState}>
              Belum ada mailbox aktif untuk akun ini.
            </div>
          ) : (
            <div className={styles.mailboxList}>
              {mailboxes.map((mailbox) => (
                <article key={mailbox.id || mailbox.email} className={styles.mailboxRow}>
                  <div className={styles.mailIcon}>
                    <Inbox size={19} />
                  </div>
                  <div className={styles.mailBody}>
                    <strong>{mailbox.email}</strong>
                    <span>ID: {mailbox.id} - {mailbox.sender_name || 'Sender name belum diatur'}</span>
                  </div>
                  <div className={styles.statusBadge}>
                    <ShieldCheck size={14} />
                    Protected
                  </div>
                  <button className={styles.openBtn} onClick={() => openInbox(mailbox)}>
                    Buka mailbox
                    <ArrowRight size={16} />
                  </button>
                </article>
              ))}
            </div>
          )}
        </section>

        {addEmailOpen && (
          <div className={styles.modalOverlay} onClick={() => setAddEmailOpen(false)}>
            <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <div>
                  <h2>Add Email</h2>
                  <p>Tambahkan email yang sudah dibuat oleh admin atau superadmin.</p>
                </div>
                <button className={styles.closeBtn} onClick={() => setAddEmailOpen(false)}><X size={20} /></button>
              </div>
              <label className={styles.modalLabel}>Alamat email</label>
              <div className={styles.splitEmailInput}>
                <input
                  value={addEmailAddress}
                  onChange={(e) => { setAddEmailAddress(e.target.value.replace(/@.*$/, '')); setError('') }}
                  placeholder="nama"
                  autoFocus
                />
                <span>@{mailDomain}</span>
              </div>
              <label className={styles.modalLabel}>Password email</label>
              <div className={styles.passwordInput}>
                <input
                  type={showAddEmailPassword ? 'text' : 'password'}
                  value={addEmailPassword}
                  onChange={(e) => { setAddEmailPassword(e.target.value); setError('') }}
                  placeholder="Password email"
                />
                <button type="button" onClick={() => setShowAddEmailPassword((v) => !v)} title="Lihat password">
                  {showAddEmailPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {error && <div className={styles.formError}>{error}</div>}
              <div className={styles.modalActions}>
                <button className={styles.cancelBtn} onClick={() => setAddEmailOpen(false)}>Batal</button>
                <button className={styles.primaryBtn} disabled={!addEmailAddress.trim() || !addEmailPassword} onClick={handleAddEmail}>
                  Tambahkan Email
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </UserDashboardShell>
  )
}
