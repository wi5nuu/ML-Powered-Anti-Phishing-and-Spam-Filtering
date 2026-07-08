import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMe } from '../api/auth'
import api from '../api/client'
import {
  Inbox, Shield, ShieldCheck, ShieldAlert, AlertTriangle,
  Mail, BarChart3, Settings, ExternalLink, Clock,
  Sparkles, Lock, Eye, FileWarning,
  ChevronRight, RefreshCw
} from 'lucide-react'
import styles from './UserDashboardPage.module.css'

const LABEL_STYLES = {
  QUARANTINE: { color: '#c5221f', bg: '#fce8e6', icon: ShieldAlert, label: 'Quarantine' },
  WARN: { color: '#856404', bg: '#fef3cd', icon: AlertTriangle, label: 'Suspicious' },
}

function formatDate(d) {
  if (!d) return ''
  try { return new Date(d).toLocaleDateString('id-ID', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) }
  catch { return d }
}

export default function UserDashboardPage() {
  const { data: auth } = useMe()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchDashboard = useCallback(() => {
    setLoading(true)
    setError(null)
    api.get('/api/user/dashboard')
      .then((r) => { setData(r.data); setLoading(false) })
      .catch((err) => { setError(err.response?.data?.detail || err.message); setLoading(false) })
  }, [])

  useEffect(() => { fetchDashboard() }, [fetchDashboard])

  const user = auth?.user
  const today = new Date().toLocaleDateString('id-ID', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  })

  if (loading) {
    return (
      <div className={styles.wrap}>
        <div style={{ padding: '60px 20px', textAlign: 'center', color: '#9CA3AF' }}>Loading dashboard...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.wrap}>
        <div style={{ padding: '60px 20px', textAlign: 'center', color: '#EF4444' }}>
          <p>Failed to load dashboard: {error}</p>
          <button onClick={fetchDashboard} style={{ marginTop: 12, padding: '8px 20px', border: '1px solid #D1D5DB', borderRadius: 8, background: '#fff', cursor: 'pointer' }}>
            <RefreshCw size={14} style={{ marginRight: 6 }} /> Retry
          </button>
        </div>
      </div>
    )
  }

  const total = data?.total_inbox || 0
  const safe = data?.safe || 0
  const spam = data?.spam || 0
  const phishing = data?.phishing || 0
  const quarantined = data?.quarantined || 0
  const alerts = data?.recent_alerts || []
  const mailbox = data?.mailbox
  const safePct = total > 0 ? Math.round((safe / total) * 100) : 0

  return (
    <div className={styles.wrap}>
      <div className={styles.hero}>
        <div className={styles.heroLeft}>
          <div className={styles.heroGreet}>
            <h1 className={styles.heroTitle}>
              Welcome back, <span className={styles.heroName}>{user?.username || 'User'}</span>
            </h1>
            <span className={styles.heroBadge}>
              <ShieldCheck size={13} />
              Protected
            </span>
          </div>
          <p className={styles.heroSub}>
            Your email security dashboard — monitor threats, review alerts, and manage your inbox.
          </p>
          <p className={styles.heroDate}>{today}</p>
        </div>
        <div className={styles.heroRight}>
          <div className={styles.protectionCard}>
            <div className={styles.protCardHeader}>
              <Shield size={14} />
              Protection Status
            </div>
            <div className={styles.protStatus}>
              <span className={styles.protStatusDot} />
              <span className={styles.protStatusText}>Active</span>
            </div>
            <div className={styles.protStats}>
              <div className={styles.protStat}>
                <span className={styles.protStatValue} style={{ color: '#059669' }}>{safePct}%</span>
                <span className={styles.protStatLabel}>Safe Rate</span>
              </div>
              <div className={styles.protStat}>
                <span className={styles.protStatValue} style={{ color: '#DC2626' }}>{(phishing + spam)}</span>
                <span className={styles.protStatLabel}>Blocked</span>
              </div>
            </div>
            {mailbox && (
              <div className={styles.protLastScan}>
                <Mail size={11} />
                {mailbox.email}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className={styles.statsGrid}>
        <div className={styles.statCard} onClick={() => navigate('/inbox')}>
          <div className={styles.scIcon} style={{ background: '#EFF6FF', color: '#2563EB' }}>
            <Inbox size={18} />
          </div>
          <div className={styles.scBody}>
            <span className={styles.scValue}>{total}</span>
            <span className={styles.scLabel}>Total Inbox</span>
            <span className={styles.scSub}>All processed emails</span>
          </div>
          <ChevronRight size={14} className={styles.scArrow} />
        </div>

        <div className={styles.statCard} onClick={() => navigate('/inbox')}>
          <div className={styles.scIcon} style={{ background: '#ECFDF5', color: '#059669' }}>
            <ShieldCheck size={18} />
          </div>
          <div className={styles.scBody}>
            <span className={styles.scValue}>{safe}</span>
            <span className={styles.scLabel}>Safe Emails</span>
            <span className={styles.scSub}>{safePct}% of inbox</span>
          </div>
          <ChevronRight size={14} className={styles.scArrow} />
        </div>

        <div className={styles.statCard} onClick={() => navigate('/mail/' + (mailbox?.id || '') + '/spam')}>
          <div className={styles.scIcon} style={{ background: '#FFFBEB', color: '#D97706' }}>
            <FileWarning size={18} />
          </div>
          <div className={styles.scBody}>
            <span className={styles.scValue}>{spam}</span>
            <span className={styles.scLabel}>Spam Blocked</span>
            <span className={styles.scSub}>Suspicious messages</span>
          </div>
          <ChevronRight size={14} className={styles.scArrow} />
        </div>

        <div className={styles.statCard} onClick={() => navigate('/mail/' + (mailbox?.id || '') + '/phishing')}>
          <div className={styles.scIcon} style={{ background: '#FEF2F2', color: '#DC2626' }}>
            <ShieldAlert size={18} />
          </div>
          <div className={styles.scBody}>
            <span className={styles.scValue}>{phishing}</span>
            <span className={styles.scLabel}>Phishing Blocked</span>
            <span className={styles.scSub}>Malicious emails</span>
          </div>
          <ChevronRight size={14} className={styles.scArrow} />
        </div>

        <div className={styles.statCard} onClick={() => navigate('/inbox')}>
          <div className={styles.scIcon} style={{ background: '#F3E8FF', color: '#7C3AED' }}>
            <AlertTriangle size={18} />
          </div>
          <div className={styles.scBody}>
            <span className={styles.scValue}>{quarantined}</span>
            <span className={styles.scLabel}>Quarantined</span>
            <span className={styles.scSub}>Awaiting review</span>
          </div>
          <ChevronRight size={14} className={styles.scArrow} />
        </div>
      </div>

      <div className={styles.contentGrid}>
        <div className={styles.col}>
          <div className={styles.sectionCard}>
            <div className={styles.scardHeader}>
              <Eye size={15} className={styles.scardIcon} />
              <span>Recent Security Alerts</span>
              {alerts.length > 0 && (
                <button className={styles.scardLink} onClick={() => navigate('/inbox')}>
                  View All
                </button>
              )}
            </div>
            {alerts.length === 0 ? (
              <div style={{ padding: '28px 18px', textAlign: 'center', color: '#9CA3AF', fontSize: '0.82rem' }}>
                <ShieldCheck size={24} style={{ margin: '0 auto 8px', opacity: 0.5 }} />
                No recent security alerts
              </div>
            ) : (
              <div className={styles.eventList}>
                {alerts.slice(0, 6).map((alert) => {
                  const style = LABEL_STYLES[alert.label] || LABEL_STYLES.WARN
                  const Icon = style.icon
                  return (
                    <div key={alert.email_id} className={styles.eventRow}>
                      <div className={styles.eventIconWrap} style={{ background: style.bg, color: style.color }}>
                        <Icon size={14} />
                      </div>
                      <div className={styles.eventBody}>
                        <span className={styles.eventLabel} style={{ color: style.color }}>
                          {style.label}
                        </span>
                        <span className={styles.eventDesc}>
                          {alert.sender} — {alert.subject || '(no subject)'}
                        </span>
                      </div>
                      <span className={styles.eventTime}>{formatDate(alert.received_at)}</span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          <div className={styles.sectionCard}>
            <div className={styles.scardHeader}>
              <Sparkles size={15} className={styles.scardIcon} />
              <span>Security Tips</span>
            </div>
            <div className={styles.tipsList}>
              <div className={styles.tipItem}>
                <span className={styles.tipIcon}>🔍</span>
                <span className={styles.tipText}>Always verify the sender's email address before clicking links.</span>
              </div>
              <div className={styles.tipItem}>
                <span className={styles.tipIcon}>🛡️</span>
                <span className={styles.tipText}>Report suspicious emails using the "Report" button in your inbox.</span>
              </div>
              <div className={styles.tipItem}>
                <span className={styles.tipIcon}>🔐</span>
                <span className={styles.tipText}>Use strong passwords and enable two-factor authentication.</span>
              </div>
              <div className={styles.tipItem}>
                <span className={styles.tipIcon}>⚠️</span>
                <span className={styles.tipText}>Be cautious of urgent requests for personal information.</span>
              </div>
            </div>
          </div>
        </div>

        <div className={styles.col}>
          <div className={styles.sectionCard}>
            <div className={styles.scardHeader}>
              <BarChart3 size={15} className={styles.scardIcon} />
              <span>Security Score</span>
            </div>
            <div className={styles.scoreSummary}>
              <div
                className={styles.scoreCircle}
                style={{ '--pct': safePct }}
              >
                <span className={styles.scoreValue}>{safePct}</span>
                <span className={styles.scorePct}>%</span>
                <span className={styles.scoreLabel}>Safe</span>
              </div>
              <div className={styles.scoreStats}>
                <div className={styles.scoreStatRow}>
                  <span className={styles.scoreDot} style={{ background: '#059669' }} />
                  <span className={styles.scoreStatLabel}>Safe / Ham</span>
                  <span className={styles.scoreStatVal}>{safe}</span>
                </div>
                <div className={styles.scoreStatRow}>
                  <span className={styles.scoreDot} style={{ background: '#D97706' }} />
                  <span className={styles.scoreStatLabel}>Spam / Suspicious</span>
                  <span className={styles.scoreStatVal}>{spam}</span>
                </div>
                <div className={styles.scoreStatRow}>
                  <span className={styles.scoreDot} style={{ background: '#DC2626' }} />
                  <span className={styles.scoreStatLabel}>Phishing / Malware</span>
                  <span className={styles.scoreStatVal}>{phishing}</span>
                </div>
                <div className={styles.scoreStatRow}>
                  <span className={styles.scoreDot} style={{ background: '#7C3AED' }} />
                  <span className={styles.scoreStatLabel}>Quarantined</span>
                  <span className={styles.scoreStatVal}>{quarantined}</span>
                </div>
              </div>
            </div>
          </div>

          <div className={styles.sectionCard}>
            <div className={styles.scardHeader}>
              <ExternalLink size={15} className={styles.scardIcon} />
              <span>Quick Actions</span>
            </div>
            <div className={styles.quickActions}>
              <button className={`${styles.qaBtn} ${styles.qaBtnPrimary}`} onClick={() => navigate('/inbox')}>
                <Inbox size={18} />
                Open Inbox
              </button>
              <button className={`${styles.qaBtn} ${styles.qaBtnSecondary}`} onClick={() => navigate('/metrics')}>
                <BarChart3 size={18} />
                View Metrics
              </button>
              <button className={`${styles.qaBtn} ${styles.qaBtnWarning}`} onClick={() => navigate('/settings')}>
                <Settings size={18} />
                Settings
              </button>
              <button className={`${styles.qaBtn} ${styles.qaBtnDanger}`} onClick={() => navigate('/help')}>
                <Lock size={18} />
                Security Guide
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
