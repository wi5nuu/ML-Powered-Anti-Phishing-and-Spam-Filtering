import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams, Link } from 'react-router-dom'
import { Check, Eye, EyeOff, LayoutDashboard } from 'lucide-react'
import api from '../api/client'
import { getMailboxById, getMailboxSession, setMailboxSession } from '../utils/mailbox'
import styles from './MailboxLoginPage.module.css'

export default function MailboxLoginPage() {
  const navigate = useNavigate()
  const { mailboxId: pathMailboxId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const mailboxId = pathMailboxId || searchParams.get('mailbox_id') || ''
  const sessionExpired = searchParams.get('expired') === '1'
  const directoryMailbox = getMailboxById(mailboxId)
  const initialEmail = searchParams.get('email') || directoryMailbox?.email || ''
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
      setError('Password is required')
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
        <section className={styles.loginPane}>
          <div className={styles.brand}>
            <svg width="42" height="42" viewBox="0 0 40 40" fill="none" aria-hidden="true">
              <circle cx="20" cy="20" r="20" fill="#f6f8fc" />
              <path d="M20 6L8 11v9c0 6.07 5.12 11.74 12 13 6.88-1.26 12-6.93 12-13v-9L20 6z" fill="#EA4335" />
              <path d="M20 6L8 11v9c0 6.07 5.12 11.74 12 13V6z" fill="#c5221f" />
              <path d="M16 20l3 3 6-6" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span>COGNIMAIL</span>
          </div>

          <form onSubmit={handleSubmit} className={styles.form}>
            <h1>Log in to CogniMail Mail</h1>
            <p className={styles.helper}>
              {sessionExpired
                ? 'Sesi mailbox sudah berakhir. Silakan masuk kembali.'
                : `Masuk ke email perusahaan${domain ? ` @${domain}` : ''}.`}
            </p>

            <label htmlFor="mailboxEmail">Email address</label>
            <input
              id="mailboxEmail"
              className={styles.input}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="support@zenime.my.id"
              required
              autoFocus={!email}
              autoComplete="username"
            />

            <label htmlFor="mailboxPassword">Password</label>
            <div className={styles.passwordWrap}>
              <input
                id="mailboxPassword"
                className={styles.input}
                type={showPwd ? 'text' : 'password'}
                value={password}
                onBlur={() => setPasswordTouched(true)}
                onChange={(e) => {
                  setPassword(e.target.value)
                  if (error === 'Password is required') setError('')
                }}
                required
                autoFocus={Boolean(email)}
                autoComplete="current-password"
              />
              <button
                type="button"
                className={styles.eyeButton}
                onClick={() => setShowPwd((v) => !v)}
                aria-label={showPwd ? 'Sembunyikan password' : 'Tampilkan password'}
              >
                {showPwd ? <EyeOff size={24} /> : <Eye size={24} />}
              </button>
            </div>

            {(error || passwordRequired) && (
              <div className={styles.error}>{error || 'Password is required'}</div>
            )}

            <button type="button" className={styles.forgotButton}>
              Forgot password?
            </button>

            <button type="submit" className={styles.submitButton} disabled={loading}>
              {loading ? 'Memproses...' : 'Login'}
            </button>

            <p className={styles.footerText}>
              Don't have an email account? <span>Contact your administrator.</span>
            </p>
          </form>

          <div className={styles.adminLink}>
            <LayoutDashboard size={15} />
            <span>Admin atau Superadmin?</span>
            <Link to="/login" className={styles.adminLinkAnchor}>Masuk ke Dashboard</Link>
          </div>
        </section>

        <section className={styles.infoPane}>
          <div className={styles.infoContent}>
            <h2>
              Email perusahaan,<br />
              <span>terlindungi otomatis</span>
            </h2>
            <p className={styles.lead}>
              Akses webmail bisnis dengan perlindungan phishing, spam, malware, dan karantina terintegrasi.
            </p>
            <ul className={styles.featureList}>
              <li><Check size={25} /> Gunakan mailbox resmi perusahaan ({email || 'nama@domainanda.com'})</li>
              <li><Check size={25} /> Email masuk dianalisis otomatis sebelum tampil di inbox</li>
              <li><Check size={25} /> Deteksi phishing, spam, malware, dan ancaman mencurigakan</li>
              <li><Check size={25} /> Kelola inbox, draft, balasan, lampiran, sampah, dan karantina</li>
              <li><Check size={25} /> Pesan berisiko dipisahkan agar pekerjaan tetap aman</li>
            </ul>
          </div>
          <div className={styles.rating}>
            <strong>Secure</strong>
            <span className={styles.stars}>★★★★★</span>
            <span>CogniMail protected mailbox</span>
          </div>
        </section>
      </main>
    </div>
  )
}
