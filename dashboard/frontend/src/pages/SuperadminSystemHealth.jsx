import { useEffect, useState } from 'react'
import api from '../api/client'
import { Server, RefreshCw, CheckCircle, XCircle, Database, Zap, ShieldCheck, Wifi, AlertTriangle } from 'lucide-react'
import styles from './AdminPage.module.css'
import { useTranslation } from '../i18n/context'

const AUTO_REFRESH_MS = 60000

export default function SuperadminSystemHealth() {
  const { t } = useTranslation()
  const [health, setHealth]           = useState(null)
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)

  const fetchHealth = () => {
    setLoading(true)
    setError('')
    // Gunakan /admin/system-health untuk data lengkap (redis, classifier, smtp, worker)
    // Fallback ke /health jika gagal (misal user bukan superadmin)
    api.get('/admin/system-health')
      .then(({ data }) => { setHealth(data); setLastUpdated(new Date()) })
      .catch(() =>
        api.get('/health')
          .then(({ data }) => { setHealth(data); setLastUpdated(new Date()) })
          .catch((err) => {
            setHealth({ status: 'error' })
            setError(err.response?.data?.detail || t('health.loadError', 'Gagal memuat status sistem.'))
          })
      )
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchHealth()
    const interval = setInterval(fetchHealth, AUTO_REFRESH_MS)
    return () => clearInterval(interval)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const allOk = health && (health.status === 'ok' || health.status === 'healthy')

  // /admin/system-health returns { services: { postgresql, redis, classifier_api, smtp_receiver, worker_pipeline } }
  // /health (fallback) returns { database, redis, classifier }
  const svcMap = health?.services || {}
  const isOk = (key, fallback) => {
    if (svcMap[key]) return svcMap[key].status === 'healthy'
    return fallback
  }

  const services = health ? [
    {
      name: t('health.service.api'),
      desc: t('health.service.apiDesc'),
      ok: allOk,
      detail: `v${health.version || '—'}`,
      icon: <Wifi size={14} />,
    },
    {
      name: t('health.service.db'),
      desc: t('health.service.dbDesc'),
      ok: isOk('postgresql', health.database === 'connected' || health.database === true),
      detail: svcMap.postgresql?.detail || (health.database === 'connected' ? 'Connected' : health.database),
      icon: <Database size={14} />,
    },
    {
      name: t('health.service.redis'),
      desc: t('health.service.redisDesc'),
      ok: isOk('redis', health.redis === true || health.redis === 'connected'),
      detail: svcMap.redis?.detail || (health.redis === true ? 'Connected' : 'Unavailable'),
      icon: <Zap size={14} />,
    },
    {
      name: t('health.service.classifier'),
      desc: t('health.service.classifierDesc'),
      ok: isOk('classifier_api', health.classifier === true || health.classifier === 'ok'),
      detail: svcMap.classifier_api?.detail || (health.classifier === true ? 'Responding' : 'Unavailable'),
      icon: <ShieldCheck size={14} />,
    },
    ...(svcMap.smtp_receiver ? [{
      name: 'SMTP Receiver',
      desc: 'Menerima email masuk',
      ok: svcMap.smtp_receiver.status === 'healthy',
      detail: svcMap.smtp_receiver.detail || '',
      icon: <Server size={14} />,
    }] : []),
    ...(svcMap.worker_pipeline ? [{
      name: 'Worker Pipeline',
      desc: 'Memproses antrian email',
      ok: svcMap.worker_pipeline.status === 'healthy',
      detail: svcMap.worker_pipeline.detail || '',
      icon: <Wifi size={14} />,
    }] : []),
  ] : []

  return (
    <div className={styles.dashWrap}>
      {/* Header */}
      <div className={styles.dashHero}>
        <div className={styles.dashHeroLeft}>
          <div className={styles.dashGreetRow}>
            <h1 className={styles.dashTitle}>{t('health.title')}</h1>
            {health && (
              <span className={styles.roleBadgePill} style={allOk
                ? { background: '#F0FDF4', color: '#16A34A', border: '1px solid #BBF7D0' }
                : { background: '#FEF2F2', color: '#DC2626', border: '1px solid #FECACA' }
              }>
                {allOk ? t('health.allNormal') : t('health.issues')}
              </span>
            )}
          </div>
          <p className={styles.dashSubtitle}>{t('health.subtitle')}</p>
        </div>
        <div className={styles.dashHeroRight}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {lastUpdated && (
              <span className={styles.dashHeroTime}>
                {t('health.update')} {lastUpdated.toLocaleTimeString('id-ID')}
              </span>
            )}
            <button onClick={fetchHealth} disabled={loading}
              className={styles.addBtn}
              style={{ background: 'none', border: '1px solid var(--border)', color: 'var(--text)' }}>
              <RefreshCw size={13} /> {t('health.refresh')}
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <div className={styles.emptySmall}>{t('health.loading')}</div>
      ) : (
        <>
          {error && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', marginBottom: 12, background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 6, color: '#DC2626', fontSize: '0.85rem' }}>
              <AlertTriangle size={14} /> {error}
            </div>
          )}
        <div className={styles.sectionCard}>
          <div className={styles.sectionCardHeader}>
            <Server size={15} className={styles.sectionCardIcon} />
            {t('health.statusTitle')}
          </div>
          <div className={styles.healthList}>
            {services.map((svc) => (
              <div key={svc.name} className={styles.healthRow}>
                <div className={styles.healthIcon} style={{
                  background: svc.ok ? '#F0FDF4' : '#FEF2F2',
                  color:      svc.ok ? '#16A34A' : '#DC2626',
                }}>
                  {svc.icon}
                </div>
                <div style={{ flex: 1 }}>
                  <div className={styles.healthName}>{svc.name}</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{svc.desc}</div>
                </div>
                <span className={styles.healthBadge} style={{
                  background: svc.ok ? '#F0FDF4' : '#FEF2F2',
                  color:      svc.ok ? '#16A34A' : '#DC2626',
                }}>
                  {svc.ok
                    ? <><CheckCircle size={11} style={{ marginRight: 4 }} />{t('health.online')}</>
                    : <><XCircle    size={11} style={{ marginRight: 4 }} />{t('health.offline')}</>
                  }
                </span>
              </div>
            ))}
          </div>
        </div>
        </>
      )}
    </div>
  )
}
