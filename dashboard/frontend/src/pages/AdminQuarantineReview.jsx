import { useEffect, useState } from 'react'
import api from '../api/client'
import { ShieldCheck, RefreshCw, AlertCircle, Check, X, Search } from 'lucide-react'
import styles from './AdminPage.module.css'
import { useTranslation } from '../i18n/context'

const CAT_COLOR = {
  phishing: { bg: '#fce8e6', text: '#c5221f' },
  spam:     { bg: '#fef3cd', text: '#856404' },
  malware:  { bg: '#f3e5f5', text: '#6a1b9a' },
}

export default function AdminQuarantineReview() {
  const { t } = useTranslation()
  const [emails,         setEmails]         = useState([])
  const [loading,        setLoading]        = useState(true)
  const [error,          setError]          = useState('')
  const [success,        setSuccess]        = useState('')
  const [page,           setPage]           = useState(1)
  const [total,          setTotal]          = useState(0)
  const [searchInput,    setSearchInput]    = useState('')
  const [search,         setSearch]         = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const PAGE_SIZE = 30

  const fetchEmails = (p = 1, q = search, cat = categoryFilter) => {
    setLoading(true); setError('')
    const params = { page: p, page_size: PAGE_SIZE }
    if (q)   params.q        = q
    if (cat) params.category = cat
    api.get('/admin/quarantine', { params })
      .then(({ data }) => {
        setEmails(Array.isArray(data?.emails) ? data.emails : [])
        setTotal(data?.total || 0)
      })
      .catch((e) => setError(e.response?.data?.detail || t('quarantine.loadError', 'Gagal memuat karantina.')))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchEmails(page) }, [page])

  const flash      = (msg) => { setSuccess(msg); setTimeout(() => setSuccess(''), 3500) }
  const handleSearch = (e) => { e.preventDefault(); setPage(1); setSearch(searchInput); fetchEmails(1, searchInput, categoryFilter) }
  const handleCat    = (val) => { setCategoryFilter(val); setPage(1); fetchEmails(1, search, val) }
  const handleClear  = () => { setSearchInput(''); setSearch(''); setCategoryFilter(''); setPage(1); fetchEmails(1, '', '') }

  const handleRelease = (id) => {
    api.post(`/emails/${id}/release`)
      .then(() => { fetchEmails(page); flash(t('quarantine.releaseSuccess', 'Email dilepas dari karantina.')) })
      .catch((e) => setError(e.response?.data?.detail || t('quarantine.releaseError', 'Gagal melepas email.')))
  }

  const handleDelete = (id, subject) => {
    const label = subject ? `"${subject.slice(0, 60)}"` : t('quarantine.thisEmail', 'email ini')
    if (!window.confirm(`${t('quarantine.confirmDelete', 'Hapus permanen')} ${label}? ${t('quarantine.confirmDeleteSuffix', 'Tindakan ini tidak dapat dibatalkan.')}`)) return
    api.delete(`/emails/${id}`)
      .then(() => { fetchEmails(page); flash(t('quarantine.deleteSuccess', 'Email dihapus.')) })
      .catch((e) => setError(e.response?.data?.detail || t('quarantine.deleteError', 'Gagal menghapus email.')))
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div style={{ padding: '0 0 24px' }}>
      {success && <div className={styles.msg}>{success}</div>}

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <div className={styles.sectionTitle}>
            <ShieldCheck size={16} />
            <div>
              <strong>{t('quarantine.title')}</strong>
              <span>{total} {t('quarantine.total', 'email dikarantina')}</span>
            </div>
          </div>
          <button onClick={() => fetchEmails(page)} disabled={loading} className={styles.actionBtn}>
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
              placeholder={t('quarantine.searchPlaceholder', 'Cari subjek atau pengirim...')}
            />
            {(searchInput || search || categoryFilter) && (
              <button type="button" onClick={handleClear} className={styles.clearBtn}>
                <X size={12} />
              </button>
            )}
          </form>
          <select className={styles.filterSelect} value={categoryFilter} onChange={(e) => handleCat(e.target.value)}>
            <option value="">{t('quarantine.allCategories', 'Semua Kategori')}</option>
            <option value="phishing">{t('gmail.phishing')}</option>
            <option value="spam">{t('gmail.spam')}</option>
            <option value="malware">{t('gmail.malware')}</option>
          </select>
        </div>

        {error && (
          <div style={{ padding: '10px 16px', background: '#fce8e6', color: '#c5221f', fontSize: '0.8125rem', display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {loading ? (
          <div className={styles.emptyState}>{t('quarantine.loading')}</div>
        ) : emails.length === 0 ? (
          <div className={styles.emptyState}>{t('quarantine.empty')}</div>
        ) : (
          <>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>{t('common.subject', 'Subjek')}</th>
                  <th>{t('common.sender', 'Pengirim')}</th>
                  <th>{t('common.recipient', 'Penerima')}</th>
                  <th>{t('common.category', 'Kategori')}</th>
                  <th>{t('common.score', 'Skor')}</th>
                  <th>{t('common.received', 'Diterima')}</th>
                  <th style={{ textAlign: 'right' }}>{t('common.actions', 'Aksi')}</th>
                </tr>
              </thead>
              <tbody>
                {emails.map((e) => {
                  const cc = CAT_COLOR[e.category] || { bg: '#f1f3f4', text: '#5f6368' }
                  return (
                    <tr key={e.email_id || e.id}>
                      <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={e.subject}>
                        {e.subject || <span style={{ color: 'var(--text-muted)' }}>{t('common.noSubject', '(no subject)')}</span>}
                      </td>
                      <td className={styles.mono} style={{ fontSize: '0.75rem' }}>{e.sender}</td>
                      <td className={styles.mono} style={{ fontSize: '0.75rem' }}>{e.recipient}</td>
                      <td>
                        <span className={styles.categoryBadge} style={{ background: cc.bg, color: cc.text }}>
                          {e.category}
                        </span>
                      </td>
                      <td className={styles.mono}>{e.fused_score != null ? Number(e.fused_score).toFixed(3) : t('common.na', '\u2014')}</td>
                      <td className={styles.mono} style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                        {e.received_at ? new Date(e.received_at).toLocaleDateString('id-ID') : t('common.na', '\u2014')}
                      </td>
                      <td>
                        <div className={styles.actionGroup} style={{ justifyContent: 'flex-end' }}>
                          <button onClick={() => handleRelease(e.email_id || e.id)} className={styles.actionBtn} title={t('quarantine.releaseTitle', 'Lepas dari karantina')} style={{ color: '#16a34a' }}>
                            <Check size={13} />
                          </button>
                          <button onClick={() => handleDelete(e.email_id || e.id, e.subject)} className={`${styles.actionBtn} ${styles.dangerActionBtn}`} title={t('quarantine.deleteTitle', 'Hapus permanen')}>
                            <X size={13} />
                          </button>
                        </div>
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
