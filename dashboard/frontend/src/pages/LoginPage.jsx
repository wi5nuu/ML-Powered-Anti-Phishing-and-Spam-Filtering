import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useLogin, useMe } from '../api/auth'
import api from '../api/client'
import { ArrowLeft, Eye, EyeOff, KeyRound, Lock, Shield, ShieldCheck, Zap, Bell } from 'lucide-react'
import { setMailboxSession } from '../utils/mailbox'
import { useTranslation } from '../i18n/context'
import logoImg from '../assets/logo.png'
import styles from './LoginPage.module.css'

export default function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const sessionExpired = searchParams.get('expired') === '1'
  const { mutateAsync: login, isPending } = useLogin()
  const { data: me } = useMe()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [error, setError] = useState('')
  const [mode, setMode] = useState('login')
  const [resetIdentity, setResetIdentity] = useState('')
  const [resetMessage, setResetMessage] = useState('')
  const { t } = useTranslation()

  useEffect(() => {
    const err = searchParams.get('error')
    if (err) setError(decodeURIComponent(err))
    else if (sessionExpired) setError(t('login.sessionExpired'))
  }, [searchParams, sessionExpired, t])

  const dashboardPathForRole = (role) => {
    if (role === 'superadmin') return '/super-admin/dashboard'
    if (role === 'admin') return '/admin/dashboard'
    if (role === 'user') return '/user/mailboxes'
    return '/login'
  }

  const mailboxPathForUser = async () => {
    try {
      // Always use the user's own email as mailbox identity
      const meRes = await api.get('/auth/me').catch(() => null)
      const userEmail = meRes?.data?.user?.email
      if (userEmail && userEmail.includes('@')) {
        setMailboxSession({ id: userEmail, email: userEmail, login_source: 'main_login' })
        return `/mail/${encodeURIComponent(userEmail)}/inbox`
      }
      // Fallback to mailboxes list
      const { data } = await api.get('/user/mailboxes')
      const rows = Array.isArray(data) ? data : []
      const firstMailbox = rows[0]
      const mailboxKey = firstMailbox?.email || firstMailbox?.id
      if (mailboxKey) {
        setMailboxSession({ ...firstMailbox, id: mailboxKey, email: firstMailbox?.email || mailboxKey, login_source: 'main_login' })
        return `/mail/${encodeURIComponent(mailboxKey)}/inbox`
      }
    } catch {
    }
    return '/user/mailboxes'
  }

  const postLoginPathForRole = async (role) => {
    if (role === 'user') return mailboxPathForUser()
    return dashboardPathForRole(role)
  }

  useEffect(() => {
    if (!me?.authenticated) return
    let cancelled = false
    const role = me.user?.role
    if (role === 'mailbox') {
      navigate('/mailbox-login', { replace: true })
      return
    }
    postLoginPathForRole(role).then((target) => {
      if (!cancelled) navigate(target, { replace: true })
    })
    return () => { cancelled = true }
  }, [me, navigate])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const res = await login({ username, password })
      if (res?.data?.role === 'mailbox') {
        const mailbox = res.data.mailbox || {
          id: res.data.mailbox_id || res.data.username,
          email: res.data.mailbox_email || res.data.username,
        }
        setMailboxSession({ ...mailbox, login_source: 'main_login' })
        const mailboxId = mailbox.id || mailbox.email
        window.location.replace(`/mail/${encodeURIComponent(mailboxId)}/inbox`)
        return
      }
      const meRes = await api.get('/auth/me').catch(() => null)
      const role = meRes?.data?.user?.role || res?.data?.role || res?.data?.user?.role
      window.location.replace(await postLoginPathForRole(role))
    } catch (err) {
      setError(err.response?.data?.detail || t('login.error'))
    }
  }

  const handleForgotPassword = (e) => {
    e.preventDefault()
    setError('')
    setResetMessage('')
    if (!resetIdentity.trim()) {
      setError(t('login.resetRequired'))
      return
    }
    setResetMessage(t('login.resetMessage'))
  }

  return (
    <div className={styles.page}>

      {/* ── Left panel — branding ── */}
      <div className={styles.left}>
        <div className={styles.leftDecor1} />
        <div className={styles.leftDecor2} />
        <div className={styles.leftDecor3} />

        {/* Hero */}
        <div className={styles.leftHero}>
          <h2 className={styles.leftTagline}>
            {t('login.heroTitle')}
          </h2>
          <p className={styles.leftTaglineSub}>
            {t('login.heroSubtitle')}
          </p>
          <div className={styles.leftFeatures}>
            {[
              { icon: <ShieldCheck size={15} />, text: t('login.feature1text') },
              { icon: <Zap size={15} />, text: t('login.feature2text') },
              { icon: <Bell size={15} />, text: t('login.feature3text') },
            ].map((f, i) => (
              <div key={i} className={styles.leftFeatureItem}>
                <div className={styles.leftFeatureDot}>{f.icon}</div>
                <span className={styles.leftFeatureText}>{f.text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Footer badges */}
        <div className={styles.leftFooter}>
          <span className={styles.leftFooterBadge}>
            <Shield size={11} /> {t('login.mlPowered')}
          </span>
          <span className={styles.leftFooterBadge}>
            <Lock size={11} /> {t('login.e2eEncrypted')}
          </span>
        </div>
      </div>

      {/* ── Right panel — form ── */}
      <div className={styles.right}>

        {/* Brand — sudut kanan atas */}
        <div className={styles.rightBrand}>
          <img src={logoImg} alt="CogniMail" style={{ width: 32, height: 32, objectFit: 'contain' }} />
          <div>
            <div className={styles.rightBrandName}>CogniMail</div>
            <div className={styles.rightBrandSub}>{t('login.brandSub')}</div>
          </div>
        </div>

        <div className={styles.rightInner}>

        <div className={styles.titleBlock}>
          <h1 className={styles.title}>
            {mode === 'login' ? t('login.title') : t('login.forgotTitle')}
          </h1>
          <p className={styles.subtitle}>
            {mode === 'login'
              ? t('login.subtitle')
              : t('login.forgotSubtitle')}
          </p>
        </div>

        {error && (
          <div className={styles.alert}>
            <span className={styles.alertIcon}>!</span>
            <span>{error}</span>
          </div>
        )}
        {resetMessage && (
          <div className={styles.alertSuccess}>
            <span className={styles.alertIcon}>✓</span>
            <span>{resetMessage}</span>
          </div>
        )}

        {mode === 'login' ? (
          <form onSubmit={handleSubmit} className={styles.form}>
            <div className={styles.field}>
              <label htmlFor="username" className={styles.fieldLabel}>
                {t('login.email')}
              </label>
              <div className={styles.inputWrap}>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={t('login.emailPlaceholder')}
                  required
                  autoFocus
                  autoComplete="username"
                  className={styles.input}
                />
              </div>
            </div>

            <div className={styles.field}>
              <div className={styles.labelRow}>
                <label htmlFor="password" className={styles.fieldLabel}>{t('login.password')}</label>
                <button
                  type="button"
                  className={styles.forgotBtn}
                  onClick={() => { setMode('forgot'); setError(''); setResetMessage('') }}
                >
                  {t('login.forgotPassword')}
                </button>
              </div>
              <div className={styles.pwdWrap}>
                <input
                  id="password"
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t('login.passwordPlaceholder')}
                  required
                  autoComplete="current-password"
                  className={styles.input}
                />
                <button
                  type="button"
                  className={styles.eyeBtn}
                  onClick={() => setShowPwd((v) => !v)}
                  tabIndex={-1}
                >
                  {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <button type="submit" className={styles.submitBtn} disabled={isPending}>
              {isPending ? <span className={styles.spinner} /> : <Lock size={17} />}
              {isPending ? t('login.processing') : t('login.btn')}
            </button>
          </form>
        ) : (
          <form onSubmit={handleForgotPassword} className={styles.form}>
            <div className={styles.field}>
              <label htmlFor="resetIdentity" className={styles.fieldLabel}>
                {t('login.resetIdentity')}
              </label>
              <div className={styles.inputWrap}>
                <input
                  id="resetIdentity"
                  type="text"
                  value={resetIdentity}
                  onChange={(e) => setResetIdentity(e.target.value)}
                  placeholder={t('login.resetPlaceholder')}
                  required
                  autoFocus
                  autoComplete="username"
                  className={styles.input}
                />
              </div>
            </div>
            <button type="submit" className={styles.submitBtn}>
              <KeyRound size={17} />
              {t('login.resetBtn')}
            </button>
            <button
              type="button"
              className={styles.backBtn}
              onClick={() => { setMode('login'); setError(''); setResetMessage('') }}
            >
              <ArrowLeft size={16} />
              {t('login.backToLogin')}
            </button>
          </form>
        )}

        <div className={styles.footer}>
          <div className={styles.footerBadges}>
            <span className={styles.footerBadge}>
              <Shield size={11} /> {t('login.mlPowered')}
            </span>
            <span className={styles.footerBadge}>
              <Lock size={11} /> {t('login.e2eEncrypted')}
            </span>
          </div>
          <p className={styles.footerNote}>{t('login.footerNote')}</p>
        </div>

        </div>{/* end rightInner */}
      </div>
    </div>
  )
}
