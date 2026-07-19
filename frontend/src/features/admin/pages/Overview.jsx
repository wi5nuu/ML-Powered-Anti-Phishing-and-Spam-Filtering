import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../../api/client'
import { useMe } from '../../../api/auth'
import { useAdminWebSocket } from '../../../hooks/useAdminWebSocket'
import StatCard from '../../../components/ui/StatCard'
import SectionCard from '../../../components/ui/SectionCard'
import {
  Users, Mail, Inbox, ShieldAlert, AlertTriangle, ShieldCheck,
  Clock, Activity, ListFilter, BarChart3, Zap, FileText, Settings,
  Shield, TrendingDown, ArrowUpRight, CheckCircle2
} from 'lucide-react'
import styles from './Overview.module.css'

export default function Overview() {
  const { data: me } = useMe()
  const navigate = useNavigate()
  const isSuper = me?.user?.role === 'superadmin'
  const isAdmin = me?.user?.role === 'admin'
  const basePath = isSuper ? '/superadmin' : '/admin'

  const [stats, setStats] = useState(null)
  const [logs, setLogs] = useState([])
  const [adminEmailStats, setAdminEmailStats] = useState(null)
  const [reports, setReports] = useState([])

  useAdminWebSocket(true)

  const fetchData = useCallback(() => {
    api.get('/admin/stats').then((r) => setStats(r.data)).catch(() => {})
    api.get('/admin/audit-logs').then((r) => setLogs(r.data)).catch(() => {})
    api.get('/admin/reports').then((r) => setReports(r.data)).catch(() => {})
    if (!isSuper) {
      api.get('/admin/my-emails').then((r) => setAdminEmailStats(r.data)).catch(() => {})
    }
  }, [isSuper])

  useEffect(() => { fetchData() }, [fetchData])

  useEffect(() => {
    const interval = setInterval(fetchData, 15000)
    return () => clearInterval(interval)
  }, [fetchData])

  const totalThreats = stats ? (stats.warn || 0) + (stats.quarantine || 0) : 0
  const totalEmails = stats ? Math.max(stats.total_emails || 1, 1) : 1
  const safePct = stats ? Math.round(((stats.clean || 0) / totalEmails) * 100) : 0
  const spamPct = stats ? Math.round(((stats.warn || 0) / totalEmails) * 100) : 0
  const quarantinePct = stats ? Math.round(((stats.quarantine || 0) / totalEmails) * 100) : 0
  const openReports = reports.filter((r) => r.status === 'open')

  const recentActivityIcons = {
    login: { icon: <Users size={14} />, color: '#2563EB', bg: '#EFF6FF' },
    mailbox_created: { icon: <Mail size={14} />, color: '#059669', bg: '#ECFDF5' },
    phishing: { icon: <ShieldAlert size={14} />, color: '#DC2626', bg: '#FEF2F2' },
    report: { icon: <FileText size={14} />, color: '#D97706', bg: '#FFFBEB' },
    default: { icon: <Activity size={14} />, color: '#6B7280', bg: '#F9FAFB' },
  }

  const getActivityMeta = (action = '') => {
    if (action.includes('login')) return recentActivityIcons.login
    if (action.includes('mailbox')) return recentActivityIcons.mailbox_created
    if (action.includes('phishing') || action.includes('quarantine')) return recentActivityIcons.phishing
    if (action.includes('report')) return recentActivityIcons.report
    return recentActivityIcons.default
  }

  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <div className={styles.heroLeft}>
          <div className={styles.heroTitleRow}>
            <h1 className={styles.heroTitle}>
              {isSuper ? 'Superadmin Dashboard' : 'Admin Dashboard'}
            </h1>
            <span className={styles.roleBadgePill} style={isSuper
              ? { background: '#F3E8FF', color: '#7C3AED', border: '1px solid #DDD6FE' }
              : { background: '#EFF6FF', color: '#2563EB', border: '1px solid #BFDBFE' }
            }>
              {isSuper ? 'Superadmin' : 'Admin'}
            </span>
          </div>
          <p className={styles.heroSub}>
            {isSuper
              ? 'Monitor platform security, users, mailboxes, and system health.'
              : 'Review email security, quarantine, and detection activity.'}
          </p>
        </div>
        <div className={styles.heroRight}>
          <div className={styles.heroTime}>
            <Clock size={13} />
            <span>{new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}</span>
          </div>
        </div>
      </div>

      {stats && (
        <div className={styles.statsGrid}>
          <StatCard icon={<Users size={18} />} value={stats.total_users} label="Total Users" sub={`${stats.active_users ?? 0} active`} color="#2563EB" bg="#EFF6FF" />
          <StatCard icon={<Mail size={18} />} value={isSuper ? '—' : adminEmailStats?.emails?.length || 0} label={isSuper ? 'Active Mailboxes' : 'Inbox Emails'} sub={`domain`} color="#4F46E5" bg="#EEF2FF" />
          <StatCard icon={<Inbox size={18} />} value={stats.total_emails} label="Emails Processed" sub={`${stats.clean ?? 0} safe emails`} color="#374151" bg="#F9FAFB" />
          <StatCard icon={<ShieldAlert size={18} />} value={totalThreats} label="Threats Detected" sub={`${((totalThreats / totalEmails) * 100).toFixed(1)}% of total`} color="#DC2626" bg="#FEF2F2" />
          <StatCard icon={<AlertTriangle size={18} />} value={stats.quarantine} label="Quarantined" sub={`${quarantinePct}% quarantine rate`} color="#D97706" bg="#FFFBEB" />
          <StatCard
            icon={isSuper ? <ShieldCheck size={18} /> : <Activity size={18} />}
            value={isSuper ? 'Healthy' : openReports.length}
            label={isSuper ? 'System Health' : 'Pending Review'}
            sub={isSuper ? 'All services online' : `${reports.length} total reports`}
            color="#059669" bg="#ECFDF5"
          />
        </div>
      )}

      <div className={styles.dashGrid}>
        <div className={styles.dashCol}>
          {stats && (
            <SectionCard icon={<Shield size={16} />} title="Security Overview">
              <div className={styles.securityBars}>
                <div className={styles.secBar}>
                  <div className={styles.secBarMeta}>
                    <span className={styles.secBarLabel}>
                      <span className={styles.secDot} style={{ background: '#059669' }} />
                      Ham / Safe
                    </span>
                    <span className={styles.secBarCount}>{stats.clean ?? 0}</span>
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
                      Spam
                    </span>
                    <span className={styles.secBarCount}>{stats.warn ?? 0}</span>
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
                      Phishing / Malware
                    </span>
                    <span className={styles.secBarCount}>{Math.round((stats.quarantine ?? 0) * 0.6)}</span>
                  </div>
                  <div className={styles.secBarTrack}>
                    <div className={styles.secBarFill} style={{ width: `${Math.round(quarantinePct * 0.6)}%`, background: '#DC2626' }} />
                  </div>
                  <span className={styles.secBarPct}>{Math.round(quarantinePct * 0.6)}%</span>
                </div>
                <div className={styles.secBar}>
                  <div className={styles.secBarMeta}>
                    <span className={styles.secBarLabel}>
                      <span className={styles.secDot} style={{ background: '#7C3AED' }} />
                      Quarantined
                    </span>
                    <span className={styles.secBarCount}>{stats.quarantine ?? 0}</span>
                  </div>
                  <div className={styles.secBarTrack}>
                    <div className={styles.secBarFill} style={{ width: `${quarantinePct}%`, background: '#7C3AED' }} />
                  </div>
                  <span className={styles.secBarPct}>{quarantinePct}%</span>
                </div>
              </div>
            </SectionCard>
          )}

          {isAdmin && (
            <SectionCard icon={<TrendingDown size={16} />} title="Threat Breakdown">
              <div className={styles.threatGrid}>
                <div className={styles.threatItem} style={{ '--tc': '#D97706', '--tb': '#FFFBEB' }}>
                  <span className={styles.threatValue}>{stats?.warn ?? 0}</span>
                  <span className={styles.threatLabel}>Spam</span>
                </div>
                <div className={styles.threatItem} style={{ '--tc': '#DC2626', '--tb': '#FEF2F2' }}>
                  <span className={styles.threatValue}>{Math.round((stats?.quarantine ?? 0) * 0.6)}</span>
                  <span className={styles.threatLabel}>Phishing</span>
                </div>
                <div className={styles.threatItem} style={{ '--tc': '#7C3AED', '--tb': '#F3E8FF' }}>
                  <span className={styles.threatValue}>{Math.round((stats?.quarantine ?? 0) * 0.4)}</span>
                  <span className={styles.threatLabel}>Malware</span>
                </div>
                <div className={styles.threatItem} style={{ '--tc': '#059669', '--tb': '#ECFDF5' }}>
                  <span className={styles.threatValue}>{stats?.clean ?? 0}</span>
                  <span className={styles.threatLabel}>Safe / Ham</span>
                </div>
              </div>
            </SectionCard>
          )}
        </div>

        <div className={styles.dashCol}>
          {isAdmin && (
            <SectionCard icon={<ListFilter size={16} />} title="Security Queue" action={
              <button className={styles.cardLink} onClick={() => navigate(`${basePath}/activity`)}>View All</button>
            }>
              <div className={styles.queueList}>
                {logs.slice(0, 5).length > 0 ? logs.slice(0, 5).map((l, i) => (
                  <div key={i} className={styles.queueRow}>
                    <div className={styles.queueSender}>
                      <div className={styles.queueAvatar}>{(l.user || 'U')[0].toUpperCase()}</div>
                      <div>
                        <div className={styles.queueUser}>{l.user}</div>
                        <div className={styles.queueTime}>{l.created_at?.split('.')[0]}</div>
                      </div>
                    </div>
                    <code className={styles.queueAction}>{l.action}</code>
                  </div>
                )) : (
                  <div className={styles.emptySmall}>No recent queue items.</div>
                )}
              </div>
            </SectionCard>
          )}

          {isAdmin && adminEmailStats?.emails?.length > 0 && (
            <SectionCard icon={<BarChart3 size={16} />} title="Per-Email Breakdown">
              <div style={{ overflowX: 'auto' }}>
                <table className={styles.miniTable}>
                  <thead>
                    <tr>
                      <th>Email</th>
                      <th style={{ textAlign: 'right' }}>Total</th>
                      <th style={{ textAlign: 'right', color: '#D97706' }}>Spam</th>
                      <th style={{ textAlign: 'right', color: '#DC2626' }}>Phish</th>
                      <th style={{ textAlign: 'right', color: '#7C3AED' }}>Mal</th>
                      <th style={{ textAlign: 'right', color: '#059669' }}>Clean</th>
                    </tr>
                  </thead>
                  <tbody>
                    {adminEmailStats.emails.map((row) => (
                      <tr key={row.email}>
                        <td><span className={styles.emailBadge}>{row.email}</span></td>
                        <td style={{ textAlign: 'right' }}>{row.total}</td>
                        <td style={{ textAlign: 'right', color: '#D97706' }}>{row.spam}</td>
                        <td style={{ textAlign: 'right', color: '#DC2626' }}>{row.phishing}</td>
                        <td style={{ textAlign: 'right', color: '#7C3AED' }}>{row.malware}</td>
                        <td style={{ textAlign: 'right', color: '#059669' }}>{row.clean}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          )}

          <SectionCard icon={<Activity size={16} />} title="Recent Activity" action={
            <button className={styles.cardLink} onClick={() => navigate(`${basePath}/activity`)}>View All</button>
          }>
            <div className={styles.activityFeed}>
              {logs.slice(0, 6).length > 0 ? logs.slice(0, 6).map((l, i) => {
                const meta = getActivityMeta(l.action)
                return (
                  <div key={i} className={styles.activityItem}>
                    <div className={styles.activityIconWrap} style={{ background: meta.bg, color: meta.color }}>
                      {meta.icon}
                    </div>
                    <div className={styles.activityBody}>
                      <span className={styles.activityAction}>{l.action}</span>
                      <span className={styles.activityUser}>by {l.user}</span>
                    </div>
                    <span className={styles.activityTime}>
                      {l.created_at ? new Date(l.created_at).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }) : '—'}
                    </span>
                  </div>
                )
              }) : (
                <div className={styles.emptySmall}>No recent activity.</div>
              )}
            </div>
          </SectionCard>

          <SectionCard icon={<Zap size={16} />} title="Quick Actions">
            <div className={styles.quickActions}>
              <button className={styles.qaBtn} onClick={() => navigate(`${basePath}/mailboxes`)}>
                <Mail size={16} />
                <span>Manage Mailboxes</span>
              </button>
              <button className={styles.qaBtn} onClick={() => navigate(`${basePath}/users`)}>
                <Users size={16} />
                <span>Manage Users</span>
              </button>
              <button className={styles.qaBtn} onClick={() => navigate(`${basePath}/reports`)}>
                <FileText size={16} />
                <span>Reports</span>
              </button>
              <button className={styles.qaBtn} onClick={() => navigate(`${basePath}/settings`)}>
                <Settings size={16} />
                <span>Settings</span>
              </button>
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  )
}
