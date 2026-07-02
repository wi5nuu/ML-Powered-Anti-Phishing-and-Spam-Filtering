export const MAILBOX_STORAGE_KEY = 'cognimail.admin.mailboxes'
export const MAIL_DOMAIN_STORAGE_KEY = 'cognimail.admin.mailDomain'
export const MAILBOX_SESSION_PREFIX = 'cognimail.mailbox.session.'
export const DEFAULT_MAIL_DOMAIN = import.meta.env.VITE_MAIL_DOMAIN || 'zenime.my.id'

export function getMailDomain() {
  try {
    return localStorage.getItem(MAIL_DOMAIN_STORAGE_KEY) || DEFAULT_MAIL_DOMAIN
  } catch {
    return DEFAULT_MAIL_DOMAIN
  }
}

export function setMailDomain(domain) {
  const clean = String(domain || '')
    .trim()
    .toLowerCase()
    .replace(/^@+/, '')
  localStorage.setItem(MAIL_DOMAIN_STORAGE_KEY, clean)
  return clean
}

export function getMailboxes() {
  try {
    return JSON.parse(localStorage.getItem(MAILBOX_STORAGE_KEY) || '[]')
  } catch {
    return []
  }
}

export function setMailboxes(mailboxes) {
  localStorage.setItem(MAILBOX_STORAGE_KEY, JSON.stringify(mailboxes))
}

export function getActiveMailbox(searchParams) {
  return searchParams?.get('mailbox') || ''
}

export function getActiveMailboxId(searchParams) {
  return searchParams?.get('mailbox_id') || ''
}

export function mailboxSessionKey(mailboxId, email) {
  return `${MAILBOX_SESSION_PREFIX}${mailboxId || email || 'default'}`
}

export function setMailboxSession(mailbox) {
  if (!mailbox?.email) return
  const session = {
    id: String(mailbox.id || mailbox.mailbox_id || mailbox.email),
    email: mailbox.email,
    createdAt: Date.now(),
  }
  localStorage.setItem(mailboxSessionKey(session.id, session.email), JSON.stringify(session))
}

export function getMailboxSession(mailboxId, email) {
  const key = mailboxSessionKey(mailboxId, email)
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const session = JSON.parse(raw)
    if (email && session.email !== email) return null
    return session
  } catch {
    return null
  }
}

export function hasMailboxSessionFromSearch(searchParams) {
  const mailbox = getActiveMailbox(searchParams)
  const mailboxId = getActiveMailboxId(searchParams)
  if (mailbox && getMailboxSession(mailboxId || mailbox, mailbox)) return true

  const from = searchParams?.get('from') || ''
  if (!from) return false
  const fromParams = new URLSearchParams(from.split('?')[1] || '')
  const fromMailbox = getActiveMailbox(fromParams)
  const fromMailboxId = getActiveMailboxId(fromParams)
  return Boolean(fromMailbox && getMailboxSession(fromMailboxId || fromMailbox, fromMailbox))
}

export function withMailbox(path, mailbox, mailboxId = '') {
  if (!mailbox) return path
  const separator = path.includes('?') ? '&' : '?'
  const idPart = mailboxId ? `mailbox_id=${encodeURIComponent(mailboxId)}&` : ''
  return `${path}${separator}${idPart}mailbox=${encodeURIComponent(mailbox)}`
}
