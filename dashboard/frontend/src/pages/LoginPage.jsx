import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useLogin, useMe } from '../api/auth'
import api from '../api/client'
import { ArrowLeft, Eye, EyeOff, KeyRound, Mail } from 'lucide-react'
import styles from './LoginPage.module.css'

export default function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
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
  }, [searchParams])

  const dashboardPathForRole = (role) => {
    if (role === 'superadmin') return '/super-admin/dashboard'
    if (role === 'admin') return '/admin/dashboard'
    return '/user/dashboard'
  }

  useEffect(() => {
    if (!me?.authenticated) return
    navigate(dashboardPathForRole(me.user?.role), { replace: true })
  }, [me, navigate])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const res = await login({ username, password })
      const meRes = await api.get('/auth/me').catch(() => null)
      const role = meRes?.data?.user?.role || res?.data?.role || res?.data?.user?.role
      window.location.replace(dashboardPathForRole(role))
    } catch (err) {
      setError(err.response?.data?.detail || 'Login gagal. Periksa username dan password Anda.')
    }
  }

  const handleForgotPassword = (e) => {
    e.preventDefault()
    setError('')
    setResetMessage('')
    if (!resetIdentity.trim()) {
      setError('Masukkan username atau email akun Anda.')
      return
    }
    setResetMessage(
      'Permintaan reset password diterima. Hubungi Admin atau Superadmin untuk dibuatkan password baru melalui Admin Panel.'
    )
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

        <h1 className={styles.title}>{mode === 'login' ? 'Masuk ke Dashboard' : 'Lupa Password'}</h1>
        <p className={styles.subtitle}>
          {mode === 'login'
            ? 'Gunakan akun organisasi yang sudah terdaftar.'
            : 'Masukkan username atau email untuk meminta reset password.'}
        </p>

        {error && <div className={styles.error}>{error}</div>}
        {resetMessage && <div className={styles.success}>{resetMessage}</div>}

        {mode === 'login' ? (
          <form onSubmit={handleSubmit} className={styles.form}>
            <div className={styles.field}>
              <label htmlFor="username">Email atau Username</label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="super atau email@company.com"
                required
                autoFocus
                autoComplete="username"
              />
            </div>

            <div className={styles.field}>
              <div className={styles.labelRow}>
                <label htmlFor="password">Password</label>
                <button type="button" className={styles.linkBtn} onClick={() => { setMode('forgot'); setError(''); setResetMessage('') }}>
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
                />
                <button type="button" className={styles.eyeBtn} onClick={() => setShowPwd((v) => !v)}>
                  {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <button type="submit" className={styles.submitBtn} disabled={isPending}>
              {isPending ? (
                <span className={styles.spinner} />
              ) : (
                <Mail size={18} />
              )}
              {isPending ? 'Memproses...' : 'Masuk'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleForgotPassword} className={styles.form}>
            <div className={styles.field}>
              <label htmlFor="resetIdentity">Username atau Email</label>
              <input
                id="resetIdentity"
                type="text"
                value={resetIdentity}
                onChange={(e) => setResetIdentity(e.target.value)}
                placeholder="super atau email@company.com"
                required
                autoFocus
                autoComplete="username"
              />
            </div>
            <button type="submit" className={styles.submitBtn}>
              <KeyRound size={18} />
              Minta Reset Password
            </button>
            <button
              type="button"
              className={styles.backBtn}
              onClick={() => { setMode('login'); setError(''); setResetMessage('') }}
            >
              <ArrowLeft size={16} />
              Kembali ke login
            </button>
          </form>
        )}

        <div className={styles.footer}>
          <p>ML-Powered Email Security & Spam Filtering</p>
        </div>
      </div>
    </div>
  )
}
