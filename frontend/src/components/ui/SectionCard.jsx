import styles from './SectionCard.module.css'

export default function SectionCard({ icon, title, badge, action, children }) {
  return (
    <div className={styles.card}>
      {(icon || title) && (
        <div className={styles.header}>
          {icon && <span className={styles.icon}>{icon}</span>}
          {title && <span className={styles.title}>{title}</span>}
          {badge && <span className={styles.badge}>{badge}</span>}
          {action && <span className={styles.action}>{action}</span>}
        </div>
      )}
      {children}
    </div>
  )
}
