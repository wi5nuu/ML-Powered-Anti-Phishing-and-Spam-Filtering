import { useEffect, useRef } from 'react'
import { AlertTriangle, Info, X } from 'lucide-react'
import styles from './ConfirmDialog.module.css'

export default function ConfirmDialog({
  open,
  title = 'Konfirmasi',
  message,
  confirmText = 'Oke',
  cancelText = 'Batal',
  onConfirm,
  onCancel,
  busy = false,
  tone = 'danger',
  detail,
  icon,
}) {
  const cancelRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onKeyDown = (event) => {
      if (event.key === 'Escape' && !busy) onCancel?.()
    }
    document.addEventListener('keydown', onKeyDown)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.requestAnimationFrame(() => cancelRef.current?.focus())
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [open, busy, onCancel])

  if (!open) return null

  const Icon = icon || (tone === 'danger' ? AlertTriangle : Info)

  return (
    <div className={styles.overlay} role="presentation" onMouseDown={(event) => event.target === event.currentTarget && !busy && onCancel?.()}>
      <div className={`${styles.dialog} ${styles[tone] || ''}`} role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title" aria-describedby="confirm-dialog-message" onMouseDown={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 id="confirm-dialog-title"><Icon size={17} strokeWidth={2} />{title}</h2>
          <button type="button" className={styles.closeBtn} onClick={onCancel} disabled={busy} aria-label="Tutup dialog">
            <X size={17} />
          </button>
        </div>
        <div className={styles.content}>
          <p id="confirm-dialog-message">{message}</p>
          {detail && <div className={styles.detail}>{detail}</div>}
        </div>
        <div className={styles.actions}>
          <button ref={cancelRef} type="button" className={styles.cancelBtn} onClick={onCancel} disabled={busy}>
            {cancelText}
          </button>
          <button type="button" className={styles.confirmBtn} onClick={onConfirm} disabled={busy}>
            {busy ? 'Memproses...' : confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
