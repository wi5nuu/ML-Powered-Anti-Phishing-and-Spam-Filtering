export const MAILBOX_STORAGE_KEY = 'cognimail.admin.mailboxes'
export const MAILBOX_DIRECTORY_KEY = 'cognimail.admin.mailboxDirectory'
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

export function getMailboxDirectory() {
  try {
    return JSON.parse(localStorage.getItem(MAILBOX_DIRECTORY_KEY) || '[]')
  } catch {
    return []
  }
}

export function setMailboxDirectory(mailboxes) {
  const rows = Array.isArray(mailboxes) ? mailboxes : []
  const normalized = rows
    .map((mailbox) => ({
      id: String(mailbox?.id || mailbox?.mailbox_id || mailbox?.email || ''),
      email: String(mailbox?.email || ''),
    }))
    .filter((mailbox) => mailbox.id && mailbox.email)
  localStorage.setItem(MAILBOX_DIRECTORY_KEY, JSON.stringify(normalized))
}

export function getMailboxById(mailboxId) {
  const id = String(mailboxId || '')
  if (!id) return null
  return getMailboxDirectory().find((mailbox) => String(mailbox.id) === id) || null
}

export function getMailboxIdByEmail(email) {
  const target = String(email || '').toLowerCase()
  if (!target) return ''
  return getMailboxDirectory().find((mailbox) => String(mailbox.email || '').toLowerCase() === target)?.id || ''
}

export function getActiveMailbox(searchParams) {
  const mailbox = searchParams?.get('mailbox') || ''
  if (mailbox) return mailbox

  const mailboxId = getActiveMailboxId(searchParams)
  if (!mailboxId) return ''

  const session = getMailboxSession(mailboxId)
  if (session?.email) return session.email

  return getMailboxById(mailboxId)?.email || ''
}

export function getActiveMailboxId(searchParams) {
  const fromQuery = searchParams?.get('mailbox_id') || ''
  if (fromQuery) return fromQuery
  try {
    const match = window.location.pathname.match(/^\/mail\/([^/]+)/)
    return match?.[1] ? decodeURIComponent(match[1]) : ''
  } catch {
    return ''
  }
}

export function mailboxSessionKey(mailboxId, email) {
  return `${MAILBOX_SESSION_PREFIX}${mailboxId || email || 'default'}`
}

function mailboxSessionKeys(mailboxId, email) {
  const keys = [mailboxSessionKey(mailboxId, email)]
  const id = String(mailboxId || '').trim()
  const targetEmail = String(email || '').trim().toLowerCase()

  if (id && targetEmail) {
    keys.push(mailboxSessionKey(targetEmail, targetEmail))
  }

  return Array.from(new Set(keys.filter(Boolean)))
}

export function setMailboxSession(mailbox) {
  if (!mailbox?.email) return
  const session = {
    id: String(mailbox.id || mailbox.mailbox_id || mailbox.email),
    email: mailbox.email,
    createdAt: Date.now(),
  }
  mailboxSessionKeys(session.id, session.email).forEach((key) => {
    localStorage.setItem(key, JSON.stringify(session))
  })
  const directory = getMailboxDirectory()
  const next = directory.filter((item) => String(item.id) !== session.id)
  next.push({ id: session.id, email: session.email })
  localStorage.setItem(MAILBOX_DIRECTORY_KEY, JSON.stringify(next))
}

export function getMailboxSession(mailboxId, email) {
  try {
    for (const key of mailboxSessionKeys(mailboxId, email)) {
      const raw = localStorage.getItem(key)
      if (!raw) continue
      const session = JSON.parse(raw)
      if (email && session.email !== email) continue
      return session
    }
    return null
  } catch {
    return null
  }
}

export function clearMailboxSession(mailboxId, email) {
  try {
    mailboxSessionKeys(mailboxId, email).forEach((key) => localStorage.removeItem(key))
  } catch {
    // Ignore localStorage failures; navigation can still proceed.
  }
}

export function hasMailboxSessionFromSearch(searchParams) {
  const mailbox = getActiveMailbox(searchParams)
  const mailboxId = getActiveMailboxId(searchParams)
  if (mailboxId && getMailboxSession(mailboxId)) return true
  if (mailbox && getMailboxSession(mailboxId || mailbox, mailbox)) return true

  const from = searchParams?.get('from') || ''
  if (!from) return false
  const fromParams = new URLSearchParams(from.split('?')[1] || '')
  const fromMailbox = getActiveMailbox(fromParams)
  const fromMailboxId = getActiveMailboxId(fromParams)
  return Boolean(
    (fromMailboxId && getMailboxSession(fromMailboxId)) ||
    (fromMailbox && getMailboxSession(fromMailboxId || fromMailbox, fromMailbox))
  )
}

export function withMailbox(path, mailbox, mailboxId = '') {
  const id = mailboxId || getMailboxIdByEmail(mailbox)
  if (!id && !mailbox) return path
  if (id) {
    const [rawPath, rawQuery = ''] = path.split('?')
    const params = new URLSearchParams(rawQuery)
    params.delete('mailbox')
    params.delete('mailbox_id')

    let target = rawPath
    if (rawPath === '/inbox') {
      const folder = params.get('folder')
      const category = params.get('category')
      params.delete('folder')
      params.delete('category')
      if (folder === 'starred') target = '/starred'
      else if (folder === 'allmail' || folder === 'all') target = '/all'
      else if (folder === 'trash') target = '/trash'
      else if (category) target = `/${category}`
      else target = '/inbox'
    } else if (rawPath === '/draft') {
      target = '/drafts'
    }

    const cleanPath = `/mail/${encodeURIComponent(id)}${target}`
    const query = params.toString()
    return query ? `${cleanPath}?${query}` : cleanPath
  }
  const separator = path.includes('?') ? '&' : '?'
  return `${path}${separator}mailbox=${encodeURIComponent(mailbox)}`
}
