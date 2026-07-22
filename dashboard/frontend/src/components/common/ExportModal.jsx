import { useState, useEffect } from 'react'
import api from '../../api/client'
import { useTranslation } from '../../i18n/context'
import styles from './ExportModal.module.css'

export default function ExportModal({ open, onClose, userRole }) {
  const isSuper = userRole === 'superadmin'
  const { t } = useTranslation()
  const [format, setFormat] = useState('pdf')
  const [period, setPeriod] = useState('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [adminMode, setAdminMode] = useState('all')
  const [admins, setAdmins] = useState([])
  const [selectedAdminIds, setSelectedAdminIds] = useState([])
  const [adminSearch, setAdminSearch] = useState('')
  const [includeUsers, setIncludeUsers] = useState(true)
  const [includeEmails, setIncludeEmails] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    api.get('/admin/list-admins-with-stats').then((r) => {
      setAdmins(Array.isArray(r.data) ? r.data : (r.data?.admins || []))
    }).catch(() => setAdmins([]))
    setFormat('pdf')
    setPeriod('all')
    setDateFrom('')
    setDateTo('')
    setAdminMode(isSuper ? 'all' : 'select')
    setSelectedAdminIds([])
    setAdminSearch('')
    setIncludeUsers(true)
    setIncludeEmails(true)
    setError('')
    setBusy(false)
  }, [open, isSuper])

  const handlePeriodChange = (val) => {
    setPeriod(val)
    const now = new Date()
    const fmt = (d) => d.toISOString().slice(0, 10)
    if (val === 'today') {
      setDateFrom(fmt(now))
      setDateTo(fmt(now))
    } else if (val === 'week') {
      const start = new Date(now)
      start.setDate(start.getDate() - start.getDay())
      setDateFrom(fmt(start))
      setDateTo(fmt(now))
    } else if (val === 'month') {
      const start = new Date(now.getFullYear(), now.getMonth(), 1)
      setDateFrom(fmt(start))
      setDateTo(fmt(now))
    } else {
      setDateFrom('')
      setDateTo('')
    }
  }

  const toggleAdmin = (id) => {
    setSelectedAdminIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    )
  }

  const filteredAdmins = admins.filter(
    (a) => a.username.toLowerCase().includes(adminSearch.toLowerCase())
  )

  const handleGenerate = async () => {
    setError('')
    setBusy(true)
    try {
      const payload = {
        format,
        date_from: period === 'all' ? null : dateFrom,
        date_to: period === 'all' ? null : dateTo,
        admin_ids: adminMode === 'all' ? null : selectedAdminIds,
        include_users: includeUsers,
        include_emails: includeEmails,
      }
      const r = await api.post('/admin/export/generate', payload, {
        responseType: 'blob',
        headers: { 'Content-Type': 'application/json' },
      })
      const ext = format === 'pdf' ? 'pdf' : 'xlsx'
      const mime = format === 'pdf'
        ? 'application/pdf'
        : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      const blob = new Blob([r.data], { type: mime })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `cognimail_report_${new Date().toISOString().slice(0, 10)}.${ext}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 5000)
      onClose()
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Unknown error'
      try {
        const text = await (err.response?.data || new Blob()).text()
        const json = JSON.parse(text)
        setError(json.detail || detail)
      } catch {
        setError(detail)
      }
    } finally {
      setBusy(false)
    }
  }

  if (!open) return null

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <h2>{t('export.title', 'Generate Report')}</h2>

        {/* Format */}
        <div className={styles.field}>
          <label className={styles.label}>{t('export.format', 'Format')}</label>
          <div className={styles.radioGroup}>
            <label className={styles.radio}>
              <input type="radio" name="format" value="pdf" checked={format === 'pdf'} onChange={() => setFormat('pdf')} />
              <span>PDF</span>
            </label>
            <label className={styles.radio}>
              <input type="radio" name="format" value="excel" checked={format === 'excel'} onChange={() => setFormat('excel')} />
              <span>Excel</span>
            </label>
          </div>
        </div>

        {/* Period */}
        <div className={styles.field}>
          <label className={styles.label}>{t('export.period', 'Period')}</label>
          <div className={styles.periodGrid}>
            {['all', 'today', 'week', 'month', 'custom'].map((p) => (
              <button
                key={p}
                className={`${styles.periodBtn} ${period === p ? styles.periodActive : ''}`}
                onClick={() => handlePeriodChange(p)}
              >
                {t(`export.period${p.charAt(0).toUpperCase() + p.slice(1)}`, p)}
              </button>
            ))}
          </div>
          {(period === 'custom' || period === 'today' || period === 'week' || period === 'month') && (
            <div className={styles.dateRow}>
              <input type="date" className={styles.dateInput} value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)} />
              <span className={styles.dateSep}>{t('export.to', 'to')}</span>
              <input type="date" className={styles.dateInput} value={dateTo}
                onChange={(e) => setDateTo(e.target.value)} />
            </div>
          )}
        </div>

        {/* Admin Selection (superadmin only) */}
        {isSuper && (
          <div className={styles.field}>
            <label className={styles.label}>{t('export.admins', 'Admins')}</label>
            <div className={styles.radioGroup}>
              <label className={styles.radio}>
                <input type="radio" name="adminMode" value="all" checked={adminMode === 'all'} onChange={() => setAdminMode('all')} />
                <span>{t('export.allAdmins', 'All Admins')}</span>
              </label>
              <label className={styles.radio}>
                <input type="radio" name="adminMode" value="select" checked={adminMode === 'select'} onChange={() => setAdminMode('select')} />
                <span>{t('export.selectAdmins', 'Select Admins')}</span>
              </label>
            </div>
            {adminMode === 'select' && (
              <div className={styles.adminList}>
                <input type="text" className={styles.searchInput} placeholder={t('export.searchAdmin', 'Search admin...')}
                  value={adminSearch} onChange={(e) => setAdminSearch(e.target.value)} />
                <div className={styles.adminScroll}>
                  {filteredAdmins.length === 0 && (
                    <div className={styles.noAdmin}>{t('export.noAdmins', 'No admins found')}</div>
                  )}
                  {filteredAdmins.map((a) => (
                    <label key={a.id} className={styles.adminRow}>
                      <input type="checkbox" checked={selectedAdminIds.includes(a.id)}
                        onChange={() => toggleAdmin(a.id)} />
                      <span className={styles.adminName}>{a.username}</span>
                      <span className={styles.adminRole}>{a.role}</span>
                      <span className={styles.adminEmail}>{a.email || ''}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Include options */}
        <div className={styles.field}>
          <label className={styles.label}>{t('export.include', 'Include')}</label>
          <div className={styles.checkGroup}>
            <label className={styles.check}>
              <input type="checkbox" checked={includeUsers} onChange={(e) => setIncludeUsers(e.target.checked)} />
              <span>{t('export.includeUsers', 'User details & stats')}</span>
            </label>
            <label className={styles.check}>
              <input type="checkbox" checked={includeEmails} onChange={(e) => setIncludeEmails(e.target.checked)} />
              <span>{t('export.includeEmails', 'Email details (phishing, spam, malware, etc.)')}</span>
            </label>
          </div>
        </div>

        {error && <div className={styles.error}>{error}</div>}

        {/* Actions */}
        <div className={styles.actions}>
          <button className={styles.cancelBtn} onClick={onClose} disabled={busy}>
            {t('export.cancel', 'Cancel')}
          </button>
          <button className={styles.generateBtn} onClick={handleGenerate} disabled={busy}>
            {busy ? t('export.generating', 'Generating...') : t('export.generate', 'Generate Report')}
          </button>
        </div>
      </div>
    </div>
  )
}