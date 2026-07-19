export const DEFAULT_AVATAR_URL = '/static/default-avatar.svg'

const AVATAR_COLORS = ['#7c3aed', '#2563eb', '#0891b2', '#059669', '#d97706', '#dc2626', '#9333ea', '#0f766e']

export function hasUploadedAvatar(avatarUrl = '') {
  const value = String(avatarUrl || '')
  return Boolean(value && value !== DEFAULT_AVATAR_URL)
}

export function avatarColor(value = '') {
  const source = String(value || 'account')
  let hash = 0
  for (let index = 0; index < source.length; index += 1) {
    hash = (hash * 31 + source.charCodeAt(index)) >>> 0
  }
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

export function avatarInitial(value = '') {
  const source = String(value || '?').trim()
  return (source[0] || '?').toUpperCase()
}

export function avatarText(value = '', length = 1) {
  const source = String(value || '?')
    .trim()
    .replace(/^[^@]*<([^>]+)>$/, '$1')
  const base = source.includes('@') ? source.split('@')[0] : source
  const clean = base.replace(/[^A-Za-z0-9]/g, '')
  const text = (clean || source || '?').slice(0, length)
  return text.toUpperCase()
}
