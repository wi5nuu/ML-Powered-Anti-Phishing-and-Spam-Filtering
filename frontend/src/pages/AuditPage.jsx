import { useState } from 'react'
import {
  ClipboardList, Filter, Download, ChevronLeft, ChevronRight,
  Loader2, Search, RefreshCw, Shield, Eye, Trash2, LogOut,
  AlertTriangle, Settings, Activity, Mail
} from 'lucide-react'
import GmailShell from '../components/layout/GmailShell'
import { useAuditLog, downloadEmailsCsv } from '../api/metrics'
import { useToast } from '../hooks/useToast'
import styles from './AuditPage.module.css'

// ─── Action icon mapping ─────────────────────────────────────────────────────────
const ACTION_CFG = {
  release:               { icon: LogOut,       color: '#34A853', label: 'Rilis' },
  confirm_spam:          { icon: Shield,        color: '#EA4335', label: 'Konfirmasi Spam' },
  report_false_positive: { icon: AlertTriangle, color: '#FBBC04', label: 'False Positive' },
  delete:                { icon: Trash2,        color: '#c5221f', label: 'Hapus' },
  manual_analyze:        { icon: Search,        color: '#1a73e8', label: 'Analisis Manual' },
  update_settings:       { icon: Settings,      color: '#8b44e8', label: 'Ubah Pengaturan' },
  view:                  { icon: Eye,           color: '#5f6368', label: 'Lihat' },
  login:                 { icon: Mail,          color: '#1a73e8', label: 'Login' },
}

function ActionBadge({ action }) {
  const cfg = ACTION_CFG[action] || { icon: Activity, color: '#5f6368', label: action }
  const Icon = cfg.icon
  return (
    <span className={styles.badge} style={{ background: `${cfg.color}18`, color: cfg.color }}>
      <Icon size={12} />
      {cfg.label}
    </span>
  )
}

// ─── Timeline item ───────────────────────────────────────────────────────────────
function TimelineItem({ item, isLast }) {
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
          <ActionBadge action={item.action} />
          <span className={styles.timelineUser}>
            oleh <strong>{item.username || 'sistem'}</strong>
          </span>
          {item.ip_address && (
            <span className={styles.timelineIp}>({item.ip_address})</span>
          )}
        </div>
        {item.details && (
          <div className={styles.timelineEmailId}>
            Detail: <span>{item.details}</span>
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

// ─── Pagination ──────────────────────────────────────────────────────────────────
function Pagination({ page, pages, onPageChange }) {
  return (
    <div className={styles.pagination}>
      <button
        className={styles.pageBtn}
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        id="audit-prev-btn"
      >
        <ChevronLeft size={16} />
      </button>
      <span className={styles.pageInfo}>Hal. {page} dari {pages || 1}</span>
      <button
        className={styles.pageBtn}
        onClick={() => onPageChange(page + 1)}
        disabled={page >= pages}
        id="audit-next-btn"
      >
        <ChevronRight size={16} />
      </button>
    </div>
  )
}

// ─── Main ────────────────────────────────────────────────────────────────────────
const EVENT_TYPES = [
  { value: '', label: 'Semua aksi' },
  { value: 'release', label: 'Rilis' },
  { value: 'confirm_spam', label: 'Konfirmasi Spam' },
  { value: 'report_false_positive', label: 'False Positive' },
  { value: 'delete', label: 'Hapus' },
  { value: 'manual_analyze', label: 'Analisis Manual' },
  { value: 'update_settings', label: 'Ubah Pengaturan' },
]

export default function AuditPage() {
  const { addToast } = useToast()
  const [page, setPage] = useState(1)
  const [eventType, setEventType] = useState('')
  const [usernameFilter, setUsernameFilter] = useState('')
  const [usernameInput, setUsernameInput] = useState('')
  const [isExporting, setIsExporting] = useState(false)

  const { data, isLoading, isError, refetch, isFetching } = useAuditLog({
    page,
    pageSize: 25,
    eventType: eventType || undefined,
    username: usernameFilter || undefined,
  })

  const items = data?.items || []
  const total = data?.total || 0
  const pages = data?.pages || 1

  const handleSearch = () => {
    setPage(1)
    setUsernameFilter(usernameInput)
  }

  const handleEventChange = (e) => {
    setPage(1)
    setEventType(e.target.value)
  }

  const handleExport = async () => {
    setIsExporting(true)
    try {
      await downloadEmailsCsv()
      addToast('Ekspor CSV berhasil diunduh.', 'success')
    } catch {
      addToast('Gagal mengekspor data.', 'error')
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <GmailShell>
      <div className={styles.wrap}>
        {/* Header */}
        <div className={styles.header}>
          <div>
            <h1 className={styles.title}><ClipboardList size={22} /> Audit Log</h1>
            <p className={styles.subtitle}>
              Rekam jejak semua aktivitas sistem — {total.toLocaleString()} entri total.
            </p>
          </div>
          <button
            className={styles.exportBtn}
            onClick={handleExport}
            disabled={isExporting}
            id="audit-export-btn"
          >
            {isExporting ? <Loader2 size={15} className={styles.spin} /> : <Download size={15} />}
            {isExporting ? 'Mengekspor...' : 'Ekspor CSV'}
          </button>
        </div>

        {/* Filters */}
        <div className={styles.filters}>
          <div className={styles.filterGroup}>
            <Filter size={15} className={styles.filterIcon} />
            <select
              className={styles.select}
              value={eventType}
              onChange={handleEventChange}
              id="audit-event-filter"
            >
              {EVENT_TYPES.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div className={styles.filterGroup}>
            <input
              className={styles.input}
              type="text"
              placeholder="Filter by username..."
              value={usernameInput}
              onChange={(e) => setUsernameInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              id="audit-username-filter"
            />
            <button
              className={styles.searchBtn}
              onClick={handleSearch}
              id="audit-search-btn"
            >
              <Search size={14} />
            </button>
          </div>

          <button
            className={styles.refreshBtn}
            onClick={() => refetch()}
            disabled={isFetching}
            id="audit-refresh-btn"
            title="Refresh"
          >
            <RefreshCw size={15} className={isFetching ? styles.spin : ''} />
          </button>
        </div>

        {/* Content */}
        {isLoading && (
          <div className={styles.loadingWrap}>
            <Loader2 size={24} className={styles.spin} />
            Memuat audit log...
          </div>
        )}

        {isError && (
          <div className={styles.errorWrap}>
            <AlertTriangle size={20} />
            Gagal memuat audit log. Anda mungkin tidak memiliki izin yang cukup.
          </div>
        )}

        {!isLoading && !isError && items.length === 0 && (
          <div className={styles.empty}>
            <ClipboardList size={48} opacity={0.15} />
            <p>Tidak ada entri audit log ditemukan.</p>
          </div>
        )}

        {!isLoading && items.length > 0 && (
          <>
            <div className={styles.timeline}>
              {items.map((item, i) => (
                <TimelineItem
                  key={item.id}
                  item={item}
                  isLast={i === items.length - 1}
                />
              ))}
            </div>

            <Pagination
              page={page}
              pages={pages}
              onPageChange={(p) => {
                setPage(p)
                window.scrollTo({ top: 0, behavior: 'smooth' })
              }}
            />
          </>
        )}
      </div>
    </GmailShell>
  )
}
