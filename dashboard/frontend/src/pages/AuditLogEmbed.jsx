import { useState } from 'react'
import { useTranslation } from '../i18n/context'
import {
  ClipboardList, Filter, Download, ChevronLeft, ChevronRight,
  Loader2, Search, RefreshCw, Shield, Eye, Trash2, LogOut,
  AlertTriangle, Settings, Activity, Mail
} from 'lucide-react'
import { useAuditLog } from '../api/metrics'
import styles from './AuditPage.module.css'

// Download audit log as CSV (separate from email CSV export)
// DISABLED: Backend endpoint /audit-log/export-csv does not exist yet
// TODO: Implement backend endpoint GET /api/audit-log/export-csv if CSV export is needed
async function downloadAuditLogCsv() {
  console.warn('Audit log CSV export not yet implemented on backend')
  alert('CSV export untuk audit log belum tersedia. Silakan hubungi administrator.')
  return
  /* Uncomment when backend endpoint is ready:
  const { default: api } = await import('../api/client')
  const { APP_TIME_ZONE } = await import('../utils/time')
  const response = await api.get('/audit-log/export-csv', { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  const date = new Date().toLocaleDateString('en-CA', { timeZone: APP_TIME_ZONE })
  link.setAttribute('download', `cognimail_audit_log_${date}.csv`)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
  */
}

const ACTION_CFG = {
  release:               { icon: LogOut,       color: '#34A853' },
  confirm_spam:          { icon: Shield,        color: '#EA4335' },
  report_false_positive: { icon: AlertTriangle, color: '#FBBC04' },
  delete:                { icon: Trash2,        color: '#c5221f' },
  manual_analyze:        { icon: Search,        color: '#1a73e8' },
  update_settings:       { icon: Settings,      color: '#8b44e8' },
  view:                  { icon: Eye,           color: '#5f6368' },
  login:                 { icon: Mail,          color: '#1a73e8' },
}

function ActionBadge({ action, t }) {
  const cfg = ACTION_CFG[action] || { icon: Activity, color: '#5f6368' }
  const Icon = cfg.icon
  const label = t(`audit.action.${action}`, action)
  return (
    <span className={styles.badge} style={{ background: `${cfg.color}18`, color: cfg.color }}>
      <Icon size={12} />
      {label}
    </span>
  )
}

function TimelineItem({ item, isLast, t }) {
  const cfg = ACTION_CFG[item.action] || { icon: Activity, color: '#5f6368' }
  const Icon = cfg.icon
  const dt = new Date(item.created_at)
  const dateStr = dt.toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' })
  const timeStr = dt.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  return (
    <div className={styles.timelineItem}>
      <div className={styles.timelineLine}>
        <div className={styles.timelineDot} style={{ background: cfg.color }}>
          <Icon size={12} color="#fff" />
        </div>
        {!isLast && <div className={styles.timelineConnector} />}
      </div>
      <div className={styles.timelineContent}>
        <div className={styles.timelineTop}>
          <ActionBadge action={item.action} t={t} />
          <span className={styles.timelineUser}>
            {t('audit.by', 'oleh')} <strong>{item.username || t('audit.system', 'sistem')}</strong>
          </span>
          {item.ip_address && (
            <span className={styles.timelineIp}>({item.ip_address})</span>
          )}
        </div>
        {item.details && (
          <div className={styles.timelineEmailId}>
            {t('audit.detail', 'Detail')}: <span>{item.details}</span>
          </div>
        )}
        {item.notes && (
          <div className={styles.timelineNotes}>{item.notes}</div>
        )}
        <div className={styles.timelineTime}>
          {dateStr} • {timeStr}
        </div>
      </div>
    </div>
  )
}

function Pagination({ page, pages, onPageChange, t }) {
  return (
    <div className={styles.pagination}>
      <button className={styles.pageBtn} onClick={() => onPageChange(page - 1)} disabled={page <= 1}>
        <ChevronLeft size={16} />
      </button>
      <span className={styles.pageInfo}>{t('audit.page', 'Hal.')} {page} {t('audit.of', 'dari')} {pages || 1}</span>
      <button className={styles.pageBtn} onClick={() => onPageChange(page + 1)} disabled={page >= pages}>
        <ChevronRight size={16} />
      </button>
    </div>
  )
}

export default function AuditLogEmbed() {
  const { t } = useTranslation()
  const [page, setPage] = useState(1)
  const [eventType, setEventType] = useState('')
  const [usernameFilter, setUsernameFilter] = useState('')
  const [usernameInput, setUsernameInput] = useState('')
  const [isExporting, setIsExporting] = useState(false)
  const [exportMsg, setExportMsg] = useState('')

  const EVENT_TYPES = [
    { value: '', label: t('audit.allActions', 'Semua aksi') },
    { value: 'release', label: t('audit.action.release', 'Rilis') },
    { value: 'confirm_spam', label: t('audit.action.confirmSpam', 'Konfirmasi Spam') },
    { value: 'report_false_positive', label: t('audit.action.falsePositive', 'False Positive') },
    { value: 'delete', label: t('audit.action.delete', 'Hapus') },
    { value: 'manual_analyze', label: t('audit.action.manualAnalyze', 'Analisis Manual') },
    { value: 'update_settings', label: t('audit.action.updateSettings', 'Ubah Pengaturan') },
  ]

  const { data, isLoading, isError, refetch, isFetching } = useAuditLog({
    page,
    pageSize: 25,
    eventType: eventType || undefined,
    username: usernameFilter || undefined,
  })

  const items = data?.items || []
  const total = data?.total || 0
  const pages = data?.pages || 1

  const handleSearch = () => { setPage(1); setUsernameFilter(usernameInput) }
  const handleEventChange = (e) => { setPage(1); setEventType(e.target.value) }

  const handleExport = async () => {
    setIsExporting(true)
    try {
      await downloadAuditLogCsv()
      setExportMsg(t('audit.exportSuccess', 'Ekspor CSV berhasil.'))
      setTimeout(() => setExportMsg(''), 3000)
    } catch {
      setExportMsg(t('audit.exportError', 'Gagal mengekspor.'))
      setTimeout(() => setExportMsg(''), 3000)
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div className={styles.wrap}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}><ClipboardList size={22} /> {t('audit.title', 'Audit Log')}</h1>
          <p className={styles.subtitle}>
            {t('audit.subtitle', 'Rekam jejak semua aktivitas sistem — {total} entri total.').replace('{total}', total.toLocaleString())}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {exportMsg && <span style={{ fontSize: '0.8rem', color: exportMsg.includes('berhasil') ? '#137333' : '#c5221f' }}>{exportMsg}</span>}
          <button className={styles.exportBtn} onClick={handleExport} disabled={isExporting}>
            {isExporting ? <Loader2 size={15} className={styles.spin} /> : <Download size={15} />}
            {isExporting ? t('audit.exporting', 'Mengekspor...') : t('audit.exportCsv', 'Ekspor CSV')}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className={styles.filters}>
        <div className={styles.filterGroup}>
          <Filter size={15} className={styles.filterIcon} />
          <select className={styles.select} value={eventType} onChange={handleEventChange}>
            {EVENT_TYPES.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className={styles.filterGroup}>
          <input
            className={styles.input}
            type="text"
            placeholder={t('audit.filterByUsername', 'Filter by username...')}
            value={usernameInput}
            onChange={(e) => setUsernameInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
          <button className={styles.searchBtn} onClick={handleSearch}>
            <Search size={14} />
          </button>
        </div>
        <button className={styles.refreshBtn} onClick={() => refetch()} disabled={isFetching} title={t('audit.refresh', 'Refresh')}>
          <RefreshCw size={15} className={isFetching ? styles.spin : ''} />
        </button>
      </div>

      {/* Content */}
      {isLoading && (
        <div className={styles.loadingWrap}>
          <Loader2 size={24} className={styles.spin} /> {t('audit.loading', 'Memuat audit log...')}
        </div>
      )}
      {isError && (
        <div className={styles.errorWrap}>
          <AlertTriangle size={20} /> {t('audit.loadError', 'Gagal memuat audit log. Anda mungkin tidak memiliki izin yang cukup.')}
        </div>
      )}
      {!isLoading && !isError && items.length === 0 && (
        <div className={styles.empty}>
          <ClipboardList size={48} opacity={0.15} />
          <p>{t('audit.empty', 'Tidak ada entri audit log ditemukan.')}</p>
        </div>
      )}
      {!isLoading && items.length > 0 && (
        <>
          <div className={styles.timeline}>
            {items.map((item, i) => (
              <TimelineItem key={item.id} item={item} isLast={i === items.length - 1} t={t} />
            ))}
          </div>
          <Pagination page={page} pages={pages} onPageChange={(p) => setPage(p)} t={t} />
        </>
      )}
    </div>
  )
}
