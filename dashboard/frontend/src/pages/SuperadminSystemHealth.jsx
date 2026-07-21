import { useEffect, useState } from 'react'
import api from '../api/client'
import { Server, RefreshCw, CheckCircle, XCircle, Database, Zap, ShieldCheck, Wifi } from 'lucide-react'
import styles from './AdminPage.module.css'
import { useTranslation } from '../i18n/context'

export default function SuperadminSystemHealth() {
  const { t } = useTranslation()
  const [health, setHealth]           = useState(null)
  const [loading, setLoading]         = useState(true)
  const [lastUpdated, setLastUpdated] = useState(null)

  const fetchHealth = () => {
    setLoading(true)
    api.get('/health')
      .then(({ data }) => { setHealth(data); setLastUpdated(new Date()) })
      .catch(() => setHealth({ status: 'error' }))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchHealth() }, [])

  const allOk = health && (health.status === 'ok' || health.status === 'healthy')

  const services = health ? [
    { name: t('health.service.api'), desc: t('health.service.apiDesc'),  ok: allOk,                                         icon: <Wifi size={14} /> },
    { name: t('health.service.db'), desc: t('health.service.dbDesc'),    ok: health.database !== false && health.db !== false, icon: <Database size={14} /> },
    { name: t('health.service.redis'), desc: t('health.service.redisDesc'), ok: health.redis !== false,                         icon: <Zap size={14} /> },
    { name: t('health.service.classifier'), desc: t('health.service.classifierDesc'), ok: health.classifier !== false,          icon: <ShieldCheck size={14} /> },
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
      )}
    </div>
  )
}
