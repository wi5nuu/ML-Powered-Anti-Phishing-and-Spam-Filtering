import { useState, useEffect, useCallback } from 'react'
import api from '../api/client'
import {
  Shield, ShieldAlert, AlertTriangle, AlertCircle,
  Search, Filter, Trash2, Check, Flag,
  ExternalLink, ChevronLeft, ChevronRight
} from 'lucide-react'
import styles from './AdminQuarantineReview.module.css'

const CATEGORY_FILTERS = [
  { value: '', label: 'All Threats' },
  { value: 'spam', label: 'Spam' },
  { value: 'phishing', label: 'Phishing' },
  { value: 'malware', label: 'Malware' },
]

const LABEL_CONFIG = {
  QUARANTINE: { icon: ShieldAlert, cls: styles.badgeQuarantine, label: 'Quarantine' },
  WARN: { icon: AlertTriangle, cls: styles.badgeWarn, label: 'Warn' },
}

const CATEGORY_CONFIG = {
  spam: { cls: styles.badgeSpam, label: 'Spam' },
  phishing: { cls: styles.badgePhishing, label: 'Phishing' },
  malware: { cls: styles.badgeMalware, label: 'Malware' },
}

function formatDate(d) {
  if (!d) return '—'
  try {
    return new Date(d).toLocaleDateString('id-ID', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
    })
  } catch { return d }
}

export default function AdminQuarantineReview() {
  const [emails, setEmails] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize] = useState(50)
  const [msg, setMsg] = useState('')
  const [msgType, setMsgType] = useState('success')
  const [actionLoading, setActionLoading] = useState({})

  const fetchEmails = useCallback(() => {
    setLoading(true)
    setError(null)
    const params = { page, page_size: pageSize }
    if (category) params.category = category
    if (search.trim()) params.q = search.trim()
    api.get('/admin/quarantine', { params })
      .then((r) => {
        setEmails(Array.isArray(r.data.emails) ? r.data.emails : [])
        setTotal(r.data.total || 0)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.response?.data?.detail || err.message)
        setLoading(false)
      })
  }, [page, pageSize, category, search])

  useEffect(() => { fetchEmails() }, [fetchEmails])

  useEffect(() => {
    if (msg) {
      const t = setTimeout(() => setMsg(''), 4000)
      return () => clearTimeout(t)
    }
  }, [msg])

  const handleSearch = (e) => {
    setSearch(e.target.value)
    setPage(1)
  }

  const handleCategoryFilter = (val) => {
    setCategory(val)
    setPage(1)
  }

  const doAction = async (emailId, action) => {
    setActionLoading((prev) => ({ ...prev, [`${emailId}-${action}`]: true }))
    try {
      let res
      if (action === 'release') {
        res = await api.post(`/api/emails/${emailId}/release`)
      } else if (action === 'delete') {
        res = await api.delete(`/api/emails/${emailId}`)
      } else if (action === 'confirm-spam') {
        res = await api.post(`/api/emails/${emailId}/confirm-spam`)
      } else if (action === 'report-false-positive') {
        res = await api.post(`/api/emails/${emailId}/report-false-positive`, { notes: 'Admin review: false positive' })
      }
      setMsgType('success')
      setMsg(`Email ${action === 'release' ? 'released' : action === 'delete' ? 'deleted' : action === 'confirm-spam' ? 'confirmed as spam' : 'reported as false positive'} successfully`)
      fetchEmails()
    } catch (err) {
      setMsgType('error')
      setMsg(err.response?.data?.detail || `Failed to ${action}`)
    } finally {
      setActionLoading((prev) => ({ ...prev, [`${emailId}-${action}`]: false }))
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h2 className={styles.title}>
            <Shield size={20} />
            Quarantine Review
          </h2>
          <p className={styles.subtitle}>
            Review, release, or remove flagged emails
          </p>
        </div>
      </div>

      {msg && (
        <div className={`${styles.msg} ${msgType === 'success' ? styles.msgSuccess : styles.msgError}`}>
          {msgType === 'success' ? <Check size={16} /> : <AlertCircle size={16} />}
          {msg}
        </div>
      )}

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
          {CATEGORY_FILTERS.map((f) => (
            <button
              key={f.value}
              className={`${styles.filterChip} ${category === f.value ? styles.filterChipActive : ''}`}
              onClick={() => handleCategoryFilter(f.value)}
            >
              <Filter size={11} style={{ marginRight: 4 }} />
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.card}>
        {loading ? (
          <div className={styles.loadingState}>Loading quarantined emails...</div>
        ) : error ? (
          <div className={styles.emptyState}>Error: {error}</div>
        ) : emails.length === 0 ? (
          <div className={styles.emptyState}>No quarantined or flagged emails found.</div>
        ) : (
          <>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Category</th>
                  <th>Sender</th>
                  <th>Subject</th>
                  <th>Score</th>
                  <th>Detection Reason</th>
                  <th>Received</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {emails.map((email) => {
                  const labelCfg = LABEL_CONFIG[email.label] || LABEL_CONFIG.WARN
                  const LabelIcon = labelCfg.icon
                  const catCfg = CATEGORY_CONFIG[email.category] || { cls: styles.badgeSpam, label: email.category }
                  const scoreColor = email.fused_score >= 0.8 ? '#c5221f' : email.fused_score >= 0.6 ? '#856404' : '#137333'
                  return (
                    <tr key={email.email_id}>
                      <td>
                        <span className={`${styles.badge} ${labelCfg.cls}`}>
                          <LabelIcon size={11} />
                          {labelCfg.label}
                        </span>
                      </td>
                      <td>
                        <span className={`${styles.badge} ${catCfg.cls}`}>
                          {catCfg.label}
                        </span>
                      </td>
                      <td className={styles.senderCell} title={email.sender}>
                        {email.sender || '—'}
                      </td>
                      <td className={styles.subjectCell} title={email.subject}>
                        {email.subject || '(no subject)'}
                      </td>
                      <td>
                        <div className={styles.scoreBar}>
                          <span style={{ color: scoreColor }}>
                            {(email.fused_score * 100).toFixed(0)}%
                          </span>
                          <div className={styles.scoreTrack}>
                            <div
                              className={styles.scoreFill}
                              style={{
                                width: `${email.fused_score * 100}%`,
                                background: scoreColor,
                              }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className={styles.reasonCell} title={email.detection_reasons?.join(', ') || email.routing_reason || ''}>
                        {email.detection_reasons?.[0] || email.routing_reason || '—'}
                      </td>
                      <td className={styles.dateCell}>
                        {formatDate(email.received_at)}
                      </td>
                      <td className={styles.actionsCell}>
                        <button
                          className={`${styles.actionBtn} ${styles.actionRelease}`}
                          onClick={() => doAction(email.email_id, 'release')}
                          disabled={actionLoading[`${email.email_id}-release`]}
                          title="Release email (mark as safe)"
                        >
                          <Check size={12} />
                          Release
                        </button>
                        <button
                          className={`${styles.actionBtn} ${styles.actionSpam}`}
                          onClick={() => doAction(email.email_id, 'confirm-spam')}
                          disabled={actionLoading[`${email.email_id}-confirm-spam`]}
                          title="Confirm as spam"
                        >
                          <Flag size={12} />
                          Spam
                        </button>
                        <button
                          className={`${styles.actionBtn} ${styles.actionFp}`}
                          onClick={() => doAction(email.email_id, 'report-false-positive')}
                          disabled={actionLoading[`${email.email_id}-report-false-positive`]}
                          title="Report as false positive"
                        >
                          <ExternalLink size={12} />
                          FP
                        </button>
                        <button
                          className={`${styles.actionBtn} ${styles.actionDelete}`}
                          onClick={() => doAction(email.email_id, 'delete')}
                          disabled={actionLoading[`${email.email_id}-delete`]}
                          title="Delete email"
                        >
                          <Trash2 size={12} />
                          Delete
                        </button>
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
