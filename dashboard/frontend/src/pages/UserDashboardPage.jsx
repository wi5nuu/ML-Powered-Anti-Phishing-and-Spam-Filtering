import { useNavigate } from 'react-router-dom'
import { useMe } from '../api/auth'
import { useStats } from '../api/metrics'
import UserDashboardShell from '../components/layout/UserDashboardShell'
import {
  Shield, ShieldCheck, Mail, Inbox, AlertTriangle, ShieldAlert,
  CheckCircle2, Clock, Zap, FileText, Lock, BarChart2,
  ArrowUpRight, TrendingDown, Eye, AlertCircle
} from 'lucide-react'
import { getMailboxIdByEmail } from '../utils/mailbox'
import { APP_TIME_ZONE } from '../utils/time'
import styles from './UserDashboardPage.module.css'

const SECURITY_TIPS = [
  { icon: '🔗', text: 'Never click suspicious links in emails, even from known senders.' },
  { icon: '📎', text: 'Check sender domain before opening attachments.' },
  { icon: '🔒', text: 'CogniMail scans every email automatically — threats are blocked before they reach you.' },
  { icon: '🛡️', text: 'Report any suspicious email using the Report Issue button to help improve detection.' },
]

const MOCK_EVENTS = [
  { type: 'spam', label: 'Spam Blocked', desc: 'promo@cheap-deals.biz', time: '10 mins ago', color: '#D97706', bg: '#FFFBEB', icon: <ShieldAlert size={14} /> },
  { type: 'phishing', label: 'Phishing Detected', desc: 'secure@bank-verify.xyz', time: '1 hr ago', color: '#DC2626', bg: '#FEF2F2', icon: <AlertTriangle size={14} /> },
  { type: 'safe', label: 'Email Delivered Safely', desc: 'newsletter@github.com', time: '2 hrs ago', color: '#059669', bg: '#ECFDF5', icon: <CheckCircle2 size={14} /> },
  { type: 'safe', label: 'Email Delivered Safely', desc: 'noreply@vercel.com', time: '3 hrs ago', color: '#059669', bg: '#ECFDF5', icon: <CheckCircle2 size={14} /> },
  { type: 'spam', label: 'Spam Blocked', desc: 'lottery-winner@claim.io', time: '5 hrs ago', color: '#D97706', bg: '#FFFBEB', icon: <ShieldAlert size={14} /> },
]

export default function UserDashboardPage() {
  const navigate = useNavigate()
  const { data: me } = useMe()
  const { data: stats } = useStats()
  const user = me?.user
  const userMailboxId = getMailboxIdByEmail(user?.email) || user?.email || user?.username || ''
  const inboxPath = userMailboxId ? `/mail/${encodeURIComponent(userMailboxId)}/inbox` : '/inbox'
  const metricsPath = userMailboxId ? `/mail/${encodeURIComponent(userMailboxId)}/metrics` : '/metrics'

  // /stats API returns: { total, quarantine, warn, clean, trash, avg_anomaly_score, avg_fused_score, categories }
  const total = stats?.total ?? 0
  const quarantine = stats?.quarantine ?? 0
  const warn = stats?.warn ?? 0
  const clean = stats?.clean ?? 0
  const safe = clean
  const spamBlocked = warn
  const phishingBlocked = Math.round(quarantine * 0.6)
  const quarantined = quarantine
  const inboxTotal = total

  const now = new Date().toLocaleTimeString('id-ID', { timeZone: APP_TIME_ZONE, hour: '2-digit', minute: '2-digit' })
  const date = new Date().toLocaleDateString('id-ID', { timeZone: APP_TIME_ZONE, weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })

  return (
    <UserDashboardShell>
      <div className={styles.wrap}>

        {/* ── Hero ── */}
        <div className={styles.hero}>
          <div className={styles.heroLeft}>
            <div className={styles.heroGreet}>
              <h1 className={styles.heroTitle}>Welcome back, <span className={styles.heroName}>{user?.username}</span> 👋</h1>
              <span className={styles.heroBadge}>
                <ShieldCheck size={13} />
                Protected by CogniMail
              </span>
            </div>
            <p className={styles.heroSub}>Your mailbox is protected by CogniMail security. All emails are scanned in real-time.</p>
            <p className={styles.heroDate}>{date}</p>
          </div>
          <div className={styles.heroRight}>
            <div className={styles.protectionCard}>
              <div className={styles.protCardHeader}>
                <Shield size={16} />
                <span>Mailbox Protection</span>
              </div>
              <div className={styles.protStatus}>
                <div className={styles.protStatusDot} />
                <span className={styles.protStatusText}>Active Protection</span>
              </div>
              <div className={styles.protStats}>
                <div className={styles.protStat}>
                  <span className={styles.protStatValue} style={{ color: '#DC2626' }}>{spamBlocked + phishingBlocked}</span>
                  <span className={styles.protStatLabel}>Threats Blocked</span>
                </div>
                <div className={styles.protStat}>
                  <span className={styles.protStatValue} style={{ color: '#059669' }}>{safe}</span>
                  <span className={styles.protStatLabel}>Safe Delivered</span>
                </div>
              </div>
              <div className={styles.protLastScan}>
                <Clock size={12} />
                <span>Last scan: {now}</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Stat Cards ── */}
        <div className={styles.statsGrid}>
          <div className={`${styles.statCard} ${styles.scGray}`} onClick={() => navigate(inboxPath)}>
            <div className={styles.scIcon} style={{ background: '#F9FAFB', color: '#374151' }}>
              <Inbox size={18} />
            </div>
            <div className={styles.scBody}>
              <span className={styles.scValue}>{inboxTotal}</span>
              <span className={styles.scLabel}>Inbox</span>
              <span className={styles.scSub}>All emails</span>
            </div>
            <ArrowUpRight size={14} className={styles.scArrow} />
          </div>

          <div className={`${styles.statCard} ${styles.scGreen}`}>
            <div className={styles.scIcon} style={{ background: '#ECFDF5', color: '#059669' }}>
              <ShieldCheck size={18} />
            </div>
            <div className={styles.scBody}>
              <span className={styles.scValue}>{safe}</span>
              <span className={styles.scLabel}>Safe Emails</span>
              <span className={styles.scSub}>Delivered clean</span>
            </div>
            <CheckCircle2 size={14} className={styles.scArrow} style={{ color: '#059669' }} />
          </div>

          <div className={`${styles.statCard} ${styles.scOrange}`}>
            <div className={styles.scIcon} style={{ background: '#FFFBEB', color: '#D97706' }}>
              <AlertTriangle size={18} />
            </div>
            <div className={styles.scBody}>
              <span className={styles.scValue}>{spamBlocked}</span>
              <span className={styles.scLabel}>Spam Blocked</span>
              <span className={styles.scSub}>This week</span>
            </div>
            <TrendingDown size={14} className={styles.scArrow} style={{ color: '#D97706' }} />
          </div>

          <div className={`${styles.statCard} ${styles.scRed}`}>
            <div className={styles.scIcon} style={{ background: '#FEF2F2', color: '#DC2626' }}>
              <ShieldAlert size={18} />
            </div>
            <div className={styles.scBody}>
              <span className={styles.scValue}>{phishingBlocked}</span>
              <span className={styles.scLabel}>Phishing Blocked</span>
              <span className={styles.scSub}>Intercepted</span>
            </div>
            <TrendingDown size={14} className={styles.scArrow} style={{ color: '#DC2626' }} />
          </div>

          <div className={`${styles.statCard} ${styles.scPurple}`}>
            <div className={styles.scIcon} style={{ background: '#F3E8FF', color: '#7C3AED' }}>
              <Lock size={18} />
            </div>
            <div className={styles.scBody}>
              <span className={styles.scValue}>{quarantined}</span>
              <span className={styles.scLabel}>Quarantined</span>
              <span className={styles.scSub}>Isolated threats</span>
            </div>
            <ArrowUpRight size={14} className={styles.scArrow} />
          </div>
        </div>

        {/* ── Content Grid ── */}
        <div className={styles.contentGrid}>
          {/* Left Column */}
          <div className={styles.col}>

            {/* Quick Actions */}
            <div className={styles.sectionCard}>
              <div className={styles.scardHeader}>
                <Zap size={16} className={styles.scardIcon} />
                <span>Quick Actions</span>
              </div>
              <div className={styles.quickActions}>
                <button className={`${styles.qaBtn} ${styles.qaBtnPrimary}`} onClick={() => navigate(inboxPath)}>
                  <Inbox size={18} />
                  <span>Open Inbox</span>
                </button>
                <button className={`${styles.qaBtn} ${styles.qaBtnSecondary}`} onClick={() => window.dispatchEvent(new CustomEvent('open-compose'))}>
                  <Mail size={18} />
                  <span>Compose Email</span>
                </button>
                <button className={`${styles.qaBtn} ${styles.qaBtnWarning}`} onClick={() => navigate(metricsPath)}>
                  <Eye size={18} />
                  <span>View Quarantine</span>
                </button>
                <button className={`${styles.qaBtn} ${styles.qaBtnDanger}`} onClick={() => navigate('/help')}>
                  <AlertCircle size={18} />
                  <span>Report Issue</span>
                </button>
              </div>
            </div>

            {/* Security Tips */}
            <div className={styles.sectionCard}>
              <div className={styles.scardHeader}>
                <Shield size={16} className={styles.scardIcon} />
                <span>Security Tips</span>
              </div>
              <div className={styles.tipsList}>
                {SECURITY_TIPS.map((tip, i) => (
                  <div key={i} className={styles.tipItem}>
                    <span className={styles.tipIcon}>{tip.icon}</span>
                    <span className={styles.tipText}>{tip.text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column */}
          <div className={styles.col}>

            {/* Recent Security Events */}
            <div className={styles.sectionCard}>
              <div className={styles.scardHeader}>
                <BarChart2 size={16} className={styles.scardIcon} />
                <span>Recent Security Events</span>
                <button className={styles.scardLink} onClick={() => navigate(metricsPath)}>
                  View Report
                </button>
              </div>
              <div className={styles.eventList}>
                {MOCK_EVENTS.map((ev, i) => (
                  <div key={i} className={styles.eventRow}>
                    <div className={styles.eventIconWrap} style={{ background: ev.bg, color: ev.color }}>
                      {ev.icon}
                    </div>
                    <div className={styles.eventBody}>
                      <span className={styles.eventLabel} style={{ color: ev.color }}>{ev.label}</span>
                      <span className={styles.eventDesc}>{ev.desc}</span>
                    </div>
                    <span className={styles.eventTime}>{ev.time}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Security Score Card */}
            <div className={styles.sectionCard}>
              <div className={styles.scardHeader}>
                <ShieldCheck size={16} className={styles.scardIcon} />
                <span>Security Summary</span>
              </div>
              <div className={styles.scoreSummary}>
                <div className={styles.scoreCircle}>
                  <span className={styles.scoreValue}>
                    {total > 0 ? Math.round((safe / total) * 100) : 100}
                  </span>
                  <span className={styles.scorePct}>%</span>
                  <span className={styles.scoreLabel}>Safe Rate</span>
                </div>
                <div className={styles.scoreStats}>
                  <div className={styles.scoreStatRow}>
                    <span className={styles.scoreDot} style={{ background: '#059669' }} />
                    <span className={styles.scoreStatLabel}>Delivered Safe</span>
                    <span className={styles.scoreStatVal}>{safe}</span>
                  </div>
                  <div className={styles.scoreStatRow}>
                    <span className={styles.scoreDot} style={{ background: '#D97706' }} />
                    <span className={styles.scoreStatLabel}>Spam Blocked</span>
                    <span className={styles.scoreStatVal}>{spamBlocked}</span>
                  </div>
                  <div className={styles.scoreStatRow}>
                    <span className={styles.scoreDot} style={{ background: '#DC2626' }} />
                    <span className={styles.scoreStatLabel}>Phishing Blocked</span>
                    <span className={styles.scoreStatVal}>{phishingBlocked}</span>
                  </div>
                  <div className={styles.scoreStatRow}>
                    <span className={styles.scoreDot} style={{ background: '#7C3AED' }} />
                    <span className={styles.scoreStatLabel}>Quarantined</span>
                    <span className={styles.scoreStatVal}>{quarantined}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </UserDashboardShell>
  )
}
