import { useEffect, useState } from 'react'
import api from '../api/client'
import { FileText, RefreshCw, AlertCircle, Search, X } from 'lucide-react'
import styles from './AdminPage.module.css'
import { useTranslation } from '../i18n/context'

const LABEL_COLOR = {
  CLEAN:      { bg: '#e8f5e9', text: '#137333' },
  WARN:       { bg: '#fef3cd', text: '#856404' },
  QUARANTINE: { bg: '#fce8e6', text: '#c5221f' },
}

const CAT_COLOR = {
  phishing: { bg: '#fce8e6', text: '#c5221f' },
  spam:     { bg: '#fef3cd', text: '#856404' },
  malware:  { bg: '#f3e5f5', text: '#6a1b9a' },
  clean:    { bg: '#e8f5e9', text: '#137333' },
}

export default function AdminDetectionLogs() {
  const { t } = useTranslation()
  const [logs,         setLogs]         = useState([])
  const [loading,      setLoading]      = useState(true)
  const [error,        setError]        = useState('')
  const [page,         setPage]         = useState(1)
  const [total,        setTotal]        = useState(0)
  const [search,       setSearch]       = useState('')
  const [searchInput,  setSearchInput]  = useState('')
  const [labelFilter,  setLabelFilter]  = useState('')
  const PAGE_SIZE = 30

  const fetchLogs = (p = 1, q = search, label = labelFilter) => {
    setLoading(true); setError('')
    const params = { page: p, page_size: PAGE_SIZE }
    if (q)     params.q     = q
    if (label) params.label = label
    api.get('/admin/detection-logs', { params })
      .then(({ data }) => {
        setLogs(Array.isArray(data?.logs) ? data.logs : [])
        setTotal(data?.total || 0)
      })
      .catch((e) => setError(e.response?.data?.detail || t('logs.loadError', 'Gagal memuat log deteksi.')))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchLogs(page) }, [page])

  const handleSearch = (e) => { e.preventDefault(); setPage(1); setSearch(searchInput); fetchLogs(1, searchInput, labelFilter) }
  const handleLabel  = (val) => { setLabelFilter(val); setPage(1); fetchLogs(1, search, val) }
  const handleClear  = () => { setSearchInput(''); setSearch(''); setLabelFilter(''); setPage(1); fetchLogs(1, '', '') }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div style={{ padding: '0 0 24px' }}>
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <div className={styles.sectionTitle}>
            <FileText size={16} />
            <div>
              <strong>{t('logs.title')}</strong>
              <span>{total.toLocaleString()} {t('logs.total')}</span>
            </div>
          </div>
          <button onClick={() => fetchLogs(page)} disabled={loading} className={styles.actionBtn}>
            <RefreshCw size={13} />
          </button>
        </div>

        {/* Filters */}
        <div className={styles.filterBar}>
          <form onSubmit={handleSearch} className={styles.searchForm}>
            <Search size={13} className={styles.searchIcon} />
            <input
              className={styles.searchInput}
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder={t('logs.searchPlaceholder')}
            />
            {(searchInput || search || labelFilter) && (
              <button type="button" onClick={handleClear} className={styles.clearBtn}>
                <X size={12} />
              </button>
            )}
          </form>
          <select className={styles.filterSelect} value={labelFilter} onChange={(e) => handleLabel(e.target.value)}>
            <option value="">{t('logs.allLabels')}</option>
            <option value="CLEAN">{t('label.clean', 'Clean')}</option>
            <option value="WARN">{t('label.warn', 'Warn')}</option>
            <option value="QUARANTINE">{t('label.quarantine', 'Quarantine')}</option>
          </select>
        </div>

        {error && (
          <div style={{ padding: '10px 16px', background: '#fce8e6', color: '#c5221f', fontSize: '0.8125rem', display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {loading ? (
          <div className={styles.emptyState}>{t('logs.loading')}</div>
        ) : logs.length === 0 ? (
          <div className={styles.emptyState}>{t('logs.empty')}</div>
        ) : (
          <>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>{t('common.subject', 'Subjek')}</th>
                  <th>{t('common.sender', 'Pengirim')}</th>
                  <th>{t('common.recipient', 'Penerima')}</th>
                  <th>{t('common.category', 'Kategori')}</th>
                  <th>{t('common.label', 'Label')}</th>
                  <th>{t('common.score', 'Skor')}</th>
                  <th style={{ whiteSpace: 'nowrap' }}>{t('common.received', 'Diterima')}</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => {
                  const lc = LABEL_COLOR[log.label] || { bg: '#f1f3f4', text: '#5f6368' }
                  const cc = CAT_COLOR[log.category] || { bg: '#f1f3f4', text: '#5f6368' }
                  return (
                    <tr key={log.email_id || log.id}>
                      <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={log.subject}>
                        {log.subject || <span style={{ color: 'var(--text-muted)' }}>{t('common.noSubject', '(no subject)')}</span>}
                      </td>
                      <td className={styles.mono} style={{ fontSize: '0.75rem' }}>{log.sender}</td>
                      <td className={styles.mono} style={{ fontSize: '0.75rem' }}>{log.recipient}</td>
                      <td>
                        <span className={styles.categoryBadge} style={{ background: cc.bg, color: cc.text }}>
                          {log.category}
                        </span>
                      </td>
                      <td>
                        <span className={styles.categoryBadge} style={{ background: lc.bg, color: lc.text }}>
                          {log.label}
                        </span>
                      </td>
                      <td className={styles.mono}>{log.fused_score != null ? Number(log.fused_score).toFixed(3) : t('common.na', '\u2014')}</td>
                      <td className={styles.mono} style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                        {log.received_at ? new Date(log.received_at).toLocaleDateString('id-ID') : t('common.na', '\u2014')}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {totalPages > 1 && (
              <div className={styles.pagination}>
                <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className={styles.pageBtn}>
                  {t('common.previous', 'Sebelumnya')}
                </button>
                <span className={styles.pageInfo}>{page} / {totalPages}</span>
                <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} className={styles.pageBtn}>
                  {t('common.next', 'Selanjutnya')}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
