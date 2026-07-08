import axios from 'axios'
import { MAILBOX_SESSION_PREFIX } from '../utils/mailbox'

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

function clearMailboxSessions() {
  try {
    Object.keys(localStorage)
      .filter((key) => key.startsWith(MAILBOX_SESSION_PREFIX))
      .forEach((key) => localStorage.removeItem(key))
  } catch {
    // Ignore localStorage failures.
  }
}

function expiredLoginTarget() {
  const path = window.location.pathname || ''
  const mailboxMatch = path.match(/^\/mail\/([^/]+)/)
  if (mailboxMatch?.[1]) {
    const params = new URLSearchParams(window.location.search || '')
    params.set('expired', '1')
    return `${path}?${params.toString()}`
  }
  return '/login?expired=1'
}

function redirectExpiredSession() {
  if (typeof window === 'undefined') return
  const path = window.location.pathname || ''
  const params = new URLSearchParams(window.location.search || '')
  if (path === '/login' || path === '/mailbox-login' || /^\/mail\/[^/]+\/login$/.test(path)) return
  if (params.get('expired') === '1') return

  const isMailboxPath = /^\/mail\/[^/]+/.test(path)
  if (isMailboxPath) {
    // For mailbox paths: only clear the mailbox localStorage session.
    // Do NOT clear dashboard sessions — dashboard user may still be logged in.
    const mailboxMatch = path.match(/^\/mail\/([^/]+)/)
    const mailboxId = mailboxMatch?.[1] ? decodeURIComponent(mailboxMatch[1]) : ''
    try {
      const key = `${MAILBOX_SESSION_PREFIX}${mailboxId || 'default'}`
      localStorage.removeItem(key)
    } catch {
      // Ignore.
    }
  } else {
    // For dashboard paths: clear all mailbox sessions on dashboard auth expiry.
    clearMailboxSessions()
  }

  window.location.replace(expiredLoginTarget())
}

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      const url = err.config?.url || ''
      const isLoginRequest = url.includes('/auth/login') || url.includes('/mailboxes/login')
      if (!isLoginRequest) redirectExpiredSession()
    }
    return Promise.reject(err)
  }
)

export default api
