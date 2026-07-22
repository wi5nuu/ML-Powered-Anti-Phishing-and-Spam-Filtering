import { useEffect, useState, useRef } from 'react'
import { useTranslation } from '../i18n/context'
import api from '../api/client'
import {
  BarChart3, RefreshCw, AlertCircle, ShieldAlert,
  Mail, Users, TrendingUp, AlertTriangle, CheckCircle, ShieldCheck,
  Calendar,
} from 'lucide-react'
import styles from './ThreatReportPage.module.css'

const THREAT_COLORS = {
  phishing:   { bg: '#fce8e6', text: '#c5221f', bar: '#ea4335' },
  spam:       { bg: '#fef3cd', text: '#856404', bar: '#f29900' },
  malware:    { bg: '#f3e5f5', text: '#6a1b9a', bar: '#9c27b0' },
  clean:      { bg: '#e8f5e9', text: '#137333', bar: '#34a853' },
  warn:       { bg: '#fef9e7', text: '#856404', bar: '#fbbc04' },
  quarantine: { bg: '#fce8e6', text: '#c5221f', bar: '#ea4335' },
}

function Bar({ value, max, color }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className={styles.barWrap}>
      <div className={styles.barTrack}>
        <div className={styles.barFill} style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className={styles.barValue}>{value}</span>
    </div>
  )
}

const TODAY = new Date().toISOString().slice(0, 10)

const getRangeOptions = (t) => [
  { label: t('report.today', 'Hari Ini'), days: 1 },
  { label: t('report.last7Days', '7 Hari'),  days: 7 },
  { label: t('report.last14Days', '14 Hari'), days: 14 },
  { label: t('report.last30Days', '30 Hari'), days: 30 },
  { label: t('report.last90Days', '90 Hari'), days: 90 },
  { label: t('report.custom', 'Custom'),  days: null },
]

export default function ThreatReportPage() {
  const { t } = useTranslation()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)
  const [activeDays, setActiveDays] = useState(14)
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState(TODAY)
  const [showCustom, setShowCustom] = useState(false)
  const reportRef = useRef(null)
  const RANGE_OPTIONS = getRangeOptions(t)

  const fetchData = (days = activeDays, from = null, to = null) => {
    setLoading(true)
    setError('')
    const params = (from && to) ? { date_from: from, date_to: to } : { days }
    api.get('/admin/threat-breakdown', { params })
      .then(({ data }) => { setData(data); setLastUpdated(new Date()) })
      .catch((e) => setError(e.response?.data?.detail || t('report.loadError', 'Gagal memuat data ancaman.')))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchData(14) }, [])

  const handleRangeSelect = (opt) => {
    if (opt.days === null) {
      setShowCustom(true)
    } else {
      setActiveDays(opt.days)
      setShowCustom(false)
      fetchData(opt.days)
    }
  }

  const handleCustomApply = () => {
    if (!customFrom || !customTo) return
    fetchData(null, customFrom, customTo)
  }

  const rangeLabel = showCustom
    ? `${customFrom || '…'} → ${customTo || '…'}`
    : (RANGE_OPTIONS.find(o => o.days === activeDays)?.label || `${activeDays} ${t('report.days', 'Hari')}`)

  const cc = data?.category_counts || {}
  const maxCat = Math.max(cc.phishing || 0, cc.spam || 0, cc.malware || 0, 1)
  const totalThreats = (cc.phishing || 0) + (cc.spam || 0) + (cc.malware || 0)
  const recipients = data?.top_recipients || []
  const senders = data?.top_senders || []
  const trend = data?.daily_trend || []
  const maxRecipient = Math.max(...recipients.map(r => r.total), 1)
  const maxSender = Math.max(...senders.map(s => s.total), 1)

  return (
    <div className={styles.wrap} ref={reportRef}>

      {/* ── Header ── */}
      <div className={styles.header}>
        <div>
          <h2 className={styles.title}>
            <BarChart3 size={18} /> {t('report.title', 'Laporan Ancaman Email')}
          </h2>
          {lastUpdated && (
            <div className={styles.lastUpdated}>
              {t('report.lastUpdated', 'Update')}: {lastUpdated.toLocaleString('id-ID')} &nbsp;·&nbsp; {t('report.period', 'Periode')}: <strong>{rangeLabel}</strong>
            </div>
          )}
        </div>
        <div className={styles.headerActions}>
          <button className={styles.btnRefresh} onClick={() => showCustom ? fetchData(null, customFrom, customTo) : fetchData(activeDays)} disabled={loading}>
            <RefreshCw size={14} className={loading ? styles.spin : ''} /> {t('report.refresh', 'Refresh')}
          </button>
        </div>
      </div>

      {/* ── Range filter ── */}
      <div className={styles.rangeBar}>
        <Calendar size={14} className={styles.rangeIcon} />
        {RANGE_OPTIONS.map((opt) => {
          const isActive = (!opt.days && showCustom) || (opt.days === activeDays && !showCustom)
          return (
            <button
              key={opt.label}
              className={`${styles.rangeBtn} ${isActive ? styles.rangeBtnActive : ''}`}
              onClick={() => handleRangeSelect(opt)}
            >
              {opt.label}
            </button>
          )
        })}
        {showCustom && (
          <div className={styles.customRange}>
            <input
              type="date" value={customFrom} max={customTo || TODAY}
              onChange={e => setCustomFrom(e.target.value)}
              className={styles.dateInput}
            />
            <span className={styles.customSep}>{t('report.rangeTo', 's/d')}</span>
            <input
              type="date" value={customTo} min={customFrom} max={TODAY}
              onChange={e => setCustomTo(e.target.value)}
              className={styles.dateInput}
            />
            <button className={styles.btnApply} onClick={handleCustomApply} disabled={!customFrom || !customTo}>
              {t('report.apply', 'Terapkan')}
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className={styles.errorBar}>
          <AlertCircle size={14} /> {error}
        </div>
      )}

      {loading ? (
        <div className={styles.loading}>{t('report.loading', 'Memuat data ancaman...')}</div>
      ) : !data ? null : (
        <>
          {/* ── Summary cards ── */}
          <div className={styles.summaryGrid}>
            {[
              { label: t('report.totalThreats', 'Total Ancaman'), value: totalThreats,       icon: <ShieldAlert size={16} color="#ea4335" />, cls: styles.cardRed },
              { label: t('report.phishing', 'Phishing'),      value: cc.phishing ?? 0,   icon: <AlertTriangle size={16} color="#c5221f" />, cls: styles.cardRed },
              { label: t('report.spam', 'Spam'),          value: cc.spam ?? 0,        icon: <Mail size={16} color="#856404" />, cls: styles.cardYellow },
              { label: t('report.malware', 'Malware'),       value: cc.malware ?? 0,     icon: <ShieldCheck size={16} color="#6a1b9a" />, cls: styles.cardPurple },
              { label: t('report.clean', 'Bersih'),        value: cc.clean ?? 0,       icon: <CheckCircle size={16} color="#137333" />, cls: styles.cardGreen },
              { label: t('report.quarantine', 'Karantina'),     value: cc.quarantine ?? 0,  icon: <ShieldAlert size={16} color="#c5221f" />, cls: styles.cardRed },
            ].map((item) => (
              <div key={item.label} className={`${styles.summaryCard} ${item.cls}`}>
                <div className={styles.summaryCardTop}>
                  {item.icon}
                  <span className={styles.summaryLabel}>{item.label}</span>
                </div>
                <div className={styles.summaryValue}>{item.value.toLocaleString()}</div>
              </div>
            ))}
          </div>

          {/* ── Two-column: category breakdown + top recipients ── */}
          <div className={styles.twoCol}>
            <div className={styles.panel}>
              <h3 className={styles.panelTitle}>
                <TrendingUp size={15} /> {t('report.categoryDistribution', 'Distribusi Kategori')}
              </h3>
              <div className={styles.catRows}>
                {[
                  { label: t('report.phishing', 'Phishing'), value: cc.phishing ?? 0, color: THREAT_COLORS.phishing.bar },
                  { label: t('report.spam', 'Spam'),     value: cc.spam ?? 0,     color: THREAT_COLORS.spam.bar },
                  { label: t('report.malware', 'Malware'),  value: cc.malware ?? 0,  color: THREAT_COLORS.malware.bar },
                ].map((item) => (
                  <div key={item.label} className={styles.catRow}>
                    <div className={styles.catRowTop}>
                      <span className={styles.catName}>{item.label}</span>
                      <span className={styles.catPct}>
                        {totalThreats > 0 ? Math.round((item.value / totalThreats) * 100) : 0}%
                      </span>
                    </div>
                    <Bar value={item.value} max={maxCat} color={item.color} />
                  </div>
                ))}
              </div>
            </div>

            <div className={styles.panel}>
              <h3 className={styles.panelTitle}>
                <Users size={15} /> {t('report.topRecipients', 'Top Penerima Terbanyak')}
              </h3>
              {recipients.length === 0 ? (
                <p className={styles.panelEmpty}>{t('report.noData', 'Tidak ada data')}</p>
              ) : (
                <div className={styles.recipRows}>
                  {recipients.slice(0, 7).map((r, i) => (
                    <div key={i}>
                      <div className={styles.recipRowTop}>
                        <span className={styles.recipName} title={r.recipient}>{r.recipient}</span>
                        <span className={styles.recipStats}>
                          <span className={styles.phishCount}>{r.phishing}</span> {t('report.phish', 'phish')}
                          {' · '}
                          <span className={styles.spamCount}>{r.spam}</span> {t('report.spamLabel', 'spam')}
                        </span>
                      </div>
                      <Bar value={r.total} max={maxRecipient} color="#1a73e8" />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ── Top senders table ── */}
          <div className={styles.panel} style={{ marginBottom: 24 }}>
            <h3 className={styles.panelTitle}>
              <ShieldAlert size={15} color="#ea4335" /> {t('report.topSenders', 'Top 10 Pengirim Berbahaya')}
            </h3>
            {senders.length === 0 ? (
              <p className={styles.panelEmpty}>{t('report.noSenders', 'Tidak ada data pengirim berbahaya')}</p>
            ) : (
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      {[
                        t('report.tableHash', '#'),
                        t('common.sender', 'Pengirim'),
                        t('report.tableTotal', 'Total'),
                        t('report.phishing', 'Phishing'),
                        t('report.spam', 'Spam'),
                        t('report.malware', 'Malware'),
                        t('report.proportion', 'Proporsi')
                      ].map((h, i) => (
                        <th key={i}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {senders.map((s, i) => (
                      <tr key={i}>
                        <td className={styles.tdMuted}>{i + 1}</td>
                        <td className={styles.tdEllipsis} title={s.sender}>{s.sender}</td>
                        <td className={styles.tdBold}>{s.total}</td>
                        <td className={styles.tdRed}>{s.phishing}</td>
                        <td className={styles.tdYellow}>{s.spam}</td>
                        <td className={styles.tdPurple}>{s.malware}</td>
                        <td style={{ minWidth: 100 }}>
                          <Bar value={s.total} max={maxSender} color="#ea4335" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── Daily trend table ── */}
          <div className={styles.panel}>
            <h3 className={styles.panelTitle}>
              <TrendingUp size={15} color="#34a853" /> {t('report.dailyTrend', 'Tren Harian')}
            </h3>
            <p className={styles.periodNote}>{t('report.period', 'Periode')}: {rangeLabel} &nbsp;({trend.length} {t('report.days', 'hari')})</p>
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    {[
                      t('report.date', 'Tanggal'),
                      t('report.tableTotal', 'Total'),
                      t('report.clean', 'Bersih'),
                      t('report.warning', 'Peringatan'),
                      t('report.quarantine', 'Karantina')
                    ].map((h, i) => (
                      <th key={i}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {trend.map((d, i) => (
                    <tr key={i} className={d.quarantine > 0 ? styles.trDanger : ''}>
                      <td className={styles.tdMuted}>{d.date}</td>
                      <td className={styles.tdBold}>{d.total}</td>
                      <td className={styles.tdGreen}>{d.clean}</td>
                      <td className={styles.tdWarn}>{d.warn}</td>
                      <td className={d.quarantine > 0 ? styles.tdRed : styles.tdMuted}>{d.quarantine}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
