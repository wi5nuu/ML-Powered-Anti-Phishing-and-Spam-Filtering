import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams, Link } from 'react-router-dom'
import { Eye, EyeOff, LayoutDashboard } from 'lucide-react'
import api from '../api/client'
import { getMailboxById, getMailboxSession, setMailboxSession } from '../utils/mailbox'
import { avatarColor, avatarText, hasUploadedAvatar } from '../utils/avatar'
import styles from './MailboxLoginPage.module.css'

export default function MailboxLoginPage() {
  const navigate = useNavigate()
  const { mailboxId: pathMailboxId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const mailboxId = pathMailboxId || searchParams.get('mailbox_id') || ''
  const sessionExpired = searchParams.get('expired') === '1'
  const directoryMailbox = getMailboxById(mailboxId)
  const initialEmail = searchParams.get('email') || directoryMailbox?.email || ''
  const hasPresetEmail = Boolean(initialEmail)
  const [email, setEmail] = useState(initialEmail)
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [passwordTouched, setPasswordTouched] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const domain = useMemo(() => {
    const parts = email.split('@')
    return parts.length === 2 ? parts[1] : ''
  }, [email])

  useEffect(() => {
    setEmail(initialEmail)
  }, [initialEmail])

  useEffect(() => {
    if (sessionExpired) return
    if (!initialEmail) return
    const session = getMailboxSession(mailboxId || initialEmail, initialEmail)
    if (!session) return
    const id = encodeURIComponent(session.id || mailboxId || initialEmail)
    navigate(`/mail/${id}/inbox`, { replace: true })
  }, [initialEmail, mailboxId, navigate, sessionExpired])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setPasswordTouched(true)
    setError('')
    if (!password.trim()) {
      setError('Password wajib diisi')
      return
    }
    setLoading(true)
    try {
      const { data } = await api.post('/mailboxes/login', {
        mailbox_id: mailboxId,
        email: email.trim().toLowerCase(),
        password,
      })
      const mailbox = data.mailbox || data
      setMailboxSession(mailbox)
      const id = encodeURIComponent(mailbox.id || mailboxId || email)
      navigate(`/mail/${id}/inbox`, { replace: true })
    } catch (err) {
      setError(err.response?.data?.detail || 'Login mailbox gagal. Periksa email dan password mailbox.')
    } finally {
      setLoading(false)
    }
  }

  const passwordRequired = passwordTouched && !password.trim()

  return (
    <div className={styles.page}>
      <main className={styles.shell}>
        <section className={styles.card}>
          <div className={styles.identityPane}>
            <div className={styles.brandMark} aria-hidden="true">
              <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                <circle cx="20" cy="20" r="20" fill="#f6f8fc" />
                <path d="M20 6L8 11v9c0 6.07 5.12 11.74 12 13 6.88-1.26 12-6.93 12-13v-9L20 6z" fill="#EA4335" />
                <path d="M20 6L8 11v9c0 6.07 5.12 11.74 12 13V6z" fill="#c5221f" />
                <path d="M16 20l3 3 6-6" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span>CogniMail</span>
            </div>
            <h1>Masuk</h1>
            <p>
              {sessionExpired
                ? 'Sesi mailbox berakhir. Masuk kembali untuk melanjutkan.'
                : 'Gunakan mailbox perusahaan untuk membuka webmail.'}
            </p>
            {hasPresetEmail && email && (
              <div className={styles.accountChip}>
                <span
                  className={styles.accountAvatar}
                  style={!hasUploadedAvatar(directoryMailbox?.avatar_url) ? { background: avatarColor(email) } : undefined}
                >
                  {hasUploadedAvatar(directoryMailbox?.avatar_url) ? (
                    <img src={directoryMailbox.avatar_url} alt="" />
                  ) : (
                    avatarText(email, 1)
                  )}
                </span>
                <strong>{email}</strong>
              </div>
            )}
          </div>

          <form onSubmit={handleSubmit} className={styles.form}>
            {!hasPresetEmail && (
              <div className={styles.fieldGroup}>
                <label htmlFor="mailboxEmail">Email</label>
                <input
                  id="mailboxEmail"
                  className={styles.input}
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="nama@domainanda.com"
                  required
                  autoFocus
                  autoComplete="username"
                />
              </div>
            )}

            <div className={styles.fieldGroup}>
              <label htmlFor="mailboxPassword">Masukkan password</label>
              <div className={styles.passwordWrap}>
                <input
                  id="mailboxPassword"
                  className={styles.input}
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onBlur={() => setPasswordTouched(true)}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    if (error === 'Password wajib diisi') setError('')
                  }}
                  required
                  autoFocus={hasPresetEmail}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className={styles.eyeButton}
                  onClick={() => setShowPwd((v) => !v)}
                  aria-label={showPwd ? 'Sembunyikan password' : 'Tampilkan password'}
                >
                  {showPwd ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </div>
            </div>

            {(error || passwordRequired) && (
              <div className={styles.error}>{error || 'Password wajib diisi'}</div>
            )}

            <p className={styles.note}>
              {domain ? `Webmail domain @${domain} dilindungi oleh CogniMail.` : 'Webmail perusahaan dilindungi oleh CogniMail.'}
            </p>

            <div className={styles.actions}>
              <button type="button" className={styles.textButton}>
                Lupa password?
              </button>
              <button type="submit" className={styles.submitButton} disabled={loading}>
                {loading ? 'Memproses...' : 'Masuk'}
              </button>
            </div>
          </form>
        </section>

        <footer className={styles.footer}>
          <div className={styles.footerLinks}>
            <span>Indonesia</span>
            <button type="button">Bantuan</button>
            <button type="button">Privasi</button>
            <button type="button">Persyaratan</button>
          </div>
          <Link to="/login" className={styles.dashboardLink}>
            <LayoutDashboard size={15} />
            Masuk ke Dashboard
          </Link>
        </footer>
      </main>
    </div>
  )
}
