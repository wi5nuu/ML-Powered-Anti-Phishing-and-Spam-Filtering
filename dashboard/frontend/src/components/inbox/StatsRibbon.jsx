import { Shield, ShieldAlert, ShieldCheck, AlertTriangle } from 'lucide-react'
import styles from './StatsRibbon.module.css'

export default function StatsRibbon({ stats }) {
  if (!stats) return null

  const total = stats.total ?? 0
  const quarantine = stats.quarantine ?? 0
  const warn = stats.warn ?? 0
  const clean = stats.clean ?? 0
  const threatRate = total > 0 ? ((quarantine + warn) / total * 100).toFixed(1) : '0.0'
  const cleanRate = total > 0 ? (clean / total * 100).toFixed(1) : '0.0'

  return (
    <div className={styles.ribbon}>
      <div className={`${styles.card} ${styles.total}`}>
        <div className={styles.cardLeft}>
          <Shield size={22} />
        </div>
        <div className={styles.cardRight}>
          <span className={styles.value}>{total.toLocaleString('id-ID')}</span>
          <span className={styles.label}>Total Diproses</span>
          <span className={styles.sub}>Semua email</span>
        </div>
      </div>

      <div className={`${styles.card} ${styles.threat}`}>
        <div className={styles.cardLeft}>
          <ShieldAlert size={22} />
        </div>
        <div className={styles.cardRight}>
          <span className={styles.value}>{(quarantine + warn).toLocaleString('id-ID')}</span>
          <span className={styles.label}>Ancaman</span>
          <span className={styles.sub}>{threatRate}% dari total</span>
        </div>
      </div>

      <div className={`${styles.card} ${styles.warnCard}`}>
        <div className={styles.cardLeft}>
          <AlertTriangle size={22} />
        </div>
        <div className={styles.cardRight}>
          <span className={styles.value}>{warn.toLocaleString('id-ID')}</span>
          <span className={styles.label}>Peringatan</span>
          <span className={styles.sub}>Memerlukan review</span>
        </div>
      </div>

      <div className={`${styles.card} ${styles.cleanCard}`}>
        <div className={styles.cardLeft}>
          <ShieldCheck size={22} />
        </div>
        <div className={styles.cardRight}>
          <span className={styles.value}>{clean.toLocaleString('id-ID')}</span>
          <span className={styles.label}>Bersih</span>
          <span className={styles.sub}>{cleanRate}% aman</span>
        </div>
      </div>
    </div>
  )
}
