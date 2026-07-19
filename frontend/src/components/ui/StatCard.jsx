import styles from './StatCard.module.css'

export default function StatCard({ icon, value, label, sub, color = '#4F46E5', bg = '#EEF2FF', onClick }) {
  return (
    <div className={styles.card} onClick={onClick} style={onClick ? { cursor: 'pointer' } : undefined}>
      <div className={styles.iconWrap} style={{ background: bg, color }}>
        {icon}
      </div>
      <div className={styles.body}>
        <span className={styles.value}>{value ?? '—'}</span>
        <span className={styles.label}>{label}</span>
        {sub && <span className={styles.sub}>{sub}</span>}
      </div>
    </div>
  )
}
