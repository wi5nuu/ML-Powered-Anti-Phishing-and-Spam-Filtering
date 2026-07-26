import { useEffect, useState } from 'react'
import api from '../api/client'
import { Server, RefreshCw, CheckCircle, XCircle, Database, Zap, ShieldCheck, Wifi, AlertTriangle } from 'lucide-react'
import styles from './AdminPage.module.css'
import { useTranslation } from '../i18n/context'

const AUTO_REFRESH_MS = 30000

const SERVICE_META = {
  dashboard_backend: ['API Dashboard', 'FastAPI + Uvicorn', Wifi],
  postgresql: ['Database', 'PostgreSQL', Database],
  redis: ['Redis', 'Cache & antrian', Zap],
  classifier_api: ['Klasifikator', 'Layanan model ML', ShieldCheck],
  smtp_receiver: ['SMTP Receiver', 'Menerima email masuk', Server],
  worker_pipeline: ['Worker Pipeline', 'Memproses antrian email', Wifi],
  spamassassin: ['SpamAssassin', 'Mesin pemeriksaan spam', ShieldCheck],
}

function presentation(status) {
  if (status === 'healthy') return { bg: '#F0FDF4', color: '#16A34A', label: 'Online', Icon: CheckCircle }
  if (status === 'warning') return { bg: '#FFFAEB', color: '#B54708', label: 'Peringatan', Icon: AlertTriangle }
  if (status === 'unavailable') return { bg: '#F2F4F7', color: '#667085', label: 'Tidak terverifikasi', Icon: AlertTriangle }
  return { bg: '#FEF2F2', color: '#DC2626', label: 'Offline', Icon: XCircle }
}

export default function SuperadminSystemHealth() {
  const { t } = useTranslation()
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)

  const fetchHealth = () => {
    setLoading(true)
    setError('')
    api.get('/admin/system-health')
      .then(({ data }) => {
        setHealth(data)
        setLastUpdated(new Date(data.checked_at || Date.now()))
      })
      .catch((err) => {
        setHealth(null)
        setError(err.response?.data?.detail || t('health.loadError', 'Gagal memuat status sistem.'))
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchHealth()
    const interval = window.setInterval(fetchHealth, AUTO_REFRESH_MS)
    return () => window.clearInterval(interval)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const services = Object.entries(health?.services || {}).map(([key, value]) => {
    const [name, desc, Icon] = SERVICE_META[key] || [key, 'Layanan sistem', Server]
    return { key, name, desc, Icon, ...value }
  })
  const overall = health?.overall || 'down'
  const overallHealthy = overall === 'healthy'
  const overallWarning = overall === 'warning'

  return (
    <div className={styles.dashWrap}>
      <div className={styles.dashHero}>
        <div className={styles.dashHeroLeft}>
          <div className={styles.dashGreetRow}>
            <h1 className={styles.dashTitle}>{t('health.title')}</h1>
            {health && (
              <span className={styles.roleBadgePill} style={{
                background: overallHealthy ? '#F0FDF4' : overallWarning ? '#FFFAEB' : '#FEF2F2',
                color: overallHealthy ? '#16A34A' : overallWarning ? '#B54708' : '#DC2626',
                border: `1px solid ${overallHealthy ? '#BBF7D0' : overallWarning ? '#FEDF89' : '#FECACA'}`,
              }}>
                {overallHealthy ? t('health.allNormal') : overallWarning ? 'Perlu perhatian' : t('health.issues')}
              </span>
            )}
          </div>
          <p className={styles.dashSubtitle}>{t('health.subtitle')}</p>
        </div>
        <div className={styles.dashHeroRight}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {lastUpdated && <span className={styles.dashHeroTime}>{t('health.update')} {lastUpdated.toLocaleTimeString('id-ID')}</span>}
            <button onClick={fetchHealth} disabled={loading} className={styles.addBtn} style={{ background: 'none', border: '1px solid var(--border)', color: 'var(--text)' }}>
              <RefreshCw size={13} /> {t('health.refresh')}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', marginBottom: 12, background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 6, color: '#DC2626', fontSize: '0.85rem' }}>
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {loading && !health ? (
        <div className={styles.emptySmall}>{t('health.loading')}</div>
      ) : (
        <div className={styles.sectionCard}>
          <div className={styles.sectionCardHeader}>
            <Server size={15} className={styles.sectionCardIcon} />
            {t('health.statusTitle')}
          </div>
          <div className={styles.healthList}>
            {services.map((service) => {
              const state = presentation(service.status)
              const StateIcon = state.Icon
              const ServiceIcon = service.Icon
              return (
                <div key={service.key} className={styles.healthRow}>
                  <div className={styles.healthIcon} style={{ background: state.bg, color: state.color }}>
                    <ServiceIcon size={14} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className={styles.healthName}>{service.name}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{service.desc}</div>
                    {service.detail && <div style={{ marginTop: 3, fontSize: '0.68rem', color: 'var(--text-muted)', overflowWrap: 'anywhere' }}>{service.detail}</div>}
                  </div>
                  <span className={styles.healthBadge} style={{ background: state.bg, color: state.color }}>
                    <StateIcon size={11} style={{ marginRight: 4 }} />{state.label}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
