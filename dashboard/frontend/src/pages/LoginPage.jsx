import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useLogin } from '../api/auth'
import { Eye, EyeOff, ShieldCheck, Mail } from 'lucide-react'
import styles from './LoginPage.module.css'

const DEMO_CREDENTIALS = [
  { user: 'superadmin', role: 'Super Admin' },
  { user: 'admin', role: 'Admin' },
  { user: 'reviewer', role: 'Reviewer' },
  { user: 'user', role: 'User' },
]

export default function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { mutate: login, isPending } = useLogin()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const err = searchParams.get('error')
    if (err) setError(decodeURIComponent(err))
  }, [searchParams])

  const handleSubmit = (e) => {
    e.preventDefault()
    setError('')
    login({ username, password }, {
      onSuccess: (res) => {
        const role = res?.data?.role
        if (role === 'superadmin' || role === 'admin') {
          navigate('/admin')
        } else {
          navigate('/inbox')
        }
      },
      onError: (err) => {
        setError(err.response?.data?.detail || 'Login gagal. Periksa username dan password Anda.')
      },
    })
  }

  const handleGoogleLogin = () => {
    window.location.href = '/auth/google/login'
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
          <span className={styles.logoText}>LTI <b>Anti-Phishing</b></span>
        </div>

        <h1 className={styles.title}>Masuk ke Dashboard</h1>
        <p className={styles.subtitle}>Gunakan akun demo berikut:</p>
        <div className={styles.credHint}>
          {DEMO_CREDENTIALS.map((c) => (
            <span key={c.user} className={styles.credBadge} onClick={() => { setUsername(c.user); setPassword(c.user === 'superadmin' ? 'SuperAdminPassword123!' : c.user === 'admin' ? 'AdminPassword123!' : c.user === 'reviewer' ? 'ReviewerPassword123!' : 'UserPassword123!') }}>
              {c.user}
            </span>
          ))}
        </div>

        {error && <div className={styles.error}>{error}</div>}

        {/* Google Sign-In Button */}
        <button className={styles.googleBtn} onClick={handleGoogleLogin}>
          <svg width="20" height="20" viewBox="0 0 48 48">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
            <path fill="#FBBC05" d="M10.53 28.59A14.5 14.5 0 0 1 9.5 24c0-1.59.28-3.14.76-4.59l-7.98-6.19A23.99 23.99 0 0 0 0 24c0 3.77.87 7.35 2.56 10.56l7.97-5.97z"/>
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 5.97C6.51 42.62 14.62 48 24 48z"/>
          </svg>
          Lanjutkan dengan Google
        </button>

        <div className={styles.divider}>
          <span>atau</span>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label htmlFor="username">Email atau Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="superadmin atau email@company.com"
              required
              autoFocus
              autoComplete="username"
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="password">Password</label>
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

        <div className={styles.footer}>
          <p>ML-Powered Anti-Phishing & Spam Filtering</p>
        </div>
      </div>
    </div>
  )
}
