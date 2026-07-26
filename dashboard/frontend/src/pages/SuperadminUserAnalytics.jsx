import { useEffect, useMemo, useState } from 'react'
import api from '../api/client'
import { useTranslation } from '../i18n/context'
import {
  AlertCircle, CheckCircle, ChevronDown, ChevronUp,
  Download, Mail, RefreshCw, Search, ShieldAlert, X,
} from 'lucide-react'
import styles from './AdminPage.module.css'
import { displayEmailCategory } from '../utils/emailCategory'

const scoreColor = (score) => score >= 70 ? '#DC2626' : score >= 40 ? '#D97706' : '#16A34A'
const scoreBackground = (score) => score >= 70 ? '#FEF2F2' : score >= 40 ? '#FFFBEB' : '#F0FDF4'

function ScoreBadge({ score }) {
  return (
    <span style={{
      display: 'inline-flex', minWidth: 38, justifyContent: 'center', padding: '3px 9px',
      borderRadius: 999, fontSize: '0.75rem', fontWeight: 700,
      background: scoreBackground(score), color: scoreColor(score),
    }}>
      {score}
    </span>
  )
}

function MiniBar({ value, max }) {
  const percent = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 62, height: 6, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${percent}%`, height: '100%', background: '#2563EB', borderRadius: 4 }} />
      </div>
      <span style={{ fontSize: '0.78rem', minWidth: 24 }}>{value}</span>
    </div>
  )
}

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString()
}

function MailboxDetailModal({ mailbox, onClose }) {
  const { t } = useTranslation()
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    api.get(`/admin/email-analytics/${mailbox.mailbox_id}`)
      .then(({ data }) => setDetail(data))
      .catch((err) => setError(err.response?.data?.detail || t('analytics.detail.loadError')))
      .finally(() => setLoading(false))
  }, [mailbox.mailbox_id, t])

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.editModal} style={{ maxWidth: 920, width: '94%', maxHeight: '88vh', overflowY: 'auto' }} onClick={(event) => event.stopPropagation()}>
        <div className={styles.editModalHeader}>
          <h3><Mail size={17} /> {t('analytics.detail.title')} — {mailbox.email}</h3>
          <button className={styles.modalCloseBtn} onClick={onClose} aria-label={t('common.close')}><X size={17} /></button>
        </div>
        <div className={styles.editModalBody}>
          {loading && <div className={styles.emptySmall}>{t('analytics.detail.loading')}</div>}
          {error && <div style={{ padding: '10px 12px', borderRadius: 7, background: '#FEF2F2', color: '#B91C1C', display: 'flex', gap: 8 }}><AlertCircle size={15} />{error}</div>}
          {detail && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 10, marginBottom: 20 }}>
                {[
                  [t('analytics.table.admin'), detail.mailbox.admin],
                  [t('analytics.table.totalEmail'), detail.mailbox.total_emails],
                  [t('analytics.summary.totalThreats'), detail.mailbox.total_threats],
                  [t('analytics.table.averageScore'), Number(detail.mailbox.average_fused_score).toFixed(4)],
                ].map(([label, value]) => (
                  <div key={label} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '11px 13px', background: 'var(--surface-alt, #f8fafc)' }}>
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: 5 }}>{label}</div>
                    <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{value || '—'}</div>
                  </div>
                ))}
              </div>

              {detail.top_senders?.length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <h4 style={{ margin: '0 0 8px', fontSize: '0.85rem' }}>{t('analytics.detail.topSenders')}</h4>
                  <table className={styles.table}>
                    <thead><tr><th>{t('common.sender')}</th><th>{t('analytics.summary.totalThreats')}</th><th>Phishing</th><th>Spam</th><th>{t('gmail.warn')}</th></tr></thead>
                    <tbody>{detail.top_senders.map((sender) => (
                      <tr key={sender.sender}><td>{sender.sender}</td><td>{sender.count}</td><td>{sender.phishing}</td><td>{sender.spam}</td><td>{sender.warn}</td></tr>
                    ))}</tbody>
                  </table>
                </div>
              )}

              <h4 style={{ margin: '0 0 8px', fontSize: '0.85rem' }}>{t('analytics.detail.recentThreats')}</h4>
              {detail.recent_threats?.length > 0 ? (
                <div style={{ overflowX: 'auto' }}>
                  <table className={styles.table}>
                    <thead><tr><th>{t('common.subject')}</th><th>{t('common.sender')}</th><th>{t('common.category')}</th><th>Fused / ML / SA</th><th>SPF / DKIM / DMARC</th><th>{t('analytics.table.lastThreat')}</th></tr></thead>
                    <tbody>{detail.recent_threats.map((email) => (
                      <tr key={email.email_id}>
                        <td>{email.subject || t('common.noSubject')}</td><td>{email.sender || '—'}</td>
                        <td>{displayEmailCategory(email.category, email.label)}</td>
                        <td>{email.fused_score.toFixed(3)} / {email.ml_probability.toFixed(3)} / {email.sa_score.toFixed(2)}</td>
                        <td>{email.spf || 'N/A'} / {email.dkim || 'N/A'} / {email.dmarc || 'N/A'}</td>
                        <td>{formatDate(email.received_at)}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              ) : <div className={styles.emptySmall}><CheckCircle size={16} /> {t('analytics.detail.noThreats')}</div>}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function SuperadminUserAnalytics({ onExport }) {
  const { t } = useTranslation()
  const [mailboxes, setMailboxes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState('total_emails')
  const [sortDir, setSortDir] = useState('desc')
  const [selected, setSelected] = useState(null)

  const fetchAnalytics = () => {
    setLoading(true); setError('')
    api.get('/admin/email-analytics')
      .then(({ data }) => setMailboxes(Array.isArray(data) ? data : []))
      .catch((err) => setError(err.response?.data?.detail || t('analytics.loadError')))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchAnalytics() }, [])

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    return mailboxes.filter((row) => !query || [row.email, row.sender_name, row.admin].some((value) => (value || '').toLowerCase().includes(query)))
      .sort((a, b) => {
        const left = a[sortKey] ?? 0; const right = b[sortKey] ?? 0
        if (typeof left === 'string') return sortDir === 'asc' ? left.localeCompare(right) : right.localeCompare(left)
        return sortDir === 'asc' ? left - right : right - left
      })
  }, [mailboxes, search, sortKey, sortDir])

  const handleSort = (key) => {
    if (sortKey === key) setSortDir((value) => value === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }
  const SortIcon = ({ column }) => sortKey !== column
    ? <ChevronDown size={11} style={{ opacity: 0.3 }} />
    : sortDir === 'asc' ? <ChevronUp size={11} /> : <ChevronDown size={11} />

  const totalEmails = mailboxes.reduce((sum, row) => sum + row.total_emails, 0)
  const totalThreats = mailboxes.reduce((sum, row) => sum + row.total_threats, 0)
  const active = mailboxes.filter((row) => row.is_active).length
  const maxTotal = Math.max(...mailboxes.map((row) => row.total_emails), 1)

  return (
    <div style={{ padding: '0 0 24px' }}>
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <div className={styles.sectionTitle}><Mail size={17} /><div><strong>{t('analytics.title')}</strong><span>{t('analytics.subtitle')}</span></div></div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={fetchAnalytics} disabled={loading} className={styles.actionBtn} title={t('common.refresh')}><RefreshCw size={14} /></button>
            <button onClick={onExport} className={styles.addBtn}><Download size={14} /> {t('analytics.downloadReport')}</button>
          </div>
        </div>

        {error && <div style={{ padding: '10px 16px', background: '#FEF2F2', color: '#B91C1C', display: 'flex', gap: 8 }}><AlertCircle size={15} />{error}</div>}

        {!loading && (
          <div className={styles.statsGrid6} style={{ padding: '16px 20px 0' }}>
            {[
              [t('analytics.summary.totalMailboxes'), mailboxes.length, <Mail size={16} />, '#EFF6FF', '#2563EB'],
              [t('analytics.summary.totalEmails'), totalEmails, <CheckCircle size={16} />, '#F0FDF4', '#16A34A'],
              [t('analytics.summary.totalThreats'), totalThreats, <ShieldAlert size={16} />, '#FEF2F2', '#DC2626'],
              [t('analytics.summary.activeMailboxes'), active, <CheckCircle size={16} />, '#F0FDF4', '#16A34A'],
            ].map(([label, value, icon, background, color]) => (
              <div key={label} className={styles.statCard2}><div className={styles.sc2Icon} style={{ background, color }}>{icon}</div><div className={styles.sc2Body}><span className={styles.sc2Value}>{value}</span><span className={styles.sc2Label}>{label}</span></div></div>
            ))}
          </div>
        )}

        <div className={styles.filterBar}>
          <div className={styles.searchForm}><Search size={14} className={styles.searchIcon} /><input className={styles.searchInput} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('analytics.searchPlaceholder')} />{search && <button type="button" onClick={() => setSearch('')} className={styles.clearBtn}><X size={12} /></button>}</div>
        </div>

        {loading ? <div className={styles.emptyState}>{t('analytics.loading')}</div> : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table className={styles.table}>
                <thead><tr>
                  {[
                    ['email', t('analytics.table.email')], ['admin', t('analytics.table.admin')],
                    ['total_emails', t('analytics.table.totalEmail')], ['phishing', 'Phishing'], ['spam', 'Spam'],
                    ['warn', t('gmail.warn')], ['quarantined', t('analytics.table.quarantined')],
                    ['threat_score', t('analytics.table.score')], ['last_threat', t('analytics.table.lastThreat')],
                  ].map(([key, label]) => <th key={key} onClick={() => handleSort(key)} style={{ cursor: 'pointer' }}><span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>{label}<SortIcon column={key} /></span></th>)}
                </tr></thead>
                <tbody>{filtered.length === 0 ? <tr><td colSpan={9} style={{ textAlign: 'center', padding: 30, color: 'var(--text-muted)' }}>{search ? t('analytics.noMatch') : t('analytics.noData')}</td></tr> : filtered.map((row) => (
                  <tr key={row.mailbox_id} onClick={() => setSelected(row)} style={{ cursor: 'pointer' }}>
                    <td><div className={styles.usernameCell}>{row.email}</div></td>
                    <td><strong>{row.admin}</strong></td>
                    <td><MiniBar value={row.total_emails} max={maxTotal} /></td>
                    <td>{row.phishing}</td><td>{row.spam}</td><td>{row.warn}</td><td>{row.quarantined}</td>
                    <td><ScoreBadge score={row.threat_score} /></td><td>{formatDate(row.last_threat)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <div style={{ padding: '9px 16px', fontSize: '0.75rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border)' }}>{t('analytics.table.showing').replace('{count}', filtered.length).replace('{total}', mailboxes.length)}</div>
          </>
        )}
      </div>
      {selected && <MailboxDetailModal mailbox={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
