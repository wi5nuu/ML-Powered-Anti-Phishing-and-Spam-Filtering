import { useEffect, useState } from 'react'
import api from '../api/client'
import { useTranslation } from '../i18n/context'
import {
  TrendingUp, RefreshCw, AlertCircle, Search, X,
  Users, ShieldAlert, AlertTriangle, CheckCircle, ChevronUp, ChevronDown
} from 'lucide-react'
import styles from './AdminPage.module.css'

const ROLE_COLORS = {
  superadmin: { bg: '#F3E8FF', color: '#7C3AED' },
  admin:      { bg: '#EFF6FF', color: '#2563EB' },
  user:       { bg: '#F0FDF4', color: '#16A34A' },
}

const SCORE_COLOR = (s) => s >= 80 ? '#DC2626' : s >= 50 ? '#D97706' : s >= 20 ? '#2563EB' : '#16A34A'
const SCORE_BG    = (s) => s >= 80 ? '#FEF2F2' : s >= 50 ? '#FFFBEB' : s >= 20 ? '#EFF6FF' : '#F0FDF4'

function ScoreBadge({ score }) {
  return (
    <span style={{
      display: 'inline-block', padding: '1px 9px', borderRadius: 99,
      fontSize: '0.75rem', fontWeight: 700,
      background: SCORE_BG(score), color: SCORE_COLOR(score),
    }}>
      {score}
    </span>
  )
}

function MiniBar({ value, max, color }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 56, height: 5, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', minWidth: 20 }}>{value}</span>
    </div>
  )
}

function UserDetailModal({ username, onClose }) {
  const { t } = useTranslation()
  const [detail,  setDetail]  = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')

  useEffect(() => {
    api.get(`/admin/user-detail/${username}`)
      .then(({ data }) => setDetail(data))
      .catch((e) => setError(e.response?.data?.detail || t('analytics.userDetail.loadError')))
      .finally(() => setLoading(false))
  }, [username])

  const CAT_COLOR = {
    phishing: { bg: '#fce8e6', text: '#c5221f' },
    spam:     { bg: '#fef3cd', text: '#856404' },
    malware:  { bg: '#f3e5f5', text: '#6a1b9a' },
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.editModal} style={{ maxWidth: 820, width: '92%', maxHeight: '90vh', overflowY: 'auto' }} onClick={(e) => e.stopPropagation()}>
        <div className={styles.editModalHeader}>
          <h3><Users size={16} />{t('analytics.userDetail.title')} — {username}</h3>
          <button className={styles.modalCloseBtn} onClick={onClose}><X size={16} /></button>
        </div>

        <div className={styles.editModalBody}>
          {loading && <div className={styles.emptySmall}>{t('analytics.userDetail.loading')}</div>}
          {error && (
            <div style={{ padding: '8px 12px', background: '#fce8e6', color: '#c5221f', borderRadius: 6, fontSize: '0.8125rem', display: 'flex', alignItems: 'center', gap: 8 }}>
              <AlertCircle size={13} /> {error}
            </div>
          )}

          {detail && (
            <>
              {/* Info + stats row */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 20 }}>
                <div style={{ background: 'var(--surface-alt, #f8f9fa)', borderRadius: 8, padding: '12px 14px', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8 }}>{t('analytics.userDetail.userInfo')}</div>
                  {[
                    [t('users.email'), detail.user.email],
                    [t('users.role'), <span className={styles.roleBadge} style={{ background: ROLE_COLORS[detail.user.role]?.bg, color: ROLE_COLORS[detail.user.role]?.color }}>{detail.user.role}</span>],
                    [t('users.status'), <span style={{ color: detail.user.is_active ? '#16a34a' : '#dc2626', fontWeight: 600 }}>{detail.user.is_active ? t('users.active') : t('users.inactive')}</span>],
                  ].map(([k, v]) => (
                    <div key={k} style={{ fontSize: '0.8125rem', marginBottom: 4 }}>
                      <span style={{ color: 'var(--text-muted)' }}>{k}: </span>{v}
                    </div>
                  ))}
                </div>
                <div style={{ background: 'var(--surface-alt, #f8f9fa)', borderRadius: 8, padding: '12px 14px', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8 }}>{t('analytics.userDetail.threatStats')}</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
                    {[
                      [t('analytics.userDetail.totalEmail'),  detail.stats.total_emails, 'var(--text)'],
                      [t('analytics.userDetail.threatScore'), <ScoreBadge score={detail.stats.threat_score} />, null],
                      [t('analytics.userDetail.phishing'),     detail.stats.phishing, '#c5221f'],
                      [t('analytics.userDetail.spam'),         detail.stats.spam, '#856404'],
                      [t('analytics.userDetail.malware'),      detail.stats.malware, '#6a1b9a'],
                      [t('analytics.userDetail.quarantined'),  detail.stats.quarantined, '#ea4335'],
                    ].map(([k, v, color]) => (
                      <div key={k} style={{ fontSize: '0.8125rem' }}>
                        <span style={{ color: 'var(--text-muted)' }}>{k}: </span>
                        <span style={{ fontWeight: 600, color: color || 'inherit' }}>{v}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Top senders */}
              {detail.top_senders?.length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text)', marginBottom: 8 }}>{t('analytics.userDetail.topSenders')}</div>
                  <table className={styles.table} style={{ margin: 0 }}>
                    <thead>
                      <tr>
                        <th>{t('analytics.userDetail.sender')}</th>
                        <th style={{ textAlign: 'right' }}>{t('analytics.userDetail.total')}</th>
                        <th style={{ textAlign: 'right', color: '#c5221f' }}>{t('analytics.userDetail.phishing')}</th>
                        <th style={{ textAlign: 'right', color: '#856404' }}>{t('analytics.userDetail.spam')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.top_senders.map((s, i) => (
                        <tr key={i}>
                          <td className={styles.mono} style={{ fontSize: '0.75rem' }}>{s.sender}</td>
                          <td style={{ textAlign: 'right', fontWeight: 600 }}>{s.count}</td>
                          <td style={{ textAlign: 'right', color: '#c5221f' }}>{s.phishing}</td>
                          <td style={{ textAlign: 'right', color: '#856404' }}>{s.spam}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Recent threats */}
              {detail.recent_threats?.length > 0 ? (
                <div>
                  <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text)', marginBottom: 8 }}>{t('analytics.userDetail.recentThreats')}</div>
                  <table className={styles.table} style={{ margin: 0 }}>
                    <thead>
                      <tr>
                        <th>{t('common.subject')}</th>
                        <th>{t('common.sender')}</th>
                        <th style={{ textAlign: 'center' }}>{t('common.category')}</th>
                        <th style={{ textAlign: 'center' }}>{t('common.label')}</th>
                        <th style={{ textAlign: 'right' }}>{t('common.score')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.recent_threats.map((e) => {
                        const cc = CAT_COLOR[e.category] || { bg: '#f1f3f4', text: '#5f6368' }
                        return (
                          <tr key={e.id}>
                            <td style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={e.subject}>
                              {e.subject || <span style={{ color: 'var(--text-muted)' }}>{t('common.noSubject')}</span>}
                            </td>
                            <td className={styles.mono} style={{ fontSize: '0.7rem' }}>{e.sender}</td>
                            <td style={{ textAlign: 'center' }}>
                              <span className={styles.categoryBadge} style={{ background: cc.bg, color: cc.text }}>{e.category}</span>
                            </td>
                            <td style={{ textAlign: 'center' }}>
                              <span style={{ fontSize: '0.7rem', fontWeight: 600, color: e.label === 'QUARANTINE' ? '#c5221f' : e.label === 'WARN' ? '#856404' : '#137333' }}>
                                {e.label}
                              </span>
                            </td>
                            <td className={styles.mono} style={{ textAlign: 'right' }}>
                              {e.score != null ? Number(e.score).toFixed(3) : t('common.na')}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className={styles.emptySmall} style={{ color: '#16a34a' }}>
                  <CheckCircle size={16} style={{ marginRight: 6 }} />
                  {t('analytics.userDetail.noThreats')}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function SuperadminUserAnalytics() {
  const { t } = useTranslation()
  const [users,       setUsers]       = useState([])
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState('')
  const [search,      setSearch]      = useState('')
  const [roleFilter,  setRoleFilter]  = useState('all')
  const [sortKey,     setSortKey]     = useState('threat_score')
  const [sortDir,     setSortDir]     = useState('desc')
  const [selected,    setSelected]    = useState(null)

  const fetchUsers = () => {
    setLoading(true); setError('')
    api.get('/admin/user-analytics')
      .then(({ data }) => { setUsers(Array.isArray(data) ? data : []) })
      .catch((e) => { setError(e.response?.data?.detail || t('analytics.loadError')) }) // BUGFIX: Removed console.error from production
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchUsers() }, [])

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const filtered = users
    .filter((u) => {
      const q = search.toLowerCase()
      if (q && !u.username.toLowerCase().includes(q) && !(u.email || '').toLowerCase().includes(q)) return false
      if (roleFilter !== 'all' && u.role !== roleFilter) return false
      return true
    })
    .sort((a, b) => {
      const va = a[sortKey] ?? 0, vb = b[sortKey] ?? 0
      if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
      return sortDir === 'asc' ? va - vb : vb - va
    })

  const maxTotal     = Math.max(...users.map(u => u.total_emails), 1)
  const totalThreats = users.reduce((s, u) => s + (u.phishing || 0) + (u.spam || 0) + (u.malware || 0), 0)
  const highRisk     = users.filter(u => u.threat_score >= 50).length

  const SortIcon = ({ col }) => sortKey !== col
    ? <ChevronDown size={11} style={{ opacity: 0.3 }} />
    : sortDir === 'asc' ? <ChevronUp size={11} /> : <ChevronDown size={11} />

  return (
    <div style={{ padding: '0 0 24px' }}>
      <div className={styles.section}>
        {/* Header */}
        <div className={styles.sectionHeader}>
          <div className={styles.sectionTitle}>
            <TrendingUp size={16} />
            <div>
              <strong>{t('analytics.title')}</strong>
              <span>{t('analytics.subtitle')}</span>
            </div>
          </div>
          <button onClick={fetchUsers} disabled={loading} className={styles.actionBtn}>
            <RefreshCw size={13} />
          </button>
        </div>

        {error && (
          <div style={{ padding: '10px 16px', background: '#fce8e6', color: '#c5221f', fontSize: '0.8125rem', display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {/* Summary cards */}
        {!loading && users.length > 0 && (
          <div className={styles.statsGrid6} style={{ padding: '16px 20px 0' }}>
            {[
              { label: t('analytics.summary.totalUsers'),   value: users.length,            icon: <Users size={16} />,        iconBg: '#EFF6FF', iconColor: '#2563EB' },
              { label: t('analytics.summary.totalThreats'), value: totalThreats,            icon: <ShieldAlert size={16} />,  iconBg: '#FEF2F2', iconColor: '#DC2626' },
              { label: t('analytics.summary.highRisk'),     value: highRisk,                icon: <AlertTriangle size={16} />,iconBg: '#FFFBEB', iconColor: '#D97706' },
              { label: t('analytics.summary.safe'),          value: users.filter(u => u.threat_score < 20).length, icon: <CheckCircle size={16} />, iconBg: '#F0FDF4', iconColor: '#16A34A' },
            ].map((item) => (
              <div key={item.label} className={styles.statCard2}>
                <div className={styles.sc2Icon} style={{ background: item.iconBg, color: item.iconColor }}>
                  {item.icon}
                </div>
                <div className={styles.sc2Body}>
                  <span className={styles.sc2Value}>{item.value}</span>
                  <span className={styles.sc2Label}>{item.label}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Filters */}
        <div className={styles.filterBar}>
          <div className={styles.searchForm}>
            <Search size={13} className={styles.searchIcon} />
            <input
              className={styles.searchInput}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('analytics.searchPlaceholder')}
            />
            {search && (
              <button type="button" onClick={() => setSearch('')} className={styles.clearBtn}>
                <X size={12} />
              </button>
            )}
          </div>
          <select className={styles.filterSelect} value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
            <option value="all">{t('analytics.roleAll')}</option>
            <option value="user">{t('label.user')}</option>
            <option value="admin">{t('label.admin')}</option>
            <option value="superadmin">{t('label.superadmin')}</option>
          </select>
        </div>

        {loading ? (
          <div className={styles.emptyState}>{t('analytics.loading')}</div>
        ) : (
          <>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th style={{ cursor: 'pointer' }} onClick={() => handleSort('username')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>{t('analytics.table.username')} <SortIcon col="username" /></span>
                  </th>
                  <th style={{ cursor: 'pointer', textAlign: 'center' }} onClick={() => handleSort('role')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 3, justifyContent: 'center' }}>{t('analytics.table.role')} <SortIcon col="role" /></span>
                  </th>
                  <th style={{ cursor: 'pointer' }} onClick={() => handleSort('total_emails')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>{t('analytics.table.totalEmail')} <SortIcon col="total_emails" /></span>
                  </th>
                  <th style={{ cursor: 'pointer', color: '#c5221f' }} onClick={() => handleSort('phishing')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>{t('analytics.table.phishing')} <SortIcon col="phishing" /></span>
                  </th>
                  <th style={{ cursor: 'pointer', color: '#856404' }} onClick={() => handleSort('spam')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>{t('analytics.table.spam')} <SortIcon col="spam" /></span>
                  </th>
                  <th style={{ cursor: 'pointer', color: '#6a1b9a' }} onClick={() => handleSort('malware')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>{t('analytics.table.malware')} <SortIcon col="malware" /></span>
                  </th>
                  <th style={{ cursor: 'pointer' }} onClick={() => handleSort('quarantined')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>{t('analytics.table.quarantined')} <SortIcon col="quarantined" /></span>
                  </th>
                  <th style={{ cursor: 'pointer', textAlign: 'center' }} onClick={() => handleSort('threat_score')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 3, justifyContent: 'center' }}>{t('analytics.table.score')} <SortIcon col="threat_score" /></span>
                  </th>
                  <th style={{ cursor: 'pointer', textAlign: 'right' }} onClick={() => handleSort('last_threat')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 3, justifyContent: 'flex-end' }}>{t('analytics.table.lastThreat')} <SortIcon col="last_threat" /></span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={9} style={{ textAlign: 'center', padding: '28px 16px', color: 'var(--text-muted)' }}>
                      {search || roleFilter !== 'all' ? t('analytics.noMatch') : t('analytics.noData')}
                    </td>
                  </tr>
                ) : filtered.map((u) => {
                  const rc = ROLE_COLORS[u.role] || ROLE_COLORS.user
                  return (
                    <tr key={u.username} style={{ cursor: 'pointer' }} onClick={() => setSelected(u.username)}>
                      <td>
                        <div className={styles.usernameCell}>{u.username}</div>
                        <div className={styles.mono} style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{u.email}</div>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span className={styles.roleBadge} style={{ background: rc.bg, color: rc.color }}>{u.role}</span>
                      </td>
                      <td><MiniBar value={u.total_emails} max={maxTotal} color="#1a73e8" /></td>
                      <td style={{ color: u.phishing > 0 ? '#c5221f' : 'var(--text-muted)', fontWeight: u.phishing > 0 ? 700 : 400 }}>{u.phishing}</td>
                      <td style={{ color: u.spam > 0 ? '#856404' : 'var(--text-muted)', fontWeight: u.spam > 0 ? 700 : 400 }}>{u.spam}</td>
                      <td style={{ color: u.malware > 0 ? '#6a1b9a' : 'var(--text-muted)', fontWeight: u.malware > 0 ? 700 : 400 }}>{u.malware}</td>
                      <td style={{ color: u.quarantined > 0 ? '#ea4335' : 'var(--text-muted)', fontWeight: u.quarantined > 0 ? 600 : 400 }}>{u.quarantined}</td>
                      <td style={{ textAlign: 'center' }}><ScoreBadge score={u.threat_score} /></td>
                      <td className={styles.mono} style={{ textAlign: 'right', fontSize: '0.75rem' }}>{u.last_threat || t('common.na')}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {filtered.length > 0 && (
              <div style={{ padding: '8px 16px', fontSize: '0.75rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border)' }}>
                {t('analytics.table.showing').replace('{count}', filtered.length).replace('{total}', users.length)}
              </div>
            )}
          </>
        )}
      </div>

      {selected && <UserDetailModal username={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
