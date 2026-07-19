import { useState, useEffect, useCallback } from 'react'
import api from '../api/client'
import { Server, Activity, Database, Cpu, Mail, Zap, Shield, Container, RefreshCw, CheckCircle2, XCircle, AlertTriangle, Clock } from 'lucide-react'
import styles from './SuperadminSystemHealth.module.css'

const SERVICE_ICONS = {
  postgresql: { icon: <Database size={17} />, color: '#336791', bg: '#E8F0FE' },
  redis: { icon: <Database size={17} />, color: '#DC382D', bg: '#FCE8E6' },
  classifier_api: { icon: <Cpu size={17} />, color: '#7C3AED', bg: '#F3E8FF' },
  smtp_receiver: { icon: <Mail size={17} />, color: '#2563EB', bg: '#EFF6FF' },
  worker_pipeline: { icon: <Zap size={17} />, color: '#D97706', bg: '#FFFBEB' },
  spamassassin: { icon: <Shield size={17} />, color: '#059669', bg: '#ECFDF5' },
  dashboard_backend: { icon: <Server size={17} />, color: '#4F46E5', bg: '#EEF2FF' },
  docker: { icon: <Container size={17} />, color: '#0DB7ED', bg: '#E6F9FF' },
}

const SERVICE_LABELS = {
  postgresql: 'PostgreSQL',
  redis: 'Redis',
  classifier_api: 'Classifier API',
  smtp_receiver: 'SMTP Receiver',
  worker_pipeline: 'Worker Pipeline',
  spamassassin: 'SpamAssassin',
  dashboard_backend: 'Dashboard Backend',
  docker: 'Docker Containers',
}

const STATUS_META = {
  healthy: { label: 'Healthy', color: '#059669', bg: '#ECFDF5', icon: <CheckCircle2 size={14} /> },
  warning: { label: 'Warning', color: '#D97706', bg: '#FFFBEB', icon: <AlertTriangle size={14} /> },
  down: { label: 'Down', color: '#DC2626', bg: '#FEF2F2', icon: <XCircle size={14} /> },
}

export default function SuperadminSystemHealth() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  const fetchHealth = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const r = await api.get('/admin/system-health')
      setData(r.data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to fetch system health')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { fetchHealth() }, [fetchHealth])

  if (loading && !data) {
    return (
      <div className={styles.wrap}>
        <div className={styles.emptyState}>
          <Activity size={28} style={{ marginBottom: 12, opacity: 0.4 }} />
          <div>Loading system health...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.wrap}>
        <div className={styles.errorState}>
          <XCircle size={28} style={{ marginBottom: 12 }} />
          <div>{error}</div>
        </div>
      </div>
    )
  }

  const { overall, services, checked_at } = data || {}
  const overallMeta = STATUS_META[overall] || STATUS_META.down

  return (
    <div className={styles.wrap}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.headerIcon} style={{ background: overallMeta.bg, color: overallMeta.color }}>
            <Server size={22} />
          </div>
          <div>
            <h2 className={styles.headerTitle}>System Health</h2>
            <p className={styles.headerSub}>Real-time status of all platform services</p>
          </div>
        </div>
        <div className={styles.headerRight}>
          <span className={styles.lastChecked}>
            <Clock size={11} style={{ marginRight: 4, verticalAlign: -1 }} />
            {checked_at ? new Date(checked_at).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'}
          </span>
          <span className={styles.overallBadge} style={{ background: overallMeta.bg, color: overallMeta.color }}>
            {overallMeta.icon} {overallMeta.label}
          </span>
          <button
            className={`${styles.refreshBtn} ${refreshing ? styles.spinning : ''}`}
            onClick={() => fetchHealth(true)}
            disabled={refreshing}
          >
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      <div className={styles.grid}>
        {services && Object.entries(services).map(([key, svc]) => {
          if (key === 'docker' && svc.containers) {
            return (
              <div key={key} className={styles.dockerSection}>
                <div className={styles.dockerHeader}>
                  <span className={styles.dockerHeaderIcon} style={{ color: SERVICE_ICONS.docker?.color }}>
                    <Container size={16} />
                  </span>
                  <span>{SERVICE_LABELS.docker || key}</span>
                  {svc.status && (
                    <span className={styles.cardBadge} style={{ background: STATUS_META[svc.status]?.bg, color: STATUS_META[svc.status]?.color }}>
                      {STATUS_META[svc.status]?.icon} {STATUS_META[svc.status]?.label}
                    </span>
                  )}
                  <span className={styles.dockerCount}>{svc.containers?.length || 0} running</span>
                </div>
                {svc.containers?.length > 0 && (
                  <div className={styles.dockerList}>
                    {svc.containers.map((c, i) => (
                      <span key={i} className={styles.dockerTag}>
                        <Container size={11} />
                        {c}
                      </span>
                    ))}
                  </div>
                )}
                {svc.detail && svc.detail !== '{0} running container(s)'.replace('{0}', svc.containers?.length || 0) && (
                  <div style={{ padding: '0 18px 14px', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    {svc.detail}
                  </div>
                )}
              </div>
            )
          }

          const icon = SERVICE_ICONS[key] || { icon: <Activity size={17} />, color: '#6B7280', bg: '#F9FAFB' }
          const meta = STATUS_META[svc.status] || STATUS_META.down
          const label = SERVICE_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

          return (
            <div key={key} className={styles.card}>
              <div className={styles.cardIcon} style={{ background: icon.bg, color: icon.color }}>
                {icon.icon}
              </div>
              <div className={styles.cardBody}>
                <div className={styles.cardName}>{label}</div>
                {svc.detail && <p className={styles.cardDetail}>{svc.detail}</p>}
              </div>
              <span className={styles.cardBadge} style={{ background: meta.bg, color: meta.color }}>
                {meta.icon} {meta.label}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
