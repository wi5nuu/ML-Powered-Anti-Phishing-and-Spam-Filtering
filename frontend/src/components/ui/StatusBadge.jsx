import styles from './StatusBadge.module.css'

const STATUS = {
  active: { label: 'Active', color: '#059669', bg: '#ECFDF5' },
  inactive: { label: 'Inactive', color: '#DC2626', bg: '#FEF2F2' },
  healthy: { label: 'Healthy', color: '#059669', bg: '#ECFDF5' },
  warning: { label: 'Warning', color: '#D97706', bg: '#FFFBEB' },
  error: { label: 'Error', color: '#DC2626', bg: '#FEF2F2' },
  online: { label: 'Online', color: '#059669', bg: '#ECFDF5' },
  offline: { label: 'Offline', color: '#DC2626', bg: '#FEF2F2' },
  open: { label: 'Open', color: '#DC2626', bg: '#FEF2F2' },
  resolved: { label: 'Resolved', color: '#059669', bg: '#ECFDF5' },
  in_progress: { label: 'In Progress', color: '#2563EB', bg: '#EFF6FF' },
}

export default function StatusBadge({ status, label, color, bg }) {
  const def = STATUS[status] || {}
  return (
    <span
      className={styles.badge}
      style={{ background: bg || def.bg || '#F3F4F6', color: color || def.color || '#6B7280' }}
    >
      {label || def.label || status}
    </span>
  )
}
