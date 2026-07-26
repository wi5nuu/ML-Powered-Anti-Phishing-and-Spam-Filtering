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
  const [mailboxMode, setMailboxMode] = useState('all')
  const [mailboxes, setMailboxes] = useState([])
  const [selectedMailboxIds, setSelectedMailboxIds] = useState([])
  const [mailboxSearch, setMailboxSearch] = useState('')
  const [includeUsers, setIncludeUsers] = useState(true)
  const [includeEmails, setIncludeEmails] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    Promise.all([
      api.get('/admin/admins/list'),
      api.get('/admin/mailboxes'),
    ]).then(([adminResponse, mailboxResponse]) => {
      setAdmins(Array.isArray(adminResponse.data) ? adminResponse.data : (adminResponse.data?.admins || []))
      setMailboxes(Array.isArray(mailboxResponse.data) ? mailboxResponse.data : (mailboxResponse.data?.mailboxes || []))
    }).catch(() => {
      setAdmins([])
      setMailboxes([])
    })
    setFormat('pdf')
    setPeriod('all')
    setDateFrom('')
    setDateTo('')
    setAdminMode(isSuper ? 'all' : 'select')
    setSelectedAdminIds([])
    setAdminSearch('')
    setMailboxMode('all')
    setSelectedMailboxIds([])
    setMailboxSearch('')
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
    setSelectedAdminIds((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
      const allowedManagers = new Set(admins.filter((admin) => next.includes(admin.id)).map((admin) => admin.username))
      setSelectedMailboxIds((selected) => selected.filter((mailboxId) => {
        const mailbox = mailboxes.find((item) => item.id === mailboxId)
        return mailbox && allowedManagers.has(mailbox.assigned_to)
      }))
      return next
    })
  }

  const toggleMailbox = (id) => {
    setSelectedMailboxIds((prev) =>
      prev.includes(id) ? prev.filter((value) => value !== id) : [...prev, id]
    )
  }

  const filteredAdmins = admins.filter(
    (a) => a.username.toLowerCase().includes(adminSearch.toLowerCase())
  )
  const selectedAdminNames = new Set(
    admins.filter((admin) => selectedAdminIds.includes(admin.id)).map((admin) => admin.username)
  )
  const filteredMailboxes = mailboxes.filter((mailbox) => {
    if (adminMode === 'select' && selectedAdminIds.length > 0 && !selectedAdminNames.has(mailbox.assigned_to)) return false
    const needle = mailboxSearch.trim().toLowerCase()
    return !needle
      || (mailbox.email || '').toLowerCase().includes(needle)
      || (mailbox.sender_name || '').toLowerCase().includes(needle)
      || (mailbox.assigned_to || '').toLowerCase().includes(needle)
  })

  const handleGenerate = async () => {
    setError('')
    if (isSuper && adminMode === 'select' && selectedAdminIds.length === 0) {
      setError(t('export.selectAtLeastOneAdmin', 'Select at least one admin.'))
      return
    }
    if (mailboxMode === 'select' && selectedMailboxIds.length === 0) {
      setError(t('export.selectAtLeastOneMailbox', 'Pilih minimal satu email.'))
      return
    }
    setBusy(true)
    try {
      const payload = {
        format,
        date_from: period === 'all' ? null : dateFrom,
        date_to: period === 'all' ? null : dateTo,
        admin_ids: adminMode === 'all' ? null : selectedAdminIds,
        mailbox_ids: mailboxMode === 'all' ? null : selectedMailboxIds,
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
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Mailbox selection is available to both roles; the API scopes admins to assigned mailboxes. */}
        {(
          <div className={styles.field}>
            <label className={styles.label}>{t('export.mailboxes', 'Email pengguna')}</label>
            <div className={styles.radioGroup}>
              <label className={styles.radio}>
                <input type="radio" name="mailboxMode" value="all" checked={mailboxMode === 'all'} onChange={() => setMailboxMode('all')} />
                <span>{t('export.allMailboxes', 'Semua email')}</span>
              </label>
              <label className={styles.radio}>
                <input type="radio" name="mailboxMode" value="select" checked={mailboxMode === 'select'} onChange={() => setMailboxMode('select')} />
                <span>{t('export.selectMailboxes', 'Pilih email')}</span>
              </label>
            </div>
            {mailboxMode === 'select' && (
              <div className={styles.adminList}>
                <input
                  type="text"
                  className={styles.searchInput}
                  placeholder={t('export.searchMailbox', 'Cari alamat email, nama, atau admin...')}
                  value={mailboxSearch}
                  onChange={(event) => setMailboxSearch(event.target.value)}
                />
                <div className={styles.adminScroll}>
                  {filteredMailboxes.length === 0 && (
                    <div className={styles.noAdmin}>{t('export.noMailboxes', 'Email tidak ditemukan')}</div>
                  )}
                  {filteredMailboxes.map((mailbox) => (
                    <label key={mailbox.id} className={styles.adminRow}>
                      <input
                        type="checkbox"
                        checked={selectedMailboxIds.includes(mailbox.id)}
                        onChange={() => toggleMailbox(mailbox.id)}
                      />
                      <span className={styles.mailboxAddress}>{mailbox.email}</span>
                      <span className={styles.mailboxName}>{mailbox.sender_name || '-'}</span>
                      <span className={styles.adminEmail}>{mailbox.assigned_to || t('export.unassigned', 'Belum ditugaskan')}</span>
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
              <span>{t('export.includeEmails', 'Detail email (phishing, spam, peringatan, dan lainnya)')}</span>
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
