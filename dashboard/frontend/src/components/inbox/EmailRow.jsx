import { Star, AlertTriangle, ShieldAlert, Info } from 'lucide-react'
import { useDeleteEmail, useReleaseEmail } from '../../api/emails'
import { useMe } from '../../api/auth'
import { useToast } from '../../hooks/useToast'
import styles from './EmailRow.module.css'

const VERDICT_CONFIG = {
  quarantine: { icon: ShieldAlert, label: 'Karantina', cls: 'quarantine', severity: 'critical' },
  warn:       { icon: AlertTriangle, label: 'Peringatan', cls: 'warn', severity: 'high' },
  clean:      { icon: Info, label: 'Bersih', cls: 'clean', severity: 'low' },
}

function timeAgo(date) {
  const diff = Date.now() - new Date(date).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'baru saja'
  if (mins < 60) return `${mins} mnt lalu`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} jam lalu`
  const days = Math.floor(hrs / 24)
  if (days < 30) return `${days} hari lalu`
  return new Date(date).toLocaleDateString('id-ID')
}

export default function EmailRow({
  email,
  isRead,
  isSelected,
  onToggleSelect,
  isStarred,
  onToggleStar,
}) {
  const { mutateAsync: deleteEmail } = useDeleteEmail()
  const { mutateAsync: releaseEmail } = useReleaseEmail()
  const { showToast } = useToast()
  const { data: meData } = useMe()
  const role = meData?.user?.role || 'user'

  const verdict = (email.final_verdict || email.ensemble_verdict || 'clean').toLowerCase()
  const vc = VERDICT_CONFIG[verdict] || VERDICT_CONFIG.clean
  const Icon = vc.icon

  const handleRowClick = (e) => {
    if (e.target.closest(`.${styles.checkboxWrap}, .${styles.starBtn}, .${styles.quickBtn}`)) return
    const baseUrl = window.location.pathname.split('/')[1] === 'admin' ? '/admin' : ''
    window.location.href = `${baseUrl}/email/${email.email_id}`
  }

  const handleQuickDelete = async (e) => {
    e.stopPropagation()
    if (role !== 'superadmin' && role !== 'admin') {
      showToast('Hanya Admin yang dapat menghapus email', 'error')
      return
    }
    if (!window.confirm(`Hapus email "${email.subject || '(no subject)'}"?`)) return
    try {
      await deleteEmail(email.email_id)
      showToast('Email dihapus', 'success')
    } catch { showToast('Gagal menghapus', 'error') }
  }

  const handleQuickRelease = async (e) => {
    e.stopPropagation()
    try {
      await releaseEmail(email.email_id)
      showToast('Email dirilis ke inbox', 'success')
    } catch { showToast('Gagal melepas', 'error') }
  }

  const score = email.phishing_probability != null
    ? (email.phishing_probability * 100).toFixed(0)
    : null

  return (
    <div
      className={`${styles.row} ${isRead ? styles.read : ''} ${isSelected ? styles.selected : ''}`}
      onClick={handleRowClick}
    >
      <div className={styles.actions}>
        <div className={styles.checkboxWrap}>
          <input
            type="checkbox"
            checked={isSelected}
            onChange={() => onToggleSelect(email.id)}
            className={styles.checkbox}
          />
        </div>
        <button
          className={`${styles.starBtn} ${isStarred ? styles.starActive : ''}`}
          onClick={(e) => { e.stopPropagation(); onToggleStar(email.id) }}
          title={isStarred ? 'Batal penting' : 'Tandai penting'}
        >
          <Star size={15} fill={isStarred ? 'var(--star-color, #f2c94c)' : 'none'} />
        </button>
      </div>

      <div className={styles.senderCol}>
        <span className={styles.sender}>{email.sender_email || 'unknown'}</span>
      </div>

      <div className={styles.body}>
        <span className={styles.subject}>{email.subject || '(no subject)'}</span>
        <span className={styles.separator}>–</span>
        <span className={styles.preview}>
          {email.body_preview || email.body_text?.slice(0, 120) || ''}
        </span>
      </div>

      <div className={styles.metaCol}>
        {score != null && (
          <span className={`${styles.score} ${+score >= 70 ? styles.scoreHigh : +score >= 40 ? styles.scoreMid : styles.scoreLow}`}>
            {score}%
          </span>
        )}
        <span className={`${styles.badge} ${styles['threat-' + vc.cls]}`}>
          <Icon size={11} />
          {vc.label}
        </span>
      </div>

      <div className={styles.quickActions}>
        {verdict === 'quarantine' && (
          <button className={`${styles.quickBtn} ${styles.quickRelease}`} onClick={handleQuickRelease}>
            Rilis
          </button>
        )}
        {(role === 'superadmin' || role === 'admin') && (
          <button className={`${styles.quickBtn} ${styles.quickDelete}`} onClick={handleQuickDelete}>
            Hapus
          </button>
        )}
      </div>

      <span className={styles.time}>
        {timeAgo(email.timestamp || email.received_at)}
      </span>
    </div>
  )
}
