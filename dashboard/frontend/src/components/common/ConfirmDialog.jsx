import { AlertTriangle, LoaderCircle, X } from 'lucide-react'

export default function ConfirmDialog({
  open,
  title,
  message,
  detail,
  confirmLabel,
  cancelLabel,
  confirmText,
  cancelText,
  onConfirm,
  onCancel,
  danger = false,
  tone,
  busy = false,
  icon,
}) {
  if (!open) return null
  const resolvedConfirmLabel = confirmLabel || confirmText || 'Konfirmasi'
  const resolvedCancelLabel = cancelLabel || cancelText || 'Batal'
  const isDanger = danger || tone === 'danger'
  const DialogIcon = icon || AlertTriangle
  return (
    <div
      role="presentation"
      onClick={onCancel}
      style={{ position: 'fixed', inset: 0, zIndex: 1000, display: 'grid', placeItems: 'center', padding: 20, background: 'rgba(15,23,42,.45)' }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        onClick={(event) => event.stopPropagation()}
        style={{ width: 'min(420px, 100%)', borderRadius: 14, background: 'var(--surface, #fff)', boxShadow: '0 24px 60px rgba(15,23,42,.25)', padding: 22 }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          <span style={{ display: 'grid', placeItems: 'center', width: 34, height: 34, borderRadius: 10, color: isDanger ? '#b42318' : '#1a73e8', background: isDanger ? '#fef3f2' : '#e8f0fe' }}>
            <DialogIcon size={18} />
          </span>
          <div style={{ flex: 1 }}>
            <h2 id="confirm-dialog-title" style={{ margin: 0, fontSize: 16, color: 'var(--text, #172033)' }}>{title}</h2>
            <p style={{ margin: '8px 0 0', lineHeight: 1.5, fontSize: 13, color: 'var(--text-muted, #667085)' }}>{message}</p>
            {detail && <p style={{ margin: '8px 0 0', lineHeight: 1.5, fontSize: 12, fontWeight: 600, color: 'var(--text, #172033)', overflowWrap: 'anywhere' }}>{detail}</p>}
          </div>
          <button type="button" onClick={onCancel} disabled={busy} aria-label={resolvedCancelLabel} style={{ border: 0, background: 'transparent', color: 'var(--text-muted)', cursor: busy ? 'not-allowed' : 'pointer' }}>
            <X size={18} />
          </button>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 22 }}>
          <button type="button" onClick={onCancel} disabled={busy} style={{ padding: '9px 14px', borderRadius: 8, border: '1px solid var(--border, #d0d5dd)', background: 'transparent', color: 'var(--text, #172033)', cursor: busy ? 'not-allowed' : 'pointer', opacity: busy ? 0.65 : 1 }}>
            {resolvedCancelLabel}
          </button>
          <button type="button" onClick={onConfirm} disabled={busy} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '9px 14px', borderRadius: 8, border: 0, background: isDanger ? '#d92d20' : '#1a73e8', color: '#fff', cursor: busy ? 'not-allowed' : 'pointer', fontWeight: 600, opacity: busy ? 0.72 : 1 }}>
            {busy && <LoaderCircle size={15} aria-hidden="true" />}
            {resolvedConfirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
