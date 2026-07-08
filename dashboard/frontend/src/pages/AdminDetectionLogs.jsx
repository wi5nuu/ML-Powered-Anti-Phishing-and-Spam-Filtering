import { useState, useEffect, useCallback } from 'react'
import api from '../api/client'
import {
  ClipboardList, Search, Filter,
  ChevronLeft, ChevronRight, AlertCircle
} from 'lucide-react'
import styles from './AdminDetectionLogs.module.css'

const LABEL_FILTERS = [
  { value: '', label: 'All Results' },
  { value: 'CLEAN', label: 'Clean' },
  { value: 'WARN', label: 'Warn' },
  { value: 'QUARANTINE', label: 'Quarantine' },
]

const LABEL_CONFIG = {
  CLEAN: { cls: styles.badgeClean, label: 'Clean' },
  WARN: { cls: styles.badgeWarn, label: 'Warn' },
  QUARANTINE: { cls: styles.badgeQuarantine, label: 'Quarantine' },
}

const STATUS_CONFIG = {
  pending: { cls: styles.statusPending, label: 'Pending' },
  released: { cls: styles.statusReleased, label: 'Released' },
  confirmed_spam: { cls: styles.statusConfirmed, label: 'Confirmed Spam' },
  trash: { cls: styles.statusTrash, label: 'Deleted' },
}

function formatDate(d) {
  if (!d) return '—'
  try {
    return new Date(d).toLocaleDateString('id-ID', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    })
  } catch { return d }
}

function getScoreColor(score) {
  if (score >= 0.8) return '#c5221f'
  if (score >= 0.6) return '#856404'
  return '#137333'
}

export default function AdminDetectionLogs() {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [label, setLabel] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize] = useState(50)

  const fetchLogs = useCallback(() => {
    setLoading(true)
    setError(null)
    const params = { page, page_size: pageSize }
    if (label) params.label = label
    if (search.trim()) params.q = search.trim()
    api.get('/api/admin/detection-logs', { params })
      .then((r) => {
        setLogs(Array.isArray(r.data.logs) ? r.data.logs : [])
        setTotal(r.data.total || 0)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.response?.data?.detail || err.message)
        setLoading(false)
      })
  }, [page, pageSize, label, search])

  useEffect(() => { fetchLogs() }, [fetchLogs])

  const handleSearch = (e) => {
    setSearch(e.target.value)
    setPage(1)
  }

  const handleLabelFilter = (val) => {
    setLabel(val)
    setPage(1)
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h2 className={styles.title}>
            <ClipboardList size={20} />
            Detection Logs
          </h2>
          <p className={styles.subtitle}>
            All processed emails with prediction results, decisions, and actions
          </p>
        </div>
      </div>

      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <Search size={15} className={styles.searchIcon} />
          <input
            className={styles.searchInput}
            placeholder="Search sender, subject, email ID..."
            value={search}
            onChange={handleSearch}
          />
        </div>
        <div className={styles.filterGroup}>
          {LABEL_FILTERS.map((f) => (
            <button
              key={f.value}
              className={`${styles.filterChip} ${label === f.value ? styles.filterChipActive : ''}`}
              onClick={() => handleLabelFilter(f.value)}
            >
              <Filter size={11} style={{ marginRight: 4 }} />
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.card}>
        {loading ? (
          <div className={styles.loadingState}>Loading detection logs...</div>
        ) : error ? (
          <div className={styles.emptyState}>Error: {error}</div>
        ) : logs.length === 0 ? (
          <div className={styles.emptyState}>No detection logs found.</div>
        ) : (
          <>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Prediction</th>
                  <th>Decision</th>
                  <th>Sender</th>
                  <th>Subject</th>
                  <th>Score</th>
                  <th>Action Taken</th>
                  <th>Detected At</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => {
                  const labelCfg = LABEL_CONFIG[log.label] || LABEL_CONFIG.CLEAN
                  const statusCfg = STATUS_CONFIG[log.status] || STATUS_CONFIG.pending
                  const scoreColor = getScoreColor(log.fused_score)
                  return (
                    <tr key={log.email_id}>
                      <td>
                        <span className={`${styles.badge} ${labelCfg.cls}`}>
                          {labelCfg.label}
                        </span>
                      </td>
                      <td>
                        <span className={`${styles.statusBadge} ${statusCfg.cls}`}>
                          {statusCfg.label}
                        </span>
                      </td>
                      <td className={styles.senderCell} title={log.sender}>
                        {log.sender || '—'}
                      </td>
                      <td className={styles.subjectCell} title={log.subject}>
                        {log.subject || '(no subject)'}
                      </td>
                      <td>
                        <div className={styles.scoreBar}>
                          <span style={{ color: scoreColor }}>
                            {(log.fused_score * 100).toFixed(0)}%
                          </span>
                          <div className={styles.scoreTrack}>
                            <div
                              className={styles.scoreFill}
                              style={{
                                width: `${log.fused_score * 100}%`,
                                background: scoreColor,
                              }}
                            />
                          </div>
                        </div>
                      </td>
                      <td>
                        {log.action_taken ? (
                          <div className={styles.actionRow}>
                            <span className={styles.actionBadge}>{log.action_taken}</span>
                            {log.action_by && (
                              <> by <strong>{log.action_by}</strong></>
                            )}
                          </div>
                        ) : (
                          <span className={styles.actionRow} style={{ color: '#9ca3af' }}>
                            No action
                          </span>
                        )}
                      </td>
                      <td className={styles.dateCell}>
                        {formatDate(log.received_at)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {totalPages > 1 && (
              <div className={styles.pagination}>
                <button
                  className={styles.pageBtn}
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft size={14} />
                </button>
                <span className={styles.pageInfo}>
                  Page {page} of {totalPages} ({total} total)
                </span>
                <button
                  className={styles.pageBtn}
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
