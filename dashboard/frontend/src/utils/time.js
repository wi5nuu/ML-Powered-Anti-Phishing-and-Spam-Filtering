export const APP_TIME_ZONE = 'Asia/Jakarta'

export function appDate(value) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatAppTime(value, options = {}) {
  const date = appDate(value)
  if (!date) return ''
  return date.toLocaleTimeString('id-ID', {
    timeZone: APP_TIME_ZONE,
    ...options,
  })
}

export function formatAppDate(value, options = {}) {
  const date = appDate(value)
  if (!date) return ''
  return date.toLocaleDateString('id-ID', {
    timeZone: APP_TIME_ZONE,
    ...options,
  })
}

export function formatAppDateTime(value, options = {}) {
  const date = appDate(value)
  if (!date) return ''
  return date.toLocaleString('id-ID', {
    timeZone: APP_TIME_ZONE,
    ...options,
  })
}
