import { useState, useEffect } from 'react'
import api from '../api/client'
import {
  Shield, ShieldAlert, AlertTriangle, Mail, Users, XCircle,
  TrendingUp, TrendingDown, Search, Filter, Download, ChevronLeft, ChevronRight,
  X, ChevronUp, ChevronDown, BarChart3
} from 'lucide-react'
import styles from './SuperadminSpamStats.module.css'

const CATEGORY_OPTIONS = [
  { value: 'all', label: 'All Categories' },
  { value: 'spam', label: 'Spam' },
  { value: 'phishing', label: 'Phishing' },
  { value: 'malware', label: 'Malware' },
  { value: 'clean', label: 'Clean' },
]

const SCOPE_OPTIONS = [
  { value: 'all', label: 'All Recipients' },
  { value: 'admin', label: 'Admin Emails Only' },
  { value: 'user', label: 'User Emails Only' },
]

const MAX_BAR = 100

export default function SuperadminSpamStats() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [scope, setScope] = useState('all')
  const [category, setCategory] = useState('all')
  const [page, setPage] = useState(0)
  const [selectedAdmin, setSelectedAdmin] = useState(null)
  const [adminDetail, setAdminDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const perPage = 20

  const fetchData = () => {
    setLoading(true)
    api.get('/superadmin/spam-stats', { params: { scope, category, limit: 200 } })
      .then((r) => { setData(r.data); setLoading(false) })
      .catch((err) => { setError(err.response?.data?.detail || err.message); setLoading(false) })
  }

  useEffect(() => { fetchData() }, [scope, category])

  const handleAdminClick = async (username) => {
    if (selectedAdmin === username) {
      setSelectedAdmin(null)
      setAdminDetail(null)
      return
    }
    setSelectedAdmin(username)
    setDetailLoading(true)
    try {
      const r = await api.get(`/superadmin/admin-emails/${username}`)
      setAdminDetail(r.data)
    } catch (err) {
      setAdminDetail({ error: err.response?.data?.detail || err.message })
    }
    setDetailLoading(false)
  }

  const results = data?.results || []
  const totalPages = Math.ceil(results.length / perPage)
  const pageResults = results.slice(page * perPage, (page + 1) * perPage)
  const maxCount = Math.max(...results.map(r => r.total), 1)

  const colorForCategory = (cat) => {
    switch (cat) {
      case 'spam': return '#D97706'
      case 'phishing': return '#DC2626'
      case 'malware': return '#7C3AED'
      case 'clean': return '#059669'
      default: return '#6B7280'
    }
  }

  const totalStats = {
    total: results.reduce((s, r) => s + r.total, 0),
    spam: results.reduce((s, r) => s + r.spam, 0),
    phishing: results.reduce((s, r) => s + r.phishing, 0),
    malware: results.reduce((s, r) => s + r.malware, 0),
    clean: results.reduce((s, r) => s + r.clean, 0),
  }

  if (loading && !data) {
    return (
      <div className={styles.loadingState}>
        <div className={styles.spinner} />
        <span>Memuat statistik...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.errorState}>
        <XCircle size={32} />
        <h3>Gagal Memuat Data</h3>
        <p>{error}</p>
        <button className={styles.retryBtn} onClick={fetchData}>Coba Lagi</button>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}><Shield size={22} /> Spam Stats</h1>
          <p className={styles.subtitle}>Top spam/phishing/malware recipients across all organizations.</p>
        </div>
      </div>

      <div className={styles.filterBar}>
        <div className={styles.filterGroup}>
          <Filter size={14} />
          <label>Scope:</label>
          <select value={scope} onChange={(e) => { setScope(e.target.value); setPage(0); setSelectedAdmin(null); setAdminDetail(null) }}>
            {SCOPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className={styles.filterGroup}>
          <label>Category:</label>
          <select value={category} onChange={(e) => { setCategory(e.target.value); setPage(0); setSelectedAdmin(null); setAdminDetail(null) }}>
            {CATEGORY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className={styles.filterGroup}>
          <Mail size={14} />
          <span>{results.length} recipients</span>
        </div>
        <div className={styles.filterGroup}>
          <Download size={14} />
          <span>{totalStats.total.toLocaleString()} total emails</span>
        </div>
      </div>

      <div className={styles.statsBar}>
        <div className={styles.statChip}>
          <AlertTriangle size={16} color="#D97706" />
          <span>Spam</span>
          <span className={styles.statChipValue} style={{ color: '#D97706' }}>{totalStats.spam.toLocaleString()}</span>
        </div>
        <div className={styles.statChip}>
          <ShieldAlert size={16} color="#DC2626" />
          <span>Phishing</span>
          <span className={styles.statChipValue} style={{ color: '#DC2626' }}>{totalStats.phishing.toLocaleString()}</span>
        </div>
        <div className={styles.statChip}>
          <Shield size={16} color="#7C3AED" />
          <span>Malware</span>
          <span className={styles.statChipValue} style={{ color: '#7C3AED' }}>{totalStats.malware.toLocaleString()}</span>
        </div>
        <div className={styles.statChip}>
          <Shield size={16} color="#059669" />
          <span>Clean</span>
          <span className={styles.statChipValue} style={{ color: '#059669' }}>{totalStats.clean.toLocaleString()}</span>
        </div>
      </div>

      {/* Admin Cards with Drill-Down */}
      {scope === 'all' && data?.admins?.length > 0 && (
        <div className={styles.adminSection}>
          <div className={styles.adminGrid}>
            {data.admins.map((adm) => (
              <div key={adm.username}>
                <div
                  className={`${styles.adminCard} ${selectedAdmin === adm.username ? styles.adminCardActive : ''}`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => handleAdminClick(adm.username)}
                >
                  <div className={styles.adminCardHeader}>
                    <div className={styles.adminAvatar} style={{ background: '#EEF2FF', color: '#4F46E5' }}>
                      {adm.username.slice(0, 2).toUpperCase()}
                    </div>
                    <div className={styles.adminInfo}>
                      <span className={styles.adminName}>{adm.username}</span>
                      <span className={styles.adminOrg}>{adm.email || '-'}</span>
                    </div>
                    <div style={{ textAlign: 'right', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                      <div>{adm.total_users} users</div>
                      <div>{adm.mailboxes?.length || 0} emails</div>
                    </div>
                    <span style={{ marginLeft: 8, color: 'var(--text-muted)' }}>
                      {selectedAdmin === adm.username ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </span>
                  </div>
                  {adm.mailboxes?.length > 0 && (
                    <div className={styles.adminMboxList}>
                      {adm.mailboxes.map((mb) => (
                        <span key={mb} className={styles.mboxChip}><Mail size={10} />{mb}</span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Drill-Down Detail */}
                {selectedAdmin === adm.username && (
                  <div className={styles.drillDown}>
                    {detailLoading ? (
                      <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                        <div className={styles.spinner} style={{ margin: '0 auto 8px' }} />
                        Loading email breakdown...
                      </div>
                    ) : adminDetail?.error ? (
                      <div style={{ padding: 16, color: '#DC2626', fontSize: '0.8rem' }}>{adminDetail.error}</div>
                    ) : adminDetail?.emails?.length > 0 ? (
                      <div style={{ padding: '12px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                          <BarChart3 size={14} style={{ color: 'var(--text-muted)' }} />
                          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                            Per-Email Breakdown for {adm.username}
                          </span>
                        </div>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                              <th style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)' }}>Email</th>
                              <th style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600, color: 'var(--text-muted)' }}>Total</th>
                              <th style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600, color: '#D97706' }}>Spam</th>
                              <th style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600, color: '#DC2626' }}>Phishing</th>
                              <th style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600, color: '#7C3AED' }}>Malware</th>
                              <th style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600, color: '#059669' }}>Clean</th>
                            </tr>
                          </thead>
                          <tbody>
                            {adminDetail.emails.map((row) => (
                              <tr key={row.email} style={{ borderBottom: '1px solid var(--border)' }}>
                                <td style={{ padding: '6px 10px', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.7rem' }}>
                                  <span style={{
                                    display: 'inline-flex', alignItems: 'center', gap: 4,
                                    padding: '1px 6px', borderRadius: 10, fontSize: '0.65rem', fontWeight: 500,
                                    background: row.owner === 'admin' ? '#EEF2FF' : '#F0FDF4',
                                    color: row.owner === 'admin' ? '#4F46E5' : '#15803D',
                                  }}>
                                    {row.owner === 'admin' ? <Users size={9} /> : <Mail size={9} />}
                                    {row.email}
                                  </span>
                                </td>
                                <td style={{ padding: '6px 10px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.total}</td>
                                <td style={{ padding: '6px 10px', textAlign: 'right', color: '#D97706', fontVariantNumeric: 'tabular-nums' }}>{row.spam}</td>
                                <td style={{ padding: '6px 10px', textAlign: 'right', color: '#DC2626', fontVariantNumeric: 'tabular-nums' }}>{row.phishing}</td>
                                <td style={{ padding: '6px 10px', textAlign: 'right', color: '#7C3AED', fontVariantNumeric: 'tabular-nums' }}>{row.malware}</td>
                                <td style={{ padding: '6px 10px', textAlign: 'right', color: '#059669', fontVariantNumeric: 'tabular-nums' }}>{row.clean}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: '0.8rem', textAlign: 'center' }}>
                        No emails found for this admin.
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top Recipients Table */}
      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.rankCell}>#</th>
              <th>Recipient</th>
              <th>Type</th>
              <th style={{ textAlign: 'right' }}>Total</th>
              <th style={{ textAlign: 'right' }}>Spam</th>
              <th style={{ textAlign: 'right' }}>Phishing</th>
              <th style={{ textAlign: 'right' }}>Malware</th>
              <th style={{ textAlign: 'right' }}>Clean</th>
              <th>Distribution</th>
            </tr>
          </thead>
          <tbody>
            {pageResults.length === 0 ? (
              <tr>
                <td colSpan={9} className={styles.emptyState}>
                  <p>Tidak ada data untuk filter ini.</p>
                </td>
              </tr>
            ) : (
              pageResults.map((row, idx) => {
                const rank = page * perPage + idx + 1
                const barPct = Math.max((row.total / maxCount) * 100, 2)
                return (
                  <tr key={row.recipient} className={styles.trRow}>
                    <td className={styles.rankCell}>{rank}</td>
                    <td className={styles.recipientCell}>
                      <span className={styles.mono}>{row.recipient}</span>
                      {row.owner_username && (
                        <span style={{ marginLeft: 8, fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                          ({row.owner_username})
                        </span>
                      )}
                    </td>
                    <td>
                      <span className={`${styles.ownerBadge} ${row.owner_type === 'admin' ? styles.ownerAdmin : styles.ownerUser}`}>
                        {row.owner_type === 'admin' ? <Users size={11} /> : <Mail size={11} />}
                        {row.owner_type}
                      </span>
                    </td>
                    <td className={styles.numCell}>{row.total.toLocaleString()}</td>
                    <td className={styles.numCell} style={{ color: '#D97706' }}>{row.spam.toLocaleString()}</td>
                    <td className={styles.numCell} style={{ color: '#DC2626' }}>{row.phishing.toLocaleString()}</td>
                    <td className={styles.numCell} style={{ color: '#7C3AED' }}>{row.malware.toLocaleString()}</td>
                    <td className={styles.numCell} style={{ color: '#059669' }}>{row.clean.toLocaleString()}</td>
                    <td>
                      <div className={styles.barContainer}>
                        <div className={styles.barFill} style={{ width: `${barPct}%`, background: colorForCategory(category === 'all' ? 'spam' : category) }} />
                      </div>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>

        {totalPages > 1 && (
          <div className={styles.pagination}>
            <button className={styles.pageBtn} disabled={page === 0} onClick={() => setPage(p => p - 1)}>
              <ChevronLeft size={14} /> Prev
            </button>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Page {page + 1} of {totalPages}
            </span>
            <button className={styles.pageBtn} disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>
              Next <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
