import { useNavigate } from 'react-router-dom'
import { useTranslation } from '../i18n/context'
import { useMe } from '../api/auth'
import { useStats } from '../api/metrics'
import {
  ShieldCheck, Inbox, AlertTriangle,
  Mail, ArrowRight, CheckCircle, Info
} from 'lucide-react'
import styles from './UserDashboardPage.module.css'

export default function UserDashboardPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { data: auth } = useMe()
  const { data: stats } = useStats()

  const user = auth?.user
  const now = new Date()
  const greeting =
    now.getHours() < 12 ? t('greeting.morning') :
    now.getHours() < 17 ? t('greeting.afternoon') : t('greeting.evening')

  const total = stats?.total ?? 0
  const clean = stats?.clean ?? 0
  const warned = stats?.warned ?? 0
  const quarantined = stats?.quarantined ?? 0
  const safeRate = total > 0 ? Math.round((clean / total) * 100) : 100

  return (
    <div className={styles.wrap}>
      {/* Hero */}
      <div className={styles.hero}>
        <div className={styles.heroLeft}>
          <div className={styles.heroGreet}>{greeting},</div>
          <div className={styles.heroName}>{user?.username || 'User'}</div>
          <div className={styles.heroTitle}>{t('userDashboard.securityDashboard')}</div>
          <div className={styles.heroSub}>{t('userDashboard.protectionActive')}</div>
        </div>
        <div className={styles.heroRight}>
          <div className={styles.heroDate}>
            {now.toLocaleDateString('id-ID', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
          </div>
          <div className={styles.heroBadge}>
            <ShieldCheck size={13} />
            {t('userDashboard.activeProtection')}
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className={styles.statsGrid}>
        <div className={styles.statCard}>
          <span style={{ fontSize: 11, color: '#5f6368' }}>{t('overview.totalEmail')}</span>
          <span style={{ fontSize: 24, fontWeight: 700, color: '#202124' }}>{total}</span>
        </div>
        <div className={styles.statCard}>
          <span style={{ fontSize: 11, color: '#5f6368' }}>{t('overview.clean')}</span>
          <span style={{ fontSize: 24, fontWeight: 700, color: '#34a853' }}>{clean}</span>
        </div>
        <div className={styles.statCard}>
          <span style={{ fontSize: 11, color: '#5f6368' }}>{t('userDashboard.needsAttention')}</span>
          <span style={{ fontSize: 24, fontWeight: 700, color: '#fbbc04' }}>{warned}</span>
        </div>
        <div className={styles.statCard}>
          <span style={{ fontSize: 11, color: '#5f6368' }}>{t('overview.quarantine')}</span>
          <span style={{ fontSize: 24, fontWeight: 700, color: '#ea4335' }}>{quarantined}</span>
        </div>
      </div>

      {/* Content Grid */}
      <div className={styles.contentGrid}>
        <div className={styles.col}>
          {/* Protection Score */}
          <div className={styles.sectionCard}>
            <div className={styles.scardHeader}>
              <span className={styles.scardIcon}><ShieldCheck size={15} /> {t('userDashboard.protectionScore')}</span>
            </div>
            <div className={styles.scoreSummary}>
              <div className={styles.scoreCircle}>
                <span className={styles.scoreValue}>{safeRate}</span>
                <span className={styles.scoreLabel}>%</span>
              </div>
              <div className={styles.scoreStats}>
                <div className={styles.scoreStatRow}>
                  <span className={styles.scoreStatLabel}>{t('userDashboard.safeEmails')}</span>
                  <span className={styles.scoreStatVal}>{clean}</span>
                </div>
                <div className={styles.scoreStatRow}>
                  <span className={styles.scoreStatLabel}>{t('userDashboard.threatsDetected')}</span>
                  <span className={styles.scoreStatVal}>{quarantined}</span>
                </div>
                <div className={styles.scoreStatRow}>
                  <span className={styles.scoreStatLabel}>{t('userDashboard.needsReview')}</span>
                  <span className={styles.scoreStatVal}>{warned}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className={styles.sectionCard}>
            <div className={styles.scardHeader}>
              <span className={styles.scardIcon}><Mail size={15} /> {t('overview.quickActions')}</span>
            </div>
            <div className={styles.quickActions}>
              <button
                className={`${styles.qaBtn} ${styles.qaBtnPrimary}`}
                onClick={() => navigate('/inbox')}
              >
                <Inbox size={15} />
                {t('userDashboard.openInbox')}
                <ArrowRight size={14} style={{ marginLeft: 'auto' }} />
              </button>
              <button
                className={`${styles.qaBtn} ${styles.qaBtnSecondary}`}
                onClick={() => navigate('/user/mailboxes')}
              >
                <Mail size={15} />
                {t('userDashboard.manageAccounts')}
                <ArrowRight size={14} style={{ marginLeft: 'auto' }} />
              </button>
              {quarantined > 0 && (
                <button
                  className={`${styles.qaBtn} ${styles.qaBtnDanger}`}
                  onClick={() => navigate('/inbox?folder=quarantine')}
                >
                  <AlertTriangle size={15} />
                  {t('userDashboard.reviewQuarantine')} ({quarantined})
                  <ArrowRight size={14} style={{ marginLeft: 'auto' }} />
                </button>
              )}
            </div>
          </div>
        </div>

        <div className={styles.col}>
          {/* Tips */}
          <div className={styles.sectionCard}>
            <div className={styles.scardHeader}>
              <span className={styles.scardIcon}><Info size={15} /> {t('userDashboard.securityTips')}</span>
            </div>
            <div className={styles.tipsList}>
              {[
                t('userDashboard.tip1'),
                t('userDashboard.tip2'),
                t('userDashboard.tip3'),
                t('userDashboard.tip4'),
              ].map((tip, i) => (
                <div key={i} className={styles.tipItem}>
                  <CheckCircle size={14} color="#34a853" className={styles.tipIcon} />
                  <span className={styles.tipText}>{tip}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Protection Status */}
          <div className={styles.protectionCard}>
            <div className={styles.protCardHeader}>
              <span className={styles.scardIcon}><ShieldCheck size={15} /> {t('overview.systemHealth')}</span>
            </div>
            <div className={styles.protStatus}>
              <div className={styles.protStatusDot} />
              <span className={styles.protStatusText}>{t('userDashboard.systemActive')}</span>
            </div>
            <div className={styles.protStats}>
              <div className={styles.protStat}>
                <div className={styles.protStatValue}>{safeRate}%</div>
                <div className={styles.protStatLabel}>{t('userDashboard.safetyLevel')}</div>
              </div>
              <div className={styles.protStat}>
                <div className={styles.protStatValue}>{total}</div>
                <div className={styles.protStatLabel}>{t('userDashboard.processed')}</div>
              </div>
              <div className={styles.protStat}>
                <div className={styles.protStatValue}>{quarantined}</div>
                <div className={styles.protStatLabel}>{t('userDashboard.blocked')}</div>
              </div>
            </div>
            <div className={styles.protLastScan}>
              {t('userDashboard.techStack')}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
