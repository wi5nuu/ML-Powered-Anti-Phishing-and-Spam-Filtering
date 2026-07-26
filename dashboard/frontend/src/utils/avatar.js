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

export async function readAvatarDimensions(file) {
  // Decode the File directly when supported. This does not create a blob URL,
  // so it remains compatible with the application's restrictive img-src CSP.
  if (typeof globalThis.createImageBitmap === 'function') {
    const bitmap = await globalThis.createImageBitmap(file)
    try {
      return { width: bitmap.width, height: bitmap.height }
    } finally {
      bitmap.close?.()
    }
  }

  // Older browsers use a data URL, which is explicitly allowed by the CSP.
  const dataUrl = await new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(new Error('image-read-failed'))
    reader.readAsDataURL(file)
  })
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight })
    image.onerror = () => reject(new Error('image-decode-failed'))
    image.src = dataUrl
  })
}
