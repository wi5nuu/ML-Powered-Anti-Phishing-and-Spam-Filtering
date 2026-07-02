import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, Mail } from 'lucide-react'
import api from '../api/client'
import { getMailboxSession, setMailboxSession } from '../utils/mailbox'
import styles from './LoginPage.module.css'

export default function MailboxLoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialEmail = searchParams.get('email') || ''
  const mailboxId = searchParams.get('mailbox_id') || ''
  const [email, setEmail] = useState(initialEmail)
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
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
    if (!initialEmail) return
    const session = getMailboxSession(mailboxId || initialEmail, initialEmail)
    if (!session) return
    const id = encodeURIComponent(session.id || mailboxId || initialEmail)
    const address = encodeURIComponent(session.email || initialEmail)
    navigate(`/inbox?mailbox_id=${id}&mailbox=${address}`, { replace: true })
  }, [initialEmail, mailboxId, navigate])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
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
      const address = encodeURIComponent(mailbox.email || email)
      navigate(`/inbox?mailbox_id=${id}&mailbox=${address}`, { replace: true })
    } catch (err) {
      setError(err.response?.data?.detail || 'Login mailbox gagal. Periksa email dan password mailbox.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.logoRow}>
          <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
            <circle cx="20" cy="20" r="20" fill="#f6f8fc"/>
            <path d="M20 6L8 11v9c0 6.07 5.12 11.74 12 13 6.88-1.26 12-6.93 12-13v-9L20 6z" fill="#EA4335"/>
            <path d="M20 6L8 11v9c0 6.07 5.12 11.74 12 13V6z" fill="#c5221f"/>
            <path d="M16 20l3 3 6-6" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span className={styles.logoText}>CogniMail</span>
        </div>

        <h1 className={styles.title}>Login Mailbox</h1>
        <p className={styles.subtitle}>
          Masuk ke dashboard email perusahaan{domain ? ` @${domain}` : ''}.
        </p>

        {error && <div className={styles.error}>{error}</div>}

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label htmlFor="mailboxEmail">Email address</label>
            <input
              id="mailboxEmail"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="support@zenime.my.id"
              required
              autoFocus={!email}
              autoComplete="username"
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="mailboxPassword">Password</label>
            <div className={styles.pwdWrap}>
              <input
                id="mailboxPassword"
                type={showPwd ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password mailbox"
                required
                autoFocus={Boolean(email)}
                autoComplete="current-password"
              />
              <button type="button" className={styles.eyeBtn} onClick={() => setShowPwd((v) => !v)}>
                {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          <button type="submit" className={styles.submitBtn} disabled={loading}>
            {loading ? <span className={styles.spinner} /> : <Mail size={18} />}
            {loading ? 'Memproses...' : 'Login'}
          </button>
        </form>

        <div className={styles.footer}>
          <p>Secure Business Mailbox</p>
        </div>
      </div>
    </div>
  )
}
