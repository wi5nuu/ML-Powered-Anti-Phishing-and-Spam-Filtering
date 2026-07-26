import { useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Shield, Activity, Mail, MessageSquare } from 'lucide-react'
import GmailShell from '../components/layout/GmailShell'
import { useMetrics } from '../api/metrics'
import { getActiveMailbox, getActiveMailboxId, withMailbox } from '../utils/mailbox'
import { useTranslation } from '../i18n/context'
import styles from './MetricsPage.module.css'

export default function MetricsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const activeMailbox = getActiveMailbox(searchParams)
  const activeMailboxId = getActiveMailboxId(searchParams)
  const inboxPath = withMailbox('/inbox', activeMailbox, activeMailboxId)
  const { t } = useTranslation()
  const { data: metrics, isLoading, isError } = useMetrics({
    mailbox: activeMailbox,
    mailboxId: activeMailboxId,
  })

  if (isLoading) {
    return (
      <GmailShell>
        <div style={{ padding: 32, color: 'var(--text-muted)', fontFamily: 'Google Sans, Roboto, sans-serif' }}>
          {t('metrics.loading')}
        </div>
      </GmailShell>
    )
  }

  if (isError || !metrics) {
    return (
      <GmailShell>
        <div style={{ padding: 32, color: '#EA4335', fontFamily: 'Google Sans, Roboto, sans-serif' }}>
          {t('metrics.error')}
        </div>
      </GmailShell>
    )
  }

  const {
    total = 0,
    quarantine_count = 0,
    warn_count = 0,
    clean_count = 0,
    feedback_count = 0,
    top_senders = [],
    daily_stats = []
  } = metrics

  const maxTotal = Math.max(total, 1)
  const quarantinePct = ((quarantine_count / maxTotal) * 100).toFixed(1)
  const warnPct = ((warn_count / maxTotal) * 100).toFixed(1)
  const cleanPct = ((clean_count / maxTotal) * 100).toFixed(1)
  const detectionRate = (((quarantine_count + warn_count) / maxTotal) * 100).toFixed(1)

  const maxDaily = daily_stats.length
    ? Math.max(...daily_stats.map(d => d.total || 1))
    : 1

  return (
    <GmailShell>
      <div className={styles.wrap}>
        {/* Header */}
        <div className={styles.header}>
          <button className={styles.backBtn} onClick={() => navigate(inboxPath)}>
            <ArrowLeft size={20} />
            {t('metrics.backToInbox')}
          </button>
          <div className={styles.titleRow}>
            <h1 className={styles.title}>{activeMailbox ? `${t('metrics.title')} ${activeMailbox}` : t('metrics.title')}</h1>
            <span className={styles.liveBadge}>{t('metrics.liveBadge')}</span>
          </div>
        </div>

        {/* Metric Cards */}
        <div className={styles.grid}>
          <div className={`${styles.card} ${styles.cardTotal}`}>
            <div className={styles.cardHeader}>
              <Mail className={styles.cardIcon} size={20} />
              <h3>{t('metrics.totalEmails')}</h3>
            </div>
            <div className={styles.value}>{total}</div>
            <div className={styles.subtext}>{t('metrics.totalSubtext')}</div>
          </div>
          <div className={`${styles.card} ${styles.cardQuarantine}`}>
            <div className={styles.cardHeader}>
              <Shield className={styles.cardIcon} size={20} />
              <h3>{t('overview.quarantined')}</h3>
            </div>
            <div className={styles.value}>{quarantine_count}</div>
            <div className={styles.subtext}>{quarantinePct}{t('metrics.ofTotal')}</div>
          </div>
          <div className={`${styles.card} ${styles.cardWarn}`}>
            <div className={styles.cardHeader}>
              <Activity className={styles.cardIcon} size={20} />
              <h3>{t('overview.warn')}</h3>
            </div>
            <div className={styles.value}>{warn_count}</div>
            <div className={styles.subtext}>{warnPct}{t('metrics.ofTotal')}</div>
          </div>
          <div className={`${styles.card} ${styles.cardClean}`}>
            <div className={styles.cardHeader}>
              <Shield className={styles.cardIcon} size={20} />
              <h3>{t('overview.cleanLabel')}</h3>
            </div>
            <div className={styles.value}>{clean_count}</div>
            <div className={styles.subtext}>{cleanPct}{t('metrics.ofTotal')}</div>
          </div>
          <div className={`${styles.card} ${styles.cardFeedback}`}>
            <div className={styles.cardHeader}>
              <MessageSquare className={styles.cardIcon} size={20} />
              <h3>{t('metrics.falsePositive')}</h3>
            </div>
            <div className={styles.value}>{feedback_count}</div>
            <div className={styles.subtext}>{t('metrics.falsePositiveSubtext')}</div>
          </div>
        </div>

        {/* Distribution Bar */}
        <div className={styles.sectionCard}>
          <h3 className={styles.sectionTitle}>{t('metrics.distributionTitle')}</h3>
          <div className={styles.barContainer}>
            {clean_count > 0 && (
              <div className={`${styles.bar} ${styles.barClean}`} style={{ width: `${(clean_count / maxTotal) * 100}%` }}>
                {Math.round((clean_count / maxTotal) * 100)}% {t('overview.cleanLabel')}
              </div>
            )}
            {warn_count > 0 && (
              <div className={`${styles.bar} ${styles.barWarn}`} style={{ width: `${(warn_count / maxTotal) * 100}%` }}>
                {Math.round((warn_count / maxTotal) * 100)}% {t('overview.warn')}
              </div>
            )}
            {quarantine_count > 0 && (
              <div className={`${styles.bar} ${styles.barQuarantine}`} style={{ width: `${(quarantine_count / maxTotal) * 100}%` }}>
                {Math.round((quarantine_count / maxTotal) * 100)}% {t('overview.quarantine')}
              </div>
            )}
          </div>
          <div className={styles.legend}>
            <span><span className={styles.dotClean}>■</span> {t('overview.cleanLabel')}: {clean_count}</span>
            <span><span className={styles.dotWarn}>■</span> {t('overview.warn')}: {warn_count}</span>
            <span><span className={styles.dotQuarantine}>■</span> {t('overview.quarantine')}: {quarantine_count}</span>
          </div>
        </div>

        {/* Daily Trend Chart */}
        {daily_stats && daily_stats.length > 0 && (
          <div className={styles.sectionCard}>
            <h3 className={styles.sectionTitle}>{t('metrics.dailyTrend')}</h3>
            <div className={styles.chart}>
              {daily_stats.map((dayData, i) => {
                const qHeight = Math.round(((dayData.quarantines || 0) / maxDaily) * 120)
                const cHeight = Math.round((Math.abs((dayData.total || 0) - (dayData.quarantines || 0)) / maxDaily) * 120)
                const label = dayData.day ? dayData.day.slice(5) : ''
                return (
                  <div key={i} className={styles.chartCol} title={`${dayData.day}: ${dayData.total} ${t('metrics.totalLower')}, ${dayData.quarantines || 0} ${t('metrics.quarantineLower')}`}>
                    <div className={styles.chartBars}>
                      <div className={`${styles.chartFill} ${styles.chartQuarantine}`} style={{ height: `${qHeight}px` }} />
                      <div className={`${styles.chartFill} ${styles.chartClean}`} style={{ height: `${cHeight}px` }} />
                    </div>
                    <span className={styles.chartLabel}>{label}</span>
                  </div>
                )
              })}
            </div>
            <div className={styles.chartLegend}>
              <span><span className={styles.dotQuarantine}>■</span> {t('overview.quarantine')}</span>
              <span><span className={styles.dotClean}>■</span> {t('metrics.chartClean')}</span>
            </div>
          </div>
        )}

        {/* Top Senders & Summary Row */}
        <div className={styles.rowLayout}>
          <div className={styles.sectionCard} style={{ flex: 1 }}>
            <h3 className={styles.sectionTitle}>{t('metrics.topSenders')}</h3>
            <div className={styles.sendersList}>
              {top_senders.map((sender, idx) => (
                <div key={idx} className={styles.senderRow}>
                  <div className={styles.senderAvatar}>
                    {(sender.sender || 'U')[0].toUpperCase()}
                  </div>
                  <span className={styles.senderName} title={sender.sender || t('metrics.unknownSender')}>
                    {sender.sender || t('metrics.unknownSender')}
                  </span>
                  <span className={styles.senderBadge}>
                    {sender.count} {t('metrics.emailUnit')}
                  </span>
                </div>
              ))}
              {top_senders.length === 0 && (
                <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                  {t('metrics.noSenders')}
                </div>
              )}
            </div>
          </div>

          <div className={`${styles.sectionCard} ${styles.summaryCard}`}>
            <h3 className={styles.sectionTitle}>{t('metrics.securitySummary')}</h3>
            <div className={styles.summaryList}>
              <div className={styles.summaryRow}>
                <span>{t('metrics.detectionRate')}</span>
                <strong style={{ color: 'var(--gmail-green)' }}>{detectionRate}%</strong>
              </div>
              <div className={styles.summaryRow}>
                <span>{t('metrics.safeEmails')}</span>
                <strong style={{ color: 'var(--gmail-blue)' }}>{cleanPct}%</strong>
              </div>
              <div className={styles.summaryRow}>
                <span>{t('metrics.falseLabel')}</span>
                <strong style={{ color: 'var(--gmail-yellow)' }}>{feedback_count}</strong>
              </div>
              <div className={styles.summaryRow}>
                <span>{t('metrics.detectionMode')}</span>
                <span className={styles.dualBadge}>{t('metrics.dualML')}</span>
              </div>
            </div>
            <button className={styles.inboxBtn} onClick={() => navigate(inboxPath)}>
              {t('metrics.viewInbox')}
            </button>
          </div>
        </div>
      </div>
    </GmailShell>
  )
}
