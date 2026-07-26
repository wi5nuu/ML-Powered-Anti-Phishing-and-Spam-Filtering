export function canonicalEmailCategory(category) {
  const normalized = String(category || '').trim().toLowerCase()
  return normalized === 'malware' ? 'phishing' : normalized
}

export function displayEmailCategory(category, label = '') {
  if (String(label || '').toUpperCase() === 'WARN') return 'warn'
  return canonicalEmailCategory(category) || String(label || '').toLowerCase()
}
