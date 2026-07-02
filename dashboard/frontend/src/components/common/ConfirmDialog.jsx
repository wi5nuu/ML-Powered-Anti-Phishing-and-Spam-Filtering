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
}) {
  if (!open) return null

  return (
    <div className={styles.overlay} role="presentation" onClick={onCancel}>
      <div className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title" onClick={(e) => e.stopPropagation()}>
        <h2 id="confirm-dialog-title">{title}</h2>
        <p>{message}</p>
        <div className={styles.actions}>
          <button type="button" className={styles.cancelBtn} onClick={onCancel} disabled={busy}>
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
