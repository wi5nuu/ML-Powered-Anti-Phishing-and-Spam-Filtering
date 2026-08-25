// Pre-validasi lampiran sebelum unggah. Server (api_send_email /
// api_save_email_draft) tetap otoritatif; ini hanya mencegah pengguna
// mengunggah file besar/bahaya lalu ditolak dengan 413/400.

export const MAX_ATTACHMENT_MB = 25
export const MAX_ATTACHMENTS = 20

const BLOCKED_ATTACHMENT_EXT = /\.(exe|scr|bat|cmd|com|pif|vbs|js|jar|ps1|hta|msi|dll|docm|xlsm|pptm)$/i

/**
 * Saring daftar File baru terhadap batas ukuran/tipe/jumlah.
 * @param {File[]} incoming   file yang baru dipilih
 * @param {File[]} existing   lampiran yang sudah ada di draft
 * @param {(key:string)=>string} t  fungsi terjemahan (opsional)
 * @returns {{accepted: File[], errors: string[]}}
 */
export function filterAttachments(incoming, existing = [], t = (k) => k) {
  const accepted = []
  const errors = []
  for (const file of incoming || []) {
    if (file.size > MAX_ATTACHMENT_MB * 1024 * 1024) {
      errors.push(`${file.name} (> ${MAX_ATTACHMENT_MB} MB)`)
      continue
    }
    if (BLOCKED_ATTACHMENT_EXT.test(file.name)) {
      errors.push(`${file.name} (${t('compose.attachmentBlockedType')})`)
      continue
    }
    if (existing.length + accepted.length >= MAX_ATTACHMENTS) {
      errors.push(`${file.name} (${t('compose.attachmentTooMany') || `maks ${MAX_ATTACHMENTS} lampiran`})`)
      continue
    }
    const duplicate = existing.some(
      (item) => item.name === file.name && item.size === file.size && (item.lastModified || '') === (file.lastModified || '')
    )
    if (!duplicate) accepted.push(file)
  }
  return { accepted, errors }
}
