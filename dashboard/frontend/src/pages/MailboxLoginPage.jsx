import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams, Link } from 'react-router-dom'
import { Eye, EyeOff, LayoutDashboard } from 'lucide-react'
import api from '../api/client'
import { getMailboxById, getMailboxSession, setMailboxSession } from '../utils/mailbox'
import { avatarColor, avatarText, hasUploadedAvatar } from '../utils/avatar'
import { useTranslation } from '../i18n/context'
import logoImg from '../assets/logo.png'
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
  const { t } = useTranslation()

  // Auto-login jika ?autotoken= ada di URL (dari klik ikon mata di tabel admin)
  useEffect(() => {
    const autoToken = searchParams.get('autotoken')
    if (!autoToken) return
    // Bersihkan token dari address bar sebelum API call agar tidak terlihat
    const cleanUrl = window.location.pathname + (searchParams.get('email') ? `?email=${encodeURIComponent(searchParams.get('email'))}` : '')
    window.history.replaceState(null, '', cleanUrl)
    setLoading(true)
    api.post('/mailboxes/autologin', { token: autoToken })
      .then(({ data }) => {
        const mailbox = data.mailbox || data
        setMailboxSession(mailbox)
        const id = encodeURIComponent(mailbox.id || mailboxId || initialEmail)
        navigate(`/mail/${id}/inbox`, { replace: true })
      })
      .catch((err) => {
        setError(err.response?.data?.detail || t('mailboxLogin.autoLoginError'))
        setLoading(false)
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
    if (searchParams.get('autotoken')) return
    const session = getMailboxSession(mailboxId || initialEmail, initialEmail)
    if (!session) return
  }, [initialEmail, mailboxId, navigate, sessionExpired, searchParams])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setPasswordTouched(true)
    setError('')
    if (!password.trim()) {
      setError(t('mailboxLogin.passwordRequired'))
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
      // Mark session so logout redirects to main login page (not mailbox login)
      setMailboxSession({ ...mailbox, login_source: mailbox.user_mode ? 'main_login' : mailbox.login_source })
      // If the backend authenticated via User table (not AdminMailbox),
      // redirect to the user dashboard instead of webmail inbox.
      if (mailbox.user_mode) {
        navigate('/user/mailboxes', { replace: true })
        return
      }
      const id = encodeURIComponent(mailbox.id || mailboxId || email)
      navigate(`/mail/${id}/inbox`, { replace: true })
    } catch (err) {
      setError(err.response?.data?.detail || t('mailboxLogin.error'))
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
              <img src={logoImg} alt="CogniMail" style={{ width: 40, height: 40, objectFit: 'contain' }} />
              <span>CogniMail</span>
            </div>
            <h1>{t('mailboxLogin.title')}</h1>
            <p>
              {sessionExpired
                ? t('mailboxLogin.expiredMessage')
                : t('mailboxLogin.message')}
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
                <label htmlFor="mailboxEmail">{t('mailboxLogin.email')}</label>
                <input
                  id="mailboxEmail"
                  className={styles.input}
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={t('mailboxLogin.emailPlaceholder')}
                  required
                  autoFocus
                  autoComplete="username"
                />
              </div>
            )}

            <div className={styles.fieldGroup}>
              <label htmlFor="mailboxPassword">{t('mailboxLogin.password')}</label>
              <div className={styles.passwordWrap}>
                <input
                  id="mailboxPassword"
                  className={styles.input}
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onBlur={() => setPasswordTouched(true)}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    if (error === t('mailboxLogin.passwordRequired')) setError('')
                  }}
                  required
                  autoFocus={hasPresetEmail}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className={styles.eyeButton}
                  onClick={() => setShowPwd((v) => !v)}
                  aria-label={showPwd ? t('mailboxLogin.hidePassword') : t('mailboxLogin.showPassword')}
                >
                  {showPwd ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </div>
            </div>

            {(error || passwordRequired) && (
              <div className={styles.error}>{error || t('mailboxLogin.passwordRequired')}</div>
            )}

            <p className={styles.note}>
              {domain ? t('mailboxLogin.noteWithDomain').replace('{domain}', domain) : t('mailboxLogin.note')}
            </p>

            <div className={styles.actions}>
              <button type="submit" className={styles.submitButton} disabled={loading}>
                {loading ? t('login.processing') : t('mailboxLogin.btn')}
              </button>
            </div>
          </form>
        </section>

        <footer className={styles.footer}>
          <div className={styles.footerLinks}>
            <span>{t('mailboxLogin.lang')}</span>
            <button type="button">{t('mailboxLogin.help')}</button>
            <button type="button">{t('mailboxLogin.privacy')}</button>
            <button type="button">{t('mailboxLogin.terms')}</button>
          </div>
          <Link to="/login" className={styles.dashboardLink}>
            <LayoutDashboard size={15} />
            {t('mailboxLogin.goToDashboard')}
          </Link>
        </footer>
      </main>
    </div>
  )
}
