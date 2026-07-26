import { useEffect, useState, useRef, useCallback } from 'react'
import api from '../api/client'
import { useTranslation } from '../i18n/context'
import {
  ShieldCheck, Mail, AlertTriangle,
  CheckCircle, Database, RefreshCw, Server, Zap, ShieldAlert,
} from 'lucide-react'
import styles from './SuperadminDashboardOverview.module.css'

const FETCH_TIMEOUT = 15000

function fetchWithTimeout(url) {
  return api.get(url, { timeout: FETCH_TIMEOUT })
}

function AnimatedValue({ value, duration = 600 }) {
  const [display, setDisplay] = useState(0)
  const prevValue = useRef(0)
  const raf = useRef(null)

  useEffect(() => {
    const target = typeof value === 'number' ? value : 0
    const start = prevValue.current
    const diff = target - start
    if (diff === 0) {
      setDisplay(target)
      return
    }
    const startTime = performance.now()
    const animate = (now) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplay(Math.round(start + diff * eased))
      if (progress < 1) raf.current = requestAnimationFrame(animate)
    }
    raf.current = requestAnimationFrame(animate)
    prevValue.current = target
    return () => { if (raf.current) cancelAnimationFrame(raf.current) }
  }, [value, duration])

  return <>{typeof value === 'number' ? display.toLocaleString() : value}</>
}

function SkeletonCard() {
  return (
    <div className={styles.skelCard}>
      <div className={styles.skelIcon} />
      <div className={styles.skelBody}>
        <div className={styles.skelLine} style={{ width: '60%', height: 28 }} />
        <div className={styles.skelLine} style={{ width: '40%', height: 14, marginTop: 8 }} />
        <div className={styles.skelLine} style={{ width: '30%', height: 12, marginTop: 6 }} />
      </div>
    </div>
  )
}

function SkeletonPanel() {
  return (
    <div className={styles.skelPanel}>
      <div className={styles.skelLine} style={{ width: '50%', height: 18, marginBottom: 16 }} />
      {[1,2,3,4].map((i) => (
        <div key={i} className={styles.skelServiceRow} style={{ marginTop: i > 1 ? 8 : 0 }}>
          <div className={styles.skelLine} style={{ width: 16, height: 16, borderRadius: '50%' }} />
          <div className={styles.skelLine} style={{ width: '40%', height: 14 }} />
          <div className={styles.skelLine} style={{ width: '15%', height: 14, borderRadius: 12 }} />
        </div>
      ))}
    </div>
  )
}

export default function SuperadminDashboardOverview({ isSuperadmin = true }) {
  const { t } = useTranslation()
  const [adminStats, setAdminStats] = useState(null)
  const [health, setHealth]         = useState(null)
  const [loading, setLoading]       = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError]           = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)
  const requestInFlight = useRef(false)

  const fetchAll = useCallback(async ({ background = false } = {}) => {
    if (requestInFlight.current) return
    requestInFlight.current = true
    if (!background) setRefreshing(true)
    try {
      const [adminRes, healthRes] = await Promise.allSettled([
        fetchWithTimeout('/admin/stats'),
        fetchWithTimeout('/health'),
      ])
      if (adminRes.status === 'fulfilled') setAdminStats(adminRes.value.data)
      if (healthRes.status === 'fulfilled') setHealth(healthRes.value.data)
      const failed = [
        adminRes.status === 'rejected' && 'statistik akun/mailbox',
        healthRes.status === 'rejected' && 'kesehatan layanan',
      ].filter(Boolean)
      setError(failed.length ? `Data tidak lengkap: gagal memuat ${failed.join(', ')}.` : '')
      if (failed.length < 2) setLastUpdated(new Date())
    } catch (err) {
      setError('Gagal memuat data: ' + (err.message || 'Terjadi kesalahan'))
    } finally {
      setLoading(false)
      if (!background) setRefreshing(false)
      requestInFlight.current = false
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible') fetchAll({ background: true })
    }, 30000)
    return () => window.clearInterval(interval)
  }, [fetchAll])

  const services = health ? [
    { name: 'API Dashboard', ok: true,                                                        icon: <Server size={16} /> },
    { name: 'Database',      ok: health.database === 'connected' || health.database === true,  icon: <Database size={16} /> },
    { name: 'Redis',         ok: health.redis === true || health.redis === 'connected',        icon: <Zap size={16} /> },
    { name: 'Classifier',    ok: health.classifier === true || health.classifier === 'ok',     icon: <ShieldCheck size={16} /> },
  ] : []
  const allOk = health ? services.every((service) => service.ok) : null

  // Overview figures must use the role-scoped mailbox statistics endpoint.
  // The generic pipeline endpoint also contains historical evaluation rows.
  const categories = adminStats?.categories || {}

  const statCards = [
    {
      key: 'total',
      value: typeof adminStats?.total_emails === 'number' ? adminStats.total_emails : '—',
      label: t('overview.totalEmail'),
      subtext: isSuperadmin ? t('overview.totalSubtextGlobal') : t('overview.totalSubtextAdmin'),
      icon: <Mail size={22} />,
      iconBg: 'rgba(26,115,232,0.1)',
      iconColor: '#1a73e8',
    },
    ...(isSuperadmin ? [{
      key: 'total-admins',
      value: typeof adminStats?.total_admins === 'number' ? adminStats.total_admins : '—',
      label: t('overview.totalAdmins'),
      subtext: t('overview.totalAdminsSubtext'),
      icon: <ShieldCheck size={22} />,
      iconBg: 'rgba(37,99,235,0.1)',
      iconColor: '#2563EB',
    }] : [{
      key: 'clean',
      value: typeof adminStats?.clean === 'number' ? adminStats.clean : '—',
      label: t('overview.clean'),
      subtext: t('overview.cleanSubtext'),
      icon: <CheckCircle size={22} />,
      iconBg: 'rgba(52,168,83,0.1)',
      iconColor: '#34a853',
    },
    {
      key: 'quarantine',
      value: typeof adminStats?.quarantine === 'number' ? adminStats.quarantine : '—',
      label: t('overview.quarantine'),
      subtext: t('overview.quarantineSubtext'),
      icon: <ShieldAlert size={22} />,
      iconBg: 'rgba(197,34,31,0.1)',
      iconColor: '#c5221f',
    },
    {
      key: 'active-mailboxes',
      value: typeof adminStats?.active_mailboxes === 'number' ? adminStats.active_mailboxes : '—',
      label: t('overview.activeMailboxes'),
      subtext: t('overview.activeMailboxesSubtext'),
      icon: <Database size={22} />,
      iconBg: 'rgba(16,185,129,0.1)',
      iconColor: '#10b981',
    }]),
  ]

  const threatItems = [
    { label: t('overview.phishing'),   value: adminStats ? (categories.phishing ?? 0) : null, color: '#ea4335' },
    { label: t('overview.spam'),       value: adminStats ? (categories.spam ?? 0) : null, color: '#f29900' },
    { label: t('overview.warn'),       value: adminStats ? (categories.warn ?? adminStats.warn ?? 0) : null, color: '#f29900' },
    { label: t('overview.cleanLabel'), value: adminStats ? (adminStats.clean ?? 0) : null, color: '#34a853' },
  ]

  const total = adminStats?.total_emails ?? 0

  return (
    <div className={styles.wrap}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>
            <span className={styles.titleIcon}><Server size={20} /></span>
            {isSuperadmin ? t('superadmin.overview.title') : t('admin.overview.title')}
          </h1>
          {lastUpdated && (
            <p className={styles.lastUpdated}>
              {t('overview.lastUpdated')}: {lastUpdated.toLocaleString('id-ID')} &middot; {isSuperadmin ? t('overview.statsDesc') : t('admin.overview.scope')}
            </p>
          )}
        </div>
        <div className={styles.headerActions}>
          <button className={styles.btnRefresh} onClick={() => fetchAll()} disabled={refreshing}>
            <RefreshCw size={14} className={refreshing ? styles.spin : ''} />
            {t('overview.refresh')}
          </button>
        </div>
      </div>

      {error && (
        <div className={styles.errorBanner}>
          <AlertTriangle size={14} /> {error === 'Gagal memuat data. Periksa koneksi server.' ? t('overview.error') : error}
        </div>
      )}

      {loading ? (
        <>
          <div className={`${styles.statGrid} ${isSuperadmin ? styles.superadminStatGrid : styles.adminStatGrid}`}>
            {[1,2,3,4].map((i) => <SkeletonCard key={i} />)}
          </div>
          <div className={styles.panelGrid}>
            <SkeletonPanel />
            <SkeletonPanel />
          </div>
        </>
      ) : (
        <>
          {/* Email stat cards */}
          <div className={`${styles.statGrid} ${isSuperadmin ? styles.superadminStatGrid : styles.adminStatGrid}`}>
            {statCards.map((card) => (
              <div key={card.key} className={styles.statCard}>
                <div className={styles.statIconWrap} style={{ background: card.iconBg }}>
                  <span style={{ color: card.iconColor, display: 'flex' }}>{card.icon}</span>
                </div>
                <div className={styles.statBody}>
                  <div className={styles.statValue}>
                    <AnimatedValue value={card.value} />
                  </div>
                  <div className={styles.statLabel}>{card.label}</div>
                  <div className={styles.statSubtext}>{card.subtext}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Health & Threat panels */}
          <div className={styles.panelGrid}>
            {/* System health */}
            <div className={styles.panel}>
              <div className={styles.panelHeader}>
                <span className={styles.panelTitle}>
                  <Server size={16} /> {t('overview.healthTitle')}
                </span>
                <span className={allOk === true ? styles.badgeOnline : styles.badgeOffline}>
                  {allOk === null ? t('overview.unavailable') : allOk ? t('overview.healthAllOk') : t('overview.healthIssues')}
                </span>
              </div>
              <div className={styles.serviceList}>
                {services.map((svc) => (
                  <div key={svc.name} className={styles.serviceRow}>
                    <span className={svc.ok ? styles.serviceIconOk : styles.serviceIconErr}>
                      {svc.icon}
                    </span>
                    <span className={styles.serviceName}>{svc.name}</span>
                    <span className={svc.ok ? styles.serviceStatusOk : styles.serviceStatusErr}>
                      {svc.ok ? t('overview.online') : t('overview.offline')}
                    </span>
                  </div>
                ))}
                {!health && <div className={styles.unavailable}>{t('overview.dataUnavailable')}</div>}
              </div>
            </div>

            {/* Threat distribution */}
            <div className={styles.panel}>
              <div className={styles.panelHeader}>
                <span className={styles.panelTitle}>
                  <ShieldAlert size={16} /> {t('overview.threatTitle')}
                </span>
              </div>
              <div className={styles.threatList}>
                {threatItems.map((item) => {
                  const pct = typeof item.value === 'number' && total > 0 ? Math.round((item.value / total) * 100) : 0
                  return (
                    <div key={item.label} className={styles.threatRow}>
                      <div className={styles.threatTop}>
                        <span className={styles.threatLabel}>
                          <span className={styles.threatDot} style={{ background: item.color }} />
                          {item.label}
                        </span>
                        <span className={styles.threatValue}>
                          <AnimatedValue value={typeof item.value === 'number' ? item.value : '—'} duration={500} />
                          <span className={styles.threatPct}>{typeof item.value === 'number' ? `${pct}%` : ''}</span>
                        </span>
                      </div>
                      <div className={styles.barTrack}>
                        <div className={styles.barFill} style={{ width: `${pct}%`, background: item.color }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
