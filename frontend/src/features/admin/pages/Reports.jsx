import { useState, useEffect, useCallback } from 'react'
import api from '../../../api/client'
import SectionCard from '../../../components/ui/SectionCard'
import StatusBadge from '../../../components/ui/StatusBadge'
import { AlertCircle, Check, Reply, ChevronDown, ChevronUp, Flag, Activity } from 'lucide-react'
import styles from './Reports.module.css'

const CATEGORY_LABELS = { bug: 'Bug / Error', question: 'Pertanyaan', access: 'Akses', false_positive: 'False Positive', other: 'Lainnya' }
const CATEGORY_COLORS = { bug: '#ea4335', question: '#1a73e8', access: '#f29900', false_positive: '#34a853', other: '#5f6368' }
const PRIORITY_COLORS = { low: '#5f6368', normal: '#1a73e8', high: '#f29900', urgent: '#ea4335' }

export default function Reports() {
  const [reports, setReports] = useState([])
  const [filterCategory, setFilterCategory] = useState('all')
  const [expandedReport, setExpandedReport] = useState(null)
  const [replyText, setReplyText] = useState('')
  const [msg, setMsg] = useState('')

  const fetchReports = useCallback(async () => {
    try {
      const r = await api.get('/admin/reports')
      setReports(Array.isArray(r.data) ? r.data : [])
    } catch {}
  }, [])

  useEffect(() => { fetchReports() }, [fetchReports])

  const handleResolveReport = async (id) => {
    try {
      await api.put(`/admin/reports/${id}`, { status: 'resolved' })
      fetchReports()
    } catch { setMsg('Gagal update laporan') }
  }

  const handleReplyReport = async (id) => {
    if (!replyText.trim()) return
    try {
      await api.put(`/admin/reports/${id}`, { admin_reply: replyText.trim() })
      setReplyText('')
      setExpandedReport(null)
      fetchReports()
    } catch { setMsg('Gagal membalas laporan') }
  }

  const handleStatusChange = async (id, status) => {
    try {
      await api.put(`/admin/reports/${id}`, { status })
      fetchReports()
    } catch { setMsg('Gagal update status') }
  }

  const filteredReports = filterCategory === 'all' ? reports : reports.filter((r) => r.category === filterCategory)

  return (
    <div className={styles.page}>
      {msg && <div className={styles.msg}>{msg}</div>}

      <SectionCard
        icon={<AlertCircle size={16} />}
        title="Laporan & Bantuan User"
      >
        <div className={styles.filterBar}>
          {['all', 'question', 'bug', 'false_positive', 'access', 'other'].map((cat) => (
            <button
              key={cat}
              className={styles.filterChip}
              style={{
                background: filterCategory === cat ? (CATEGORY_COLORS[cat] || '#1a73e8') : 'transparent',
                color: filterCategory === cat ? '#fff' : 'var(--text-muted)'
              }}
              onClick={() => setFilterCategory(cat)}
            >
              {cat === 'all' ? 'Semua' : CATEGORY_LABELS[cat]}
            </button>
          ))}
        </div>

        {filteredReports.length === 0 ? (
          <div className={styles.emptyState}>Belum ada laporan dari user.</div>
        ) : (
          <div className={styles.reportList}>
            {filteredReports.map((r) => (
              <div key={r.id} className={styles.reportCard}>
                <div className={styles.reportCardHeader}>
                  <div className={styles.reportCardLeft}>
                    <strong>{r.username}</strong>
                    <span className={styles.reportCategory} style={{ background: CATEGORY_COLORS[r.category] || '#5f6368' }}>
                      {CATEGORY_LABELS[r.category] || r.category}
                    </span>
                    <span className={styles.reportPriority} style={{ color: PRIORITY_COLORS[r.priority] || '#5f6368' }}>
                      <Flag size={12} /> {r.priority}
                    </span>
                  </div>
                  <div className={styles.reportCardRight}>
                    <StatusBadge status={r.status} />
                    <button className={styles.expandBtn} onClick={() => setExpandedReport(expandedReport === r.id ? null : r.id)}>
                      {expandedReport === r.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                  </div>
                </div>
                <p className={styles.reportSubject}>{r.subject}</p>
                <p className={styles.reportMessage}>{r.message}</p>
                <div className={styles.reportFooter}>
                  <span className={styles.reportDate}>{r.created_at?.split('.')[0]}</span>
                  {r.status === 'open' && (
                    <button className={styles.resolveBtn} onClick={() => handleResolveReport(r.id)}>
                      <Check size={14} /> Selesai
                    </button>
                  )}
                </div>

                {expandedReport === r.id && (
                  <div className={styles.reportDetail}>
                    {r.admin_reply && (
                      <div className={styles.replyBubble}>
                        <strong style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Balasan Admin:</strong>
                        <p style={{ margin: '4px 0 0', fontSize: '0.8125rem', color: 'var(--text)' }}>{r.admin_reply}</p>
                      </div>
                    )}
                    <div className={styles.replyArea}>
                      <textarea
                        className={styles.replyInput}
                        placeholder="Tulis balasan untuk user ini..."
                        value={expandedReport === r.id ? replyText : ''}
                        onChange={(e) => setReplyText(e.target.value)}
                        rows={3}
                      />
                      <div className={styles.replyActions}>
                        <button className={styles.replySendBtn} onClick={() => handleReplyReport(r.id)} disabled={!replyText.trim()}>
                          <Reply size={14} /> Kirim Balasan
                        </button>
                        {r.status !== 'resolved' && (
                          <>
                            <button className={styles.actionSecBtn} onClick={() => handleStatusChange(r.id, 'in_progress')}>
                              <Activity size={14} /> Proses
                            </button>
                            <button className={styles.actionSecBtn} onClick={() => handleResolveReport(r.id)}>
                              <Check size={14} /> Selesai
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  )
}
