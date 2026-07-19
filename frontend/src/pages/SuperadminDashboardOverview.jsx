import { useState, useEffect } from 'react'
import api from '../api/client'
import {
  Users, Mail, Inbox, ShieldAlert, AlertTriangle, AlertCircle,
  Server, Activity, Clock, Shield, ExternalLink, Wifi, Database,
  CheckCircle2, XCircle, ShieldCheck, Eye, TrendingUp, TrendingDown,
  ChevronDown, ChevronRight, FileText, Download
} from 'lucide-react'
import styles from './SuperadminDashboardOverview.module.css'

export default function SuperadminDashboardOverview() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedAdmin, setExpandedAdmin] = useState(null)

  useEffect(() => {
    api.get('/admin/superadmin-dashboard')
      .then((r) => { setData(r.data); setLoading(false) })
      .catch((err) => { setError(err.response?.data?.detail || err.message); setLoading(false) })
  }, [])

  const pct = (num, total) => total > 0 ? ((num / total) * 100).toFixed(1) : '0.0'
  const safePct = data ? Number(pct(data.total_clean, data.total_emails_processed)) : 0
  const spamPct = data ? Number(pct(data.total_spam + data.total_warn, data.total_emails_processed)) : 0
  const phishPct = data ? Number(pct(data.total_phishing, data.total_emails_processed)) : 0
  const quarPct = data ? Number(pct(data.total_quarantined, data.total_emails_processed)) : 0

  if (loading) {
    return (
      <div className={styles.loadingState}>
        <div className={styles.spinner} />
        <span>Memuat dashboard...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.errorState}>
        <XCircle size={32} />
        <h3>Gagal Memuat Dashboard</h3>
        <p>{error}</p>
        <button className={styles.retryBtn} onClick={() => window.location.reload()}>Coba Lagi</button>
      </div>
    )
  }

  const health = data.system_health || {}
  const healthIcon = health.database === 'connected' ? CheckCircle2 : XCircle
  const healthColor = health.database === 'connected' ? '#059669' : '#DC2626'

  return (
    <div className={styles.page}>
      {/* Hero Header */}
      <div className={styles.hero}>
        <div className={styles.heroLeft}>
          <div className={styles.heroTitleRow}>
            <h1 className={styles.heroTitle}>Superadmin Dashboard</h1>
            <span className={styles.badge}>Superadmin</span>
          </div>
          <p className={styles.heroSub}>Monitor platform security, users, mailboxes, and system health.</p>
        </div>
        <div className={styles.heroRight}>
          <button className={styles.exportBtn} onClick={() => {
            window.open('/api/admin/export-report/pdf', '_blank')
          }} title="Download PDF Report">
            <FileText size={13} /> PDF
          </button>
          <button className={styles.exportBtn} onClick={() => {
            window.open('/api/admin/export-report/excel', '_blank')
          }} title="Download Excel Report">
            <Download size={13} /> Excel
          </button>
          <Clock size={13} />
          <span>{new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      </div>

      {/* Stats Cards */}
      <div className={styles.statsGrid}>
        <div className={`${styles.statCard} ${styles.scPurple}`}>
          <div className={styles.statIcon}><Users size={20} /></div>
          <div className={styles.statBody}>
            <span className={styles.statValue}>{data.total_users}</span>
            <span className={styles.statLabel}>Total Users</span>
            <span className={styles.statSub}>{data.active_users} active</span>
          </div>
        </div>

        <div className={`${styles.statCard} ${styles.scIndigo}`}>
          <div className={styles.statIcon}><Mail size={20} /></div>
          <div className={styles.statBody}>
            <span className={styles.statValue}>{data.total_mailboxes}</span>
            <span className={styles.statLabel}>Active Mailboxes</span>
            <span className={styles.statSub}>Registered mailboxes</span>
          </div>
        </div>

        <div className={`${styles.statCard} ${styles.scBlue}`}>
          <div className={styles.statIcon}><Inbox size={20} /></div>
          <div className={styles.statBody}>
            <span className={styles.statValue}>{data.total_emails_processed}</span>
            <span className={styles.statLabel}>Emails Processed</span>
            <span className={styles.statSub}>{data.total_clean} safe</span>
          </div>
        </div>

        <div className={`${styles.statCard} ${styles.scOrange}`}>
          <div className={styles.statIcon}><AlertTriangle size={20} /></div>
          <div className={styles.statBody}>
            <span className={styles.statValue}>{data.total_spam}</span>
            <span className={styles.statLabel}>Spam Detected</span>
            <span className={styles.statSub}>{spamPct}% of total</span>
          </div>
        </div>

        <div className={`${styles.statCard} ${styles.scRed}`}>
          <div className={styles.statIcon}><ShieldAlert size={20} /></div>
          <div className={styles.statBody}>
            <span className={styles.statValue}>{data.total_phishing}</span>
            <span className={styles.statLabel}>Phishing Detected</span>
            <span className={styles.statSub}>{phishPct}% of total</span>
          </div>
        </div>

        <div className={`${styles.statCard} ${styles.scDarkRed}`}>
          <div className={styles.statIcon}><AlertCircle size={20} /></div>
          <div className={styles.statBody}>
            <span className={styles.statValue}>{data.total_quarantined}</span>
            <span className={styles.statLabel}>Quarantined Emails</span>
            <span className={styles.statSub}>{quarPct}% quarantine rate</span>
          </div>
        </div>

        <div className={`${styles.statCard} ${styles.scPurple}`}>
          <div className={styles.statIcon}><ShieldAlert size={20} /></div>
          <div className={styles.statBody}>
            <span className={styles.statValue}>{data.total_malware || 0}</span>
            <span className={styles.statLabel}>Malware Detected</span>
            <span className={styles.statSub}>Malicious attachments</span>
          </div>
        </div>

        <div className={`${styles.statCard} ${styles.scGreen}`}>
          <div className={styles.statIcon}><Server size={20} /></div>
          <div className={styles.statBody}>
            <span className={styles.statValue} style={{ color: healthColor }}>
              {health.database === 'connected' ? 'Online' : 'Offline'}
            </span>
            <span className={styles.statLabel}>System Health</span>
            <span className={styles.statSub}>All services {health.database === 'connected' ? 'operational' : 'degraded'}</span>
          </div>
        </div>
      </div>

      {/* Admin & User Hierarchy */}
      {data.admins && data.admins.length > 0 && (
        <div className={styles.adminSection}>
          <div className={styles.adminSectionHeader}>
            <Users size={16} />
            <span>Admin & User Hierarchy</span>
            <span className={styles.cardBadge}>{data.admins.length} admins</span>
          </div>
          <div className={styles.adminList}>
            {data.admins.map((adm) => (
              <div key={adm.username} className={styles.adminCard}>
                <div className={styles.adminCardHeader} onClick={() => setExpandedAdmin(expandedAdmin === adm.username ? null : adm.username)}>
                  <div className={styles.adminAvatar} style={{ background: '#EEF2FF', color: '#4F46E5' }}>
                    {adm.username.slice(0, 2).toUpperCase()}
                  </div>
                  <div className={styles.adminInfo}>
                    <span className={styles.adminName}>{adm.username}</span>
                    <span className={styles.adminOrg}>{adm.organization_name || 'No Organization'}</span>
                  </div>
                  <div className={styles.adminStats}>
                    <span className={styles.adminStat}><Users size={12} /> {adm.total_users} users</span>
                  </div>
                  {expandedAdmin === adm.username ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </div>
                {expandedAdmin === adm.username && adm.users && (
                  <div className={styles.adminUsersTable}>
                    <table className={styles.adminTable}>
                      <thead>
                        <tr>
                          <th>Username</th>
                          <th>Email</th>
                          <th>Total</th>
                          <th style={{ color: '#059669' }}>Clean</th>
                          <th style={{ color: '#D97706' }}>Spam</th>
                          <th style={{ color: '#DC2626' }}>Phishing</th>
                          <th style={{ color: '#7C3AED' }}>Malware</th>
                        </tr>
                      </thead>
                      <tbody>
                        {adm.users.map((u) => (
                          <tr key={u.username}>
                            <td><span className={styles.userBadge}>{u.username}</span></td>
                            <td className={styles.mono}>{u.email}</td>
                            <td className={styles.numCell}>{u.total_emails}</td>
                            <td className={styles.numCell} style={{ color: '#059669' }}>{u.clean}</td>
                            <td className={styles.numCell} style={{ color: '#D97706' }}>{u.spam}</td>
                            <td className={styles.numCell} style={{ color: '#DC2626' }}>{u.phishing}</td>
                            <td className={styles.numCell} style={{ color: '#7C3AED' }}>{u.malware}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Two-Column Dashboard */}
      <div className={styles.dashGrid}>
        {/* Left Column */}
        <div className={styles.dashCol}>

          {/* Security Overview */}
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <Shield size={16} />
              <span>Security Overview</span>
            </div>
            <div className={styles.securityBars}>
              <div className={styles.secBar}>
                <div className={styles.secBarMeta}>
                  <span className={styles.secBarLabel}>
                    <span className={styles.secDot} style={{ background: '#059669' }} />
                    Safe / Clean
                  </span>
                  <span className={styles.secBarCount}>{data.total_clean}</span>
                </div>
                <div className={styles.secBarTrack}>
                  <div className={styles.secBarFill} style={{ width: `${safePct}%`, background: '#059669' }} />
                </div>
                <span className={styles.secBarPct}>{safePct}%</span>
              </div>

              <div className={styles.secBar}>
                <div className={styles.secBarMeta}>
                  <span className={styles.secBarLabel}>
                    <span className={styles.secDot} style={{ background: '#D97706' }} />
                    Spam / Warn
                  </span>
                  <span className={styles.secBarCount}>{data.total_spam + data.total_warn}</span>
                </div>
                <div className={styles.secBarTrack}>
                  <div className={styles.secBarFill} style={{ width: `${spamPct}%`, background: '#D97706' }} />
                </div>
                <span className={styles.secBarPct}>{spamPct}%</span>
              </div>

              <div className={styles.secBar}>
                <div className={styles.secBarMeta}>
                  <span className={styles.secBarLabel}>
                    <span className={styles.secDot} style={{ background: '#DC2626' }} />
                    Phishing
                  </span>
                  <span className={styles.secBarCount}>{data.total_phishing}</span>
                </div>
                <div className={styles.secBarTrack}>
                  <div className={styles.secBarFill} style={{ width: `${phishPct}%`, background: '#DC2626' }} />
                </div>
                <span className={styles.secBarPct}>{phishPct}%</span>
              </div>

              <div className={styles.secBar}>
                <div className={styles.secBarMeta}>
                  <span className={styles.secBarLabel}>
                    <span className={styles.secDot} style={{ background: '#7C3AED' }} />
                    Quarantined
                  </span>
                  <span className={styles.secBarCount}>{data.total_quarantined}</span>
                </div>
                <div className={styles.secBarTrack}>
                  <div className={styles.secBarFill} style={{ width: `${quarPct}%`, background: '#7C3AED' }} />
                </div>
                <span className={styles.secBarPct}>{quarPct}%</span>
              </div>
            </div>
          </div>

          {/* Recent Security Detections */}
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <ShieldAlert size={16} />
              <span>Recent Security Detections</span>
              <span className={styles.cardBadge}>{data.recent_security_detections?.length || 0}</span>
            </div>
            {data.recent_security_detections?.length > 0 ? (
              <div className={styles.detectionList}>
                {data.recent_security_detections.map((det, idx) => (
                  <div key={idx} className={styles.detectionRow}>
                    <div className={styles.detIcon} style={{
                      background: det.label === 'QUARANTINE' ? '#FEF2F2' : '#FFFBEB',
                      color: det.label === 'QUARANTINE' ? '#DC2626' : '#D97706'
                    }}>
                      {det.label === 'QUARANTINE' ? <ShieldAlert size={14} /> : <AlertTriangle size={14} />}
                    </div>
                    <div className={styles.detBody}>
                      <span className={styles.detSubject}>{det.subject || '(no subject)'}</span>
                      <span className={styles.detSender}>{det.sender}</span>
                    </div>
                    <div className={styles.detMeta}>
                      <span className={styles.detLabel} style={{
                        background: det.label === 'QUARANTINE' ? '#FEF2F2' : '#FFFBEB',
                        color: det.label === 'QUARANTINE' ? '#DC2626' : '#D97706'
                      }}>
                        {det.label === 'QUARANTINE' ? 'QUARANTINE' : 'WARN'}
                      </span>
                      <span className={styles.detCategory}>{det.category}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className={styles.emptyState}>
                <ShieldCheck size={24} />
                <p>No recent security detections</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column */}
        <div className={styles.dashCol}>

          {/* System Health */}
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <Server size={16} />
              <span>System Health</span>
            </div>
            <div className={styles.healthGrid}>
              <div className={styles.healthItem}>
                <div className={styles.healthIcon} style={{ background: '#ECFDF5', color: '#059669' }}>
                  <Wifi size={16} />
                </div>
                <div className={styles.healthBody}>
                  <span className={styles.healthLabel}>API Status</span>
                  <span className={styles.healthValue} style={{ color: '#059669' }}>
                    {health.status || 'healthy'}
                  </span>
                </div>
              </div>
              <div className={styles.healthItem}>
                <div className={styles.healthIcon} style={{ background: health.database === 'connected' ? '#ECFDF5' : '#FEF2F2', color: health.database === 'connected' ? '#059669' : '#DC2626' }}>
                  <Database size={16} />
                </div>
                <div className={styles.healthBody}>
                  <span className={styles.healthLabel}>Database</span>
                  <span className={styles.healthValue} style={{ color: health.database === 'connected' ? '#059669' : '#DC2626' }}>
                    {health.database === 'connected' ? 'Connected' : 'Error'}
                  </span>
                </div>
              </div>
              <div className={styles.healthItem}>
                <div className={styles.healthIcon} style={{ background: '#EFF6FF', color: '#2563EB' }}>
                  <Activity size={16} />
                </div>
                <div className={styles.healthBody}>
                  <span className={styles.healthLabel}>WebSocket</span>
                  <span className={styles.healthValue}>{health.websocket_connections || 0} connections</span>
                </div>
              </div>
            </div>
          </div>

          {/* Recent Activities */}
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <Activity size={16} />
              <span>Recent Activities</span>
              <span className={styles.cardBadge}>{data.recent_activities?.length || 0}</span>
            </div>
            {data.recent_activities?.length > 0 ? (
              <div className={styles.activityList}>
                {data.recent_activities.slice(0, 10).map((act, idx) => (
                  <div key={idx} className={styles.activityRow}>
                    <div className={styles.activityDot} />
                    <div className={styles.activityBody}>
                      <span className={styles.activityAction}>{act.action}</span>
                      {act.details && <span className={styles.activityDetail}>{act.details}</span>}
                      {act.ip_address && <span className={styles.activityIp}>IP: {act.ip_address}</span>}
                    </div>
                    <div className={styles.activityMeta}>
                      <span className={styles.activityUser}>{act.user}</span>
                      <span className={styles.activityTime}>
                        {act.created_at ? new Date(act.created_at).toLocaleDateString('id-ID', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className={styles.emptyState}>
                <Activity size={24} />
                <p>No recent activities</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
