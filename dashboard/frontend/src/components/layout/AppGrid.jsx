import { useNavigate } from 'react-router-dom'
import { Pencil } from 'lucide-react'
import { useStats } from '../../api/metrics'
import styles from './AppGrid.module.css'

const USER_APPS = {
  user: {
    favorite: [
      { id: 'inbox', label: 'Kotak Masuk', path: '/inbox', bg: '#1a73e8', emoji: 'ðŸ“§', badgeKey: null },
      { id: 'allmail', label: 'Semua Email', path: '/inbox?folder=allmail', bg: '#43a047', emoji: 'Mail', badgeKey: null },
      { id: 'settings', label: 'Pengaturan', path: '/settings', bg: '#f29900', emoji: 'ðŸ”§', badgeKey: null },
    ],
    more: [
      { id: 'sent', label: 'Terkirim', path: '/sent', bg: '#00bcd4', emoji: 'ðŸ“¤', badgeKey: null },
    ],
  },
  admin: {
    favorite: [
      { id: 'admin-panel', label: 'Admin Panel', path: '/admin/dashboard', bg: '#1a73e8', emoji: '⚙️', badgeKey: null },
      { id: 'metrik', label: 'Metrik', path: '/metrics', bg: '#34a853', emoji: '📊', badgeKey: null },
      { id: 'settings', label: 'Pengaturan', path: '/settings', bg: '#f29900', emoji: '🔧', badgeKey: null },
      { id: 'laporan', label: 'Laporan', path: '/admin/dashboard?tab=reports', bg: '#9c27b0', emoji: '📄', badgeKey: null },
    ],
    more: [
      { id: 'inbox', label: 'Kotak Masuk', path: '/inbox', bg: '#1a73e8', emoji: '📧', badgeKey: null },
    ],
  },
  superadmin: {
    favorite: [
      { id: 'admin-panel', label: 'Superadmin Panel', path: '/super-admin/dashboard', bg: '#1a73e8', emoji: '⚙️', badgeKey: null },
      { id: 'users', label: 'Users', path: '/super-admin/dashboard?tab=users', bg: '#0d47a1', emoji: '👥', badgeKey: null },
      { id: 'metrik', label: 'Metrik', path: '/metrics', bg: '#34a853', emoji: '📊', badgeKey: null },
      { id: 'settings', label: 'Pengaturan', path: '/settings', bg: '#f29900', emoji: '🔧', badgeKey: null },
    ],
    more: [
      { id: 'laporan', label: 'Laporan', path: '/super-admin/dashboard?tab=reports', bg: '#9c27b0', emoji: '📄', badgeKey: null },
      { id: 'inbox', label: 'Kotak Masuk', path: '/inbox', bg: '#1a73e8', emoji: '📧', badgeKey: null },
    ],
  },
}

function AppItem({ app, stats, onClick }) {
  const badgeCount = app.badgeKey && stats ? stats[app.badgeKey] : 0

  return (
    <button
      className={styles.appItem}
      onClick={() => onClick(app)}
      title={app.label}
      id={`app-grid-${app.id}`}
    >
      {badgeCount > 0 && (
        <span className={styles.appBadge}>{badgeCount > 99 ? '99+' : badgeCount}</span>
      )}
      <div className={styles.appIconWrap} style={{ background: app.bg }}>
        <span style={{ fontSize: 26, lineHeight: 1 }}>{app.emoji}</span>
      </div>
      <span className={styles.appLabel}>{app.label}</span>
    </button>
  )
}

export default function AppGrid({ open, onClose, user }) {
  const navigate = useNavigate()
  const { data: stats } = useStats()

  if (!open) return null

  const role = user?.role || 'user'
  const roleKey = role === 'superadmin' ? 'superadmin' : role === 'admin' ? 'admin' : 'user'
  const apps = USER_APPS[roleKey] || USER_APPS.user

  const handleAppClick = (app) => {
    onClose()
    if (app.external) {
      window.open(app.external, '_blank', 'noopener,noreferrer')
    } else if (app.path) {
      navigate(app.path)
    }
  }

  return (
    <>
      <div className={styles.overlay} onClick={onClose} />
      <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.headerTitle}>Favorit Anda</span>
          <button className={styles.editBtn} title="Edit pintasan">
            <Pencil size={16} />
          </button>
        </div>

        <div className={styles.grid}>
          {apps.favorite.map((app) => (
            <AppItem key={app.id} app={app} stats={stats} onClick={handleAppClick} />
          ))}
        </div>

        <div className={styles.dividerLine} />

        <div className={styles.sectionLabel}>Lebih Banyak</div>
        <div className={styles.grid}>
          {apps.more.map((app) => (
            <AppItem key={app.id} app={app} stats={stats} onClick={handleAppClick} />
          ))}
        </div>

        <div className={styles.footer}>
          <div className={styles.footerInfo}>
            CogniMail Email Security System
          </div>
        </div>
      </div>
    </>
  )
}

