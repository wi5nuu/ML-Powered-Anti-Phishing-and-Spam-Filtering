import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Shield, Activity, Mail, MessageSquare } from 'lucide-react'
import GmailShell from '../components/layout/GmailShell'
import { useMetrics } from '../api/metrics'
import styles from './MetricsPage.module.css'

export default function MetricsPage() {
  const navigate = useNavigate()
  const { data: metrics, isLoading, isError } = useMetrics()

  if (isLoading) {
    return (
      <GmailShell>
        <div style={{ padding: 32, color: 'var(--text-muted)', fontFamily: 'Google Sans, Roboto, sans-serif' }}>
          Memuat panel metrik...
        </div>
      </GmailShell>
    )
  }

  if (isError || !metrics) {
    return (
      <GmailShell>
        <div style={{ padding: 32, color: '#EA4335', fontFamily: 'Google Sans, Roboto, sans-serif' }}>
          Gagal memuat panel metrik.
        </div>
      </GmailShell>
    )
  }

  const {
    total = 0,
    quarantine_count = 0,
    warn_count = 0,
    clean_count = 0,
    feedback_count = 0,
    top_senders = [],
    daily_stats = []
  } = metrics

  const maxTotal = Math.max(total, 1)
  const quarantinePct = ((quarantine_count / maxTotal) * 100).toFixed(1)
  const warnPct = ((warn_count / maxTotal) * 100).toFixed(1)
  const cleanPct = ((clean_count / maxTotal) * 100).toFixed(1)
  const detectionRate = (((quarantine_count + warn_count) / maxTotal) * 100).toFixed(1)

  const maxDaily = daily_stats.length
    ? Math.max(...daily_stats.map(d => d.total || 1))
    : 1

  return (
    <GmailShell>
      <div className={styles.wrap}>
        {/* Header */}
        <div className={styles.header}>
          <button className={styles.backBtn} onClick={() => navigate('/inbox')}>
            <ArrowLeft size={20} />
            Kembali ke Inbox
          </button>
          <div className={styles.titleRow}>
            <h1 className={styles.title}>Panel Metrik</h1>
            <span className={styles.liveBadge}>Real-time</span>
          </div>
        </div>

        {/* Metric Cards */}
        <div className={styles.grid}>
          <div className={`${styles.card} ${styles.cardTotal}`}>
            <div className={styles.cardHeader}>
              <Mail className={styles.cardIcon} size={20} />
              <h3>Total Diproses</h3>
            </div>
            <div className={styles.value}>{total}</div>
            <div className={styles.subtext}>semua email</div>
          </div>
          <div className={`${styles.card} ${styles.cardQuarantine}`}>
            <div className={styles.cardHeader}>
              <Shield className={styles.cardIcon} size={20} />
              <h3>Dikarantina</h3>
            </div>
            <div className={styles.value}>{quarantine_count}</div>
            <div className={styles.subtext}>{quarantinePct}% dari total</div>
          </div>
          <div className={`${styles.card} ${styles.cardWarn}`}>
            <div className={styles.cardHeader}>
              <Activity className={styles.cardIcon} size={20} />
              <h3>Peringatan</h3>
            </div>
            <div className={styles.value}>{warn_count}</div>
            <div className={styles.subtext}>{warnPct}% dari total</div>
          </div>
          <div className={`${styles.card} ${styles.cardClean}`}>
            <div className={styles.cardHeader}>
              <Shield className={styles.cardIcon} size={20} />
              <h3>Bersih</h3>
            </div>
            <div className={styles.value}>{clean_count}</div>
            <div className={styles.subtext}>{cleanPct}% dari total</div>
          </div>
          <div className={`${styles.card} ${styles.cardFeedback}`}>
            <div className={styles.cardHeader}>
              <MessageSquare className={styles.cardIcon} size={20} />
              <h3>False Positive</h3>
            </div>
            <div className={styles.value}>{feedback_count}</div>
            <div className={styles.subtext}>laporan pengguna</div>
          </div>
        </div>

        {/* Distribution Bar */}
        <div className={styles.sectionCard}>
          <h3 className={styles.sectionTitle}>Distribusi Label Email</h3>
          <div className={styles.barContainer}>
            {clean_count > 0 && (
              <div className={`${styles.bar} ${styles.barClean}`} style={{ width: `${(clean_count / maxTotal) * 100}%` }}>
                {Math.round((clean_count / maxTotal) * 100)}% Bersih
              </div>
            )}
            {warn_count > 0 && (
              <div className={`${styles.bar} ${styles.barWarn}`} style={{ width: `${(warn_count / maxTotal) * 100}%` }}>
                {Math.round((warn_count / maxTotal) * 100)}% Peringatan
              </div>
            )}
            {quarantine_count > 0 && (
              <div className={`${styles.bar} ${styles.barQuarantine}`} style={{ width: `${(quarantine_count / maxTotal) * 100}%` }}>
                {Math.round((quarantine_count / maxTotal) * 100)}% Karantina
              </div>
            )}
          </div>
          <div className={styles.legend}>
            <span><span className={styles.dotClean}>■</span> Bersih: {clean_count}</span>
            <span><span className={styles.dotWarn}>■</span> Peringatan: {warn_count}</span>
            <span><span className={styles.dotQuarantine}>■</span> Karantina: {quarantine_count}</span>
          </div>
        </div>

        {/* Daily Trend Chart */}
        {daily_stats && daily_stats.length > 0 && (
          <div className={styles.sectionCard}>
            <h3 className={styles.sectionTitle}>Tren Harian (14 Hari Terakhir)</h3>
            <div className={styles.chart}>
              {daily_stats.map((dayData, i) => {
                const qHeight = Math.round(((dayData.quarantines || 0) / maxDaily) * 120)
                const cHeight = Math.round((Math.abs((dayData.total || 0) - (dayData.quarantines || 0)) / maxDaily) * 120)
                const label = dayData.day ? dayData.day.slice(5) : ''
                return (
                  <div key={i} className={styles.chartCol} title={`${dayData.day}: ${dayData.total} total, ${dayData.quarantines || 0} karantina`}>
                    <div className={styles.chartBars}>
                      <div className={`${styles.chartFill} ${styles.chartQuarantine}`} style={{ height: `${qHeight}px` }} />
                      <div className={`${styles.chartFill} ${styles.chartClean}`} style={{ height: `${cHeight}px` }} />
                    </div>
                    <span className={styles.chartLabel}>{label}</span>
                  </div>
                )
              })}
            </div>
            <div className={styles.chartLegend}>
              <span><span className={styles.dotQuarantine}>■</span> Karantina</span>
              <span><span className={styles.dotClean}>■</span> Bersih / WARN</span>
            </div>
          </div>
        )}

        {/* Top Senders & Summary Row */}
        <div className={styles.rowLayout}>
          <div className={styles.sectionCard} style={{ flex: 1 }}>
            <h3 className={styles.sectionTitle}>🏆 Top 10 Pengirim Terblokir</h3>
            <div className={styles.sendersList}>
              {top_senders.map((sender, idx) => (
                <div key={idx} className={styles.senderRow}>
                  <div className={styles.senderAvatar}>
                    {(sender.sender || 'U')[0].toUpperCase()}
                  </div>
                  <span className={styles.senderName} title={sender.sender || '(tidak diketahui)'}>
                    {sender.sender || '(tidak diketahui)'}
                  </span>
                  <span className={styles.senderBadge}>
                    {sender.count} email
                  </span>
                </div>
              ))}
              {top_senders.length === 0 && (
                <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                  Belum ada data pengirim
                </div>
              )}
            </div>
          </div>

          <div className={`${styles.sectionCard} ${styles.summaryCard}`}>
            <h3 className={styles.sectionTitle}>📈 Ringkasan Keamanan</h3>
            <div className={styles.summaryList}>
              <div className={styles.summaryRow}>
                <span>Tingkat Deteksi</span>
                <strong style={{ color: 'var(--gmail-green)' }}>{detectionRate}%</strong>
              </div>
              <div className={styles.summaryRow}>
                <span>Email Aman</span>
                <strong style={{ color: 'var(--gmail-blue)' }}>{cleanPct}%</strong>
              </div>
              <div className={styles.summaryRow}>
                <span>Laporan False Positive</span>
                <strong style={{ color: 'var(--gmail-yellow)' }}>{feedback_count}</strong>
              </div>
              <div className={styles.summaryRow}>
                <span>Mode Deteksi</span>
                <span className={styles.dualBadge}>Dual ML + SA</span>
              </div>
            </div>
            <button className={styles.inboxBtn} onClick={() => navigate('/inbox')}>
              Lihat Kotak Masuk
            </button>
          </div>
        </div>
      </div>
    </GmailShell>
  )
}
