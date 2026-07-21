import { useEffect, useState } from 'react'
import { Mail, RefreshCw, ShieldCheck, AlertCircle, Plus, Eye, EyeOff, X, ArrowRight, LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'
import { useLogout } from '../api/auth'
import { useTranslation } from '../i18n/context'
import logoImg from '../assets/logo.png'
import { getMailDomain, setMailboxDirectory, setMailboxSession } from '../utils/mailbox'
import styles from './UserMailboxPage.module.css'

export default function UserMailboxPage() {
  const navigate = useNavigate()
  const { mutate: logout } = useLogout()
  const [mailboxes, setMailboxes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [addEmailOpen, setAddEmailOpen] = useState(false)
  const [addEmailAddress, setAddEmailAddress] = useState('')
  const [addEmailPassword, setAddEmailPassword] = useState('')
  const [showAddEmailPassword, setShowAddEmailPassword] = useState(false)
  const [mailDomain] = useState(() => getMailDomain())
  const { t } = useTranslation()

  const fetchMailboxes = async () => {
    setLoading(true)
    setError('')
    try {
      // Get user's own email first — this is the mailbox identity
      const meRes = await api.get('/auth/me').catch(() => null)
      const userEmail = meRes?.data?.user?.email

      if (userEmail && userEmail.includes('@')) {
        setMailboxSession({ id: userEmail, email: userEmail, login_source: 'main_login' })
        navigate(`/mail/${encodeURIComponent(userEmail)}/inbox`, { replace: true })
        return
      }

      // Fallback: try /user/mailboxes
      const { data } = await api.get('/user/mailboxes')
      const rows = Array.isArray(data) ? data : []
      setMailboxes(rows)
      setMailboxDirectory(rows)

      if (rows.length > 0) {
        const firstMailbox = rows[0]
        // Prefer email over integer id so backend filters by recipient_list correctly
        const mailboxKey = firstMailbox?.email || firstMailbox?.id
        if (mailboxKey) {
          setMailboxSession({ ...firstMailbox, id: mailboxKey, email: firstMailbox?.email || mailboxKey, login_source: 'main_login' })
          navigate(`/mail/${encodeURIComponent(mailboxKey)}/inbox`, { replace: true })
          return
        }
      }
    } catch (e) {
      setError(e.response?.data?.detail || t('userMailbox.loadError'))
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
    navigate(`/mail/${encodeURIComponent(mailboxId)}/inbox`)
  }

  const handleAddEmail = async () => {
    const localPart = addEmailAddress.trim().toLowerCase().replace(/@.*$/, '')
    const email = `${localPart}@${mailDomain}`
    if (!/^[a-z0-9._%+-]+$/i.test(localPart)) {
      setError(t('userMailbox.modalErrorValidation'))
      return
    }
    if (!addEmailPassword) {
      setError(t('userMailbox.modalErrorPassword'))
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
      setError(e.response?.data?.detail || t('userMailbox.modalErrorAdd'))
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.shell}>

        {/* Top bar */}
        <div className={styles.topbar}>
          <div className={styles.brand}>
            <img src={logoImg} alt="CogniMail" style={{ width: 32, height: 32, objectFit: 'contain' }} />
            <span className={styles.brandName}>CogniMail</span>
          </div>
          <button className={styles.logoutBtn} onClick={() => logout()} title={t('gmail.logout')}>
            <LogOut size={16} />
            <span>{t('gmail.logout')}</span>
          </button>
        </div>

        {/* Card */}
        <div className={styles.card}>
          {/* Left pane — identity */}
          <div className={styles.identityPane}>
            <h1>{t('userMailbox.title')}</h1>
            <p>
              {t('userMailbox.subtitle')}
            </p>

            <div className={styles.actions}>
              <button
                className={styles.secondaryBtn}
                onClick={fetchMailboxes}
                disabled={loading}
                title={t('userMailbox.refresh')}
              >
                <RefreshCw size={15} className={loading ? styles.spin : ''} />
                {t('userMailbox.refresh')}
              </button>
              <button
                className={styles.primaryBtn}
                onClick={() => { setAddEmailOpen(true); setError('') }}
              >
                <Plus size={15} />
                {t('userMailbox.add')}
              </button>
            </div>
          </div>

          {/* Right pane — mailbox list */}
          <div className={styles.listPane}>
            <div className={styles.listHeader}>
              <span className={styles.listTitle}>{t('userMailbox.listTitle')}</span>
              <span className={styles.listCount}>{t('userMailbox.listCount').replace('{count}', mailboxes.length)}</span>
            </div>

            {loading ? (
              <div className={styles.emptyState}>
                <RefreshCw size={18} className={styles.spin} />
                {t('userMailbox.loading')}
              </div>
            ) : error ? (
              <div className={styles.errorBox}>
                <AlertCircle size={18} />
                {error}
              </div>
            ) : mailboxes.length === 0 ? (
              <div className={styles.emptyState}>
                <Mail size={18} />
                {t('userMailbox.empty')}
                <button className={styles.inlineAddBtn} onClick={() => { setAddEmailOpen(true); setError('') }}>
                  <Plus size={14} /> {t('userMailbox.add')}
                </button>
              </div>
            ) : (
              <div className={styles.mailboxList}>
                {mailboxes.map((mb) => (
                  <button
                    key={mb.id || mb.email}
                    className={styles.mailboxRow}
                    onClick={() => openInbox(mb)}
                  >
                    <div className={styles.mailIcon}>
                      <Mail size={18} />
                    </div>
                    <div className={styles.mailBody}>
                      <strong>{mb.email}</strong>
                      <span>{mb.domain || mb.email?.split('@')[1]}</span>
                    </div>
                    <div className={styles.statusBadge}>
                      <ShieldCheck size={12} />
                      {t('label.active')}
                    </div>
                    <ArrowRight size={16} className={styles.arrowIcon} />
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <span>{t('userMailbox.footer')}</span>
        </div>
      </div>

      {/* Add email modal */}
      {addEmailOpen && (
        <div className={styles.modalOverlay} onClick={(e) => { if (e.target === e.currentTarget) setAddEmailOpen(false) }}>
          <div className={styles.modal}>
            <div className={styles.modalHeader}>
              <div>
                <h2>{t('userMailbox.modalTitle')}</h2>
                <p>{t('userMailbox.modalSubtitle')}</p>
              </div>
              <button className={styles.closeBtn} onClick={() => setAddEmailOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <label className={styles.modalLabel}>{t('userMailbox.modalEmailLabel')}</label>
            <div className={styles.splitEmailInput}>
              <input
                type="text"
                placeholder={t('userMailbox.modalEmailPlaceholder')}
                value={addEmailAddress}
                onChange={(e) => { setAddEmailAddress(e.target.value); setError('') }}
                onKeyDown={(e) => e.key === 'Enter' && handleAddEmail()}
              />
              <span>@{mailDomain}</span>
            </div>

            <label className={styles.modalLabel}>{t('userMailbox.modalPasswordLabel')}</label>
            <div className={styles.passwordInput}>
              <input
                type={showAddEmailPassword ? 'text' : 'password'}
                value={addEmailPassword}
                onChange={(e) => { setAddEmailPassword(e.target.value); setError('') }}
                onKeyDown={(e) => e.key === 'Enter' && handleAddEmail()}
                placeholder={t('userMailbox.modalPasswordPlaceholder')}
              />
              <button type="button" onClick={() => setShowAddEmailPassword((v) => !v)} title={t('userMailbox.modalPasswordView')}>
                {showAddEmailPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>

            {error && <div className={styles.formError}>{error}</div>}

            <div className={styles.modalActions}>
              <button className={styles.cancelBtn} onClick={() => setAddEmailOpen(false)}>{t('btn.cancel')}</button>
              <button
                className={styles.primaryBtn}
                disabled={!addEmailAddress.trim() || !addEmailPassword}
                onClick={handleAddEmail}
              >
                {t('userMailbox.modalConfirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
