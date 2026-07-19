import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useLogin, useMe } from '../api/auth'
import api from '../api/client'
<<<<<<< HEAD
import { ArrowLeft, Eye, EyeOff, KeyRound, Shield, Lock, Inbox } from 'lucide-react'
=======
import { ArrowLeft, Eye, EyeOff, KeyRound, Shield, Lock } from 'lucide-react'
import { setMailboxSession } from '../utils/mailbox'
>>>>>>> origin/mailbox
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

  useEffect(() => {
    const err = searchParams.get('error')
    if (err) setError(decodeURIComponent(err))
    else if (sessionExpired) setError('Sesi sudah berakhir. Silakan masuk kembali.')
  }, [searchParams, sessionExpired])

  const dashboardPathForRole = (role) => {
    if (role === 'superadmin') return '/super-admin/dashboard'
    if (role === 'admin') return '/admin/dashboard'
<<<<<<< HEAD
    return '/inbox'
=======
    if (role === 'user') return '/user/mailboxes'
    return '/login'
  }

  const mailboxPathForUser = async () => {
    try {
      const { data } = await api.get('/user/mailboxes')
      const rows = Array.isArray(data) ? data : []
      const firstMailbox = rows[0]
      const mailboxId = firstMailbox?.id || firstMailbox?.email
      if (mailboxId) return `/mail/${encodeURIComponent(mailboxId)}/inbox`
    } catch {
      // Fall back to the mailbox list; route guards still enforce permissions.
    }
    return '/user/mailboxes'
  }

  const postLoginPathForRole = async (role) => {
    if (role === 'user') return mailboxPathForUser()
    return dashboardPathForRole(role)
>>>>>>> origin/mailbox
  }

  useEffect(() => {
    if (!me?.authenticated) return
    if (me.user?.role === 'mailbox') return
    let cancelled = false
    postLoginPathForRole(me.user?.role).then((target) => {
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
      setError(err.response?.data?.detail || 'Login gagal. Periksa username dan password Anda.')
    }
  }

  const handleForgotPassword = (e) => {
    e.preventDefault()
    setError('')
    setResetMessage('')
    if (!resetIdentity.trim()) {
      setError('Masukkan username akun Anda.')
      return
    }
    setResetMessage(
      'Permintaan reset password diterima. Hubungi Admin atau Superadmin untuk dibuatkan password baru melalui Admin Panel.'
    )
  }

  return (
    <div className={styles.page}>
      <div className={styles.bgDecor1} />
      <div className={styles.bgDecor2} />
      <div className={styles.bgDecor3} />

      <div className={styles.card}>
        <div className={styles.brand}>
          <div className={styles.brandIcon}>
            <Shield size={22} strokeWidth={2.5} />
          </div>
          <div className={styles.brandText}>
            <span className={styles.brandName}>CogniMail</span>
            <span className={styles.brandSub}>Security Platform</span>
          </div>
        </div>

        <div className={styles.divider} />

        <div className={styles.titleBlock}>
          <h1 className={styles.title}>
            {mode === 'login' ? 'Selamat Datang' : 'Reset Password'}
          </h1>
          <p className={styles.subtitle}>
            {mode === 'login'
              ? 'Masuk dengan akun organisasi Anda yang telah terdaftar.'
              : 'Masukkan username untuk meminta reset password.'}
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
                Username atau Email
              </label>
              <div className={styles.inputWrap}>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="username atau email"
                  required
                  autoFocus
                  autoComplete="username"
                  className={styles.input}
                />
              </div>
            </div>

            <div className={styles.field}>
              <div className={styles.labelRow}>
                <label htmlFor="password" className={styles.fieldLabel}>Password</label>
                <button
                  type="button"
                  className={styles.forgotBtn}
                  onClick={() => { setMode('forgot'); setError(''); setResetMessage('') }}
                >
                  Lupa password?
                </button>
              </div>
              <div className={styles.pwdWrap}>
                <input
                  id="password"
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Masukkan password"
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
              {isPending ? (
                <span className={styles.spinner} />
              ) : (
                <Lock size={17} />
              )}
              {isPending ? 'Memproses...' : 'Masuk'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleForgotPassword} className={styles.form}>
            <div className={styles.field}>
              <label htmlFor="resetIdentity" className={styles.fieldLabel}>
                Username
              </label>
              <div className={styles.inputWrap}>
                <input
                  id="resetIdentity"
                  type="text"
                  value={resetIdentity}
                  onChange={(e) => setResetIdentity(e.target.value)}
                  placeholder="username"
                  required
                  autoFocus
                  autoComplete="username"
                  className={styles.input}
                />
              </div>
            </div>
            <button type="submit" className={styles.submitBtn}>
              <KeyRound size={17} />
              Minta Reset Password
            </button>
            <button
              type="button"
              className={styles.backBtn}
              onClick={() => { setMode('login'); setError(''); setResetMessage('') }}
            >
              <ArrowLeft size={16} />
              Kembali ke Login
            </button>
          </form>
        )}

        <div className={styles.footer}>
          <div className={styles.footerBadges}>
            <span className={styles.footerBadge}>
              <Shield size={12} />
              ML-Powered
            </span>
            <span className={styles.footerBadge}>
              <Lock size={12} />
              End-to-End Encrypted
            </span>
          </div>
          <p className={styles.footerNote}>ML-Powered Anti-Phishing &amp; Spam Filtering System</p>
        </div>
      </div>
    </div>
  )
}
