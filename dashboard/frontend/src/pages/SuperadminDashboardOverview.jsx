import { useEffect, useState, useRef, useCallback } from 'react'
import api from '../api/client'
import { useTranslation } from '../i18n/context'
import {
  ShieldCheck, Users, Mail, Activity, AlertTriangle,
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

export default function SuperadminDashboardOverview() {
  const { t } = useTranslation()
  const [emailStats, setEmailStats] = useState(null)
  const [adminStats, setAdminStats] = useState(null)
  const [health, setHealth]         = useState(null)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [emailRes, adminRes, healthRes] = await Promise.allSettled([
        fetchWithTimeout('/stats'),
        fetchWithTimeout('/admin/stats'),
        fetchWithTimeout('/health'),
      ])
      if (emailRes.status  === 'fulfilled') setEmailStats(emailRes.value.data)
      if (adminRes.status  === 'fulfilled') setAdminStats(adminRes.value.data)
      if (healthRes.status === 'fulfilled') setHealth(healthRes.value.data)
      if (emailRes.status  === 'rejected' && adminRes.status  === 'rejected' && healthRes.status === 'rejected') {
        setError('Gagal memuat data. Periksa koneksi server.')
      }
      setLastUpdated(new Date())
    } catch (err) {
      setError('Gagal memuat data: ' + (err.message || 'Terjadi kesalahan'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  const allOk = health && (health.status === 'ok' || health.status === 'healthy')

  const services = health ? [
    { name: 'API Dashboard', ok: allOk,                                                       icon: <Server size={16} /> },
    { name: 'Database',      ok: health.database === 'connected' || health.database === true,  icon: <Database size={16} /> },
    { name: 'Redis',         ok: health.redis === true || health.redis === 'connected',        icon: <Zap size={16} /> },
    { name: 'Classifier',    ok: health.classifier === true || health.classifier === 'ok',     icon: <ShieldCheck size={16} /> },
  ] : []

  const categories = emailStats?.categories || {}

  const statCards = [
    {
      key: 'total',
      value: typeof emailStats?.total === 'number' ? emailStats.total : 0,
      label: t('overview.totalEmail'),
      subtext: t('overview.totalSubtext'),
      icon: <Mail size={22} />,
      iconBg: 'rgba(26,115,232,0.1)',
      iconColor: '#1a73e8',
    },
    {
      key: 'clean',
      value: typeof emailStats?.clean === 'number' ? emailStats.clean : 0,
      label: t('overview.clean'),
      subtext: t('overview.cleanSubtext'),
      icon: <CheckCircle size={22} />,
      iconBg: 'rgba(52,168,83,0.1)',
      iconColor: '#34a853',
    },
    {
      key: 'warn',
      value: typeof emailStats?.warn === 'number' ? emailStats.warn : 0,
      label: t('overview.warn'),
      subtext: t('overview.warnSubtext'),
      icon: <AlertTriangle size={22} />,
      iconBg: 'rgba(242,153,0,0.1)',
      iconColor: '#f29900',
    },
    {
      key: 'quarantine',
      value: typeof emailStats?.quarantine === 'number' ? emailStats.quarantine : 0,
      label: t('overview.quarantine'),
      subtext: t('overview.quarantineSubtext'),
      icon: <ShieldAlert size={22} />,
      iconBg: 'rgba(197,34,31,0.1)',
      iconColor: '#c5221f',
    },
  ]

  const threatItems = [
    { label: t('overview.phishing'),   value: categories.phishing ?? 0, color: '#ea4335' },
    { label: t('overview.spam'),       value: categories.spam     ?? 0, color: '#f29900' },
    { label: t('overview.malware'),    value: categories.malware  ?? 0, color: '#9c27b0' },
    { label: t('overview.warnLabel'),  value: emailStats?.warn    ?? 0, color: '#fb8c00' },
    { label: t('overview.cleanLabel'), value: emailStats?.clean   ?? 0, color: '#34a853' },
  ]

  const total = emailStats?.total || 1

  return (
    <div className={styles.wrap}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>
            <span className={styles.titleIcon}><Server size={20} /></span>
            {t('overview.title')}
          </h1>
          {lastUpdated && (
            <p className={styles.lastUpdated}>
              {t('overview.lastUpdated')}: {lastUpdated.toLocaleString('id-ID')} &middot; {t('overview.statsDesc')}
            </p>
          )}
        </div>
        <div className={styles.headerActions}>
          <button className={styles.btnRefresh} onClick={fetchAll} disabled={loading}>
            <RefreshCw size={14} className={loading ? styles.spin : ''} />
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
          <div className={styles.statGrid}>
            {[1,2,3,4].map((i) => <SkeletonCard key={i} />)}
          </div>
          <div className={styles.statGrid}>
            {[1,2].map((i) => <SkeletonCard key={i} />)}
          </div>
          <div className={styles.panelGrid}>
            <SkeletonPanel />
            <SkeletonPanel />
          </div>
        </>
      ) : (
        <>
          {/* Email stat cards */}
          <div className={styles.statGrid}>
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

          {/* User stat cards */}
          <div className={styles.statGrid}>
            <div className={styles.statCard}>
              <div className={styles.statIconWrap} style={{ background: 'rgba(139,92,246,0.1)' }}>
                <Users size={22} style={{ color: '#7c3aed' }} />
              </div>
              <div className={styles.statBody}>
                <div className={styles.statValue}>
                  <AnimatedValue value={adminStats?.total_regular_users ?? 0} />
                </div>
                <div className={styles.statLabel}>{t('overview.totalUsers')}</div>
                <div className={styles.statSubtext}>{t('overview.totalUsersSubtext')}</div>
              </div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statIconWrap} style={{ background: 'rgba(37,99,235,0.1)' }}>
                <ShieldCheck size={22} style={{ color: '#2563EB' }} />
              </div>
              <div className={styles.statBody}>
                <div className={styles.statValue}>
                  <AnimatedValue value={adminStats?.total_admins ?? 0} />
                </div>
                <div className={styles.statLabel}>{t('overview.totalAdmins')}</div>
                <div className={styles.statSubtext}>{t('overview.totalAdminsSubtext')}</div>
              </div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statIconWrap} style={{ background: 'rgba(16,185,129,0.1)' }}>
                <Database size={22} style={{ color: '#10b981' }} />
              </div>
              <div className={styles.statBody}>
                <div className={styles.statValue}>
                  <AnimatedValue value={adminStats?.total_organizations ?? 0} />
                </div>
                <div className={styles.statLabel}>{t('overview.totalOrganizations')}</div>
                <div className={styles.statSubtext}>{t('overview.totalOrganizationsSubtext')}</div>
              </div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statIconWrap} style={{ background: 'rgba(20,184,166,0.1)' }}>
                <Activity size={22} style={{ color: '#14b8a6' }} />
              </div>
              <div className={styles.statBody}>
                <div className={styles.statValue}>
                  <AnimatedValue value={(adminStats?.total_regular_users ?? 0) + (adminStats?.total_admins ?? 0) + (adminStats?.total_superadmins ?? 0)} />
                </div>
                <div className={styles.statLabel}>{t('overview.totalAllAccounts')}</div>
                <div className={styles.statSubtext}>{t('overview.totalAllAccountsSubtext')}</div>
              </div>
            </div>
          </div>

          {/* Health & Threat panels */}
          <div className={styles.panelGrid}>
            {/* System health */}
            <div className={styles.panel}>
              <div className={styles.panelHeader}>
                <span className={styles.panelTitle}>
                  <Server size={16} /> {t('overview.healthTitle')}
                </span>
                <span className={allOk ? styles.badgeOnline : styles.badgeOffline}>
                  {allOk ? t('overview.healthAllOk') : t('overview.healthIssues')}
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
                  const pct = Math.round((item.value / total) * 100)
                  return (
                    <div key={item.label} className={styles.threatRow}>
                      <div className={styles.threatTop}>
                        <span className={styles.threatLabel}>
                          <span className={styles.threatDot} style={{ background: item.color }} />
                          {item.label}
                        </span>
                        <span className={styles.threatValue}>
                          <AnimatedValue value={item.value} duration={500} />
                          <span className={styles.threatPct}>{pct}%</span>
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
