import { useState } from 'react'
import api from '../api/client'
import {
  FileText, Download, FileSpreadsheet, FileBarChart,
  Loader2, CheckCircle2, XCircle, AlertCircle, Clock,
  Users, Mail, Shield, Activity, DownloadCloud, Eye, Filter
} from 'lucide-react'
import styles from './SuperadminReports.module.css'

const SCOPE_LABELS = { all: 'All Data', admin: 'Admin Emails Only', user: 'User Emails Only' }

export default function SuperadminReports() {
  const [loading, setLoading] = useState(null)
  const [msg, setMsg] = useState('')
  const [msgType, setMsgType] = useState('success')
  const [preview, setPreview] = useState(null)
  const [previewData, setPreviewData] = useState(null)
  const [reportScope, setReportScope] = useState('all')

  const showMsg = (text, type = 'success') => {
    setMsg(text); setMsgType(type)
    setTimeout(() => setMsg(''), 6000)
  }

  const downloadPDF = async () => {
    setLoading('pdf')
    try {
      const response = await api.get('/admin/export-report/pdf', {
        params: { scope: reportScope },
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }))
      const link = document.createElement('a')
      link.href = url
      const date = new Date().toISOString().slice(0, 10)
      const scopeSuffix = reportScope !== 'all' ? `_${reportScope}` : ''
      link.setAttribute('download', `cognimail_report${scopeSuffix}_${date}.pdf`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      showMsg('Laporan PDF berhasil diunduh')
    } catch (e) {
      showMsg('Gagal mengunduh PDF: ' + (e.response?.data?.detail || e.message), 'error')
    } finally {
      setLoading(null)
    }
  }

  const downloadExcel = async () => {
    setLoading('excel')
    try {
      const response = await api.get('/admin/export-report/excel', {
        params: { scope: reportScope },
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }))
      const link = document.createElement('a')
      link.href = url
      const date = new Date().toISOString().slice(0, 10)
      link.setAttribute('download', `cognimail_report_${date}.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      showMsg('Laporan CSV/Excel berhasil diunduh')
    } catch (e) {
      showMsg('Gagal mengunduh CSV: ' + (e.response?.data?.detail || e.message), 'error')
    } finally {
      setLoading(null)
    }
  }

  const downloadEmailCsv = async (label) => {
    setLoading('emailCsv')
    try {
      const params = label && label !== 'all' ? { label } : {}
      const response = await api.get('/emails/export-csv', {
        params,
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }))
      const link = document.createElement('a')
      link.href = url
      const date = new Date().toISOString().slice(0, 10)
      const labelSuffix = label && label !== 'all' ? `_${label}` : ''
      link.setAttribute('download', `cognimail_emails${labelSuffix}_${date}.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      showMsg('Email CSV berhasil diunduh')
    } catch (e) {
      showMsg('Gagal mengunduh CSV email', 'error')
    } finally {
      setLoading(null)
    }
  }

  const fetchPreview = async (type) => {
    setPreview(type)
    try {
      const r = await api.get('/admin/superadmin-dashboard')
      setPreviewData(r.data)
    } catch (e) {
      showMsg('Gagal memuat data preview', 'error')
      setPreview(null)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}><FileBarChart size={22} /> Generate Reports</h1>
          <p className={styles.subtitle}>Generate and download comprehensive security reports in PDF or CSV/Excel format.</p>
        </div>
      </div>

      {msg && (
        <div className={`${styles.msg} ${msgType === 'error' ? styles.msgError : styles.msgSuccess}`}>
          {msgType === 'error' ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
          <span>{msg}</span>
        </div>
      )}

      {/* Scope Filter */}
      <div className={styles.filterBar}>
        <div className={styles.filterGroup}>
          <Filter size={14} />
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>Scope:</span>
          {['all', 'admin', 'user'].map((s) => (
            <button
              key={s}
              className={`${styles.scopeBtn} ${reportScope === s ? styles.scopeBtnActive : ''}`}
              onClick={() => setReportScope(s)}
            >
              {SCOPE_LABELS[s]}
            </button>
          ))}
        </div>
        <div className={styles.filterGroup}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Report akan berisi: <strong>{SCOPE_LABELS[reportScope]}</strong>
          </span>
        </div>
      </div>

      <div className={styles.grid}>
        <div className={styles.reportCard}>
          <div className={styles.reportIcon} style={{ background: '#FEF2F2', color: '#DC2626' }}>
            <FileText size={28} />
          </div>
          <h3 className={styles.reportTitle}>PDF Security Report</h3>
          <p className={styles.reportDesc}>
            Comprehensive PDF report including executive summary, threat breakdown,
            organization stats, admin overview, and recent system activities with IP addresses.
          </p>
          <div className={styles.reportMeta}>
            <span><Clock size={13} /> Real-time data</span>
            <span><FileText size={13} /> PDF format</span>
          </div>
          <div className={styles.reportActions}>
            <button
              className={styles.primaryBtn}
              onClick={downloadPDF}
              disabled={loading === 'pdf'}
            >
              {loading === 'pdf' ? <Loader2 size={16} className={styles.spin} /> : <DownloadCloud size={16} />}
              {loading === 'pdf' ? 'Generating...' : 'Download PDF'}
            </button>
            <button className={styles.previewBtn} onClick={() => fetchPreview('pdf')}>
              <Eye size={14} /> Preview
            </button>
          </div>
        </div>

        <div className={styles.reportCard}>
          <div className={styles.reportIcon} style={{ background: '#ECFDF5', color: '#059669' }}>
            <FileSpreadsheet size={28} />
          </div>
          <h3 className={styles.reportTitle}>CSV / Excel Report</h3>
          <p className={styles.reportDesc}>
            Full data export with per-user email breakdown, threat counts by category,
            and recent activity logs with IP addresses and timestamps.
          </p>
          <div className={styles.reportMeta}>
            <span><Clock size={13} /> Real-time data</span>
            <span><FileSpreadsheet size={13} /> CSV format</span>
          </div>
          <div className={styles.reportActions}>
            <button
              className={styles.primaryBtn}
              onClick={downloadExcel}
              disabled={loading === 'excel'}
            >
              {loading === 'excel' ? <Loader2 size={16} className={styles.spin} /> : <DownloadCloud size={16} />}
              {loading === 'excel' ? 'Generating...' : 'Download CSV/Excel'}
            </button>
          </div>
        </div>

        <div className={styles.reportCard}>
          <div className={styles.reportIcon} style={{ background: '#EFF6FF', color: '#2563EB' }}>
            <Mail size={28} />
          </div>
          <h3 className={styles.reportTitle}>Email Log Export</h3>
          <p className={styles.reportDesc}>
            Export raw email processing logs with all detection scores, labels,
            routing decisions, and timestamps. Filterable by threat category.
          </p>
          <div className={styles.reportMeta}>
            <span><Clock size={13} /> Up to 5000 records</span>
            <span><FileSpreadsheet size={13} /> CSV format</span>
          </div>
          <div className={styles.reportFilterRow}>
            {['all', 'CLEAN', 'WARN', 'QUARANTINE'].map((lbl) => (
              <button
                key={lbl}
                className={styles.filterChip}
                onClick={() => downloadEmailCsv(lbl === 'all' ? 'all' : lbl)}
                disabled={loading === 'emailCsv'}
              >
                {loading === 'emailCsv' ? <Loader2 size={12} className={styles.spin} /> : <Download size={12} />}
                {lbl === 'all' ? 'All Emails' : lbl}
              </button>
            ))}
          </div>
        </div>
      </div>

      {preview && previewData && (
        <div className={styles.previewSection}>
          <div className={styles.previewHeader}>
            <h2><Eye size={18} /> Dashboard Preview</h2>
            <button className={styles.closeBtn} onClick={() => setPreview(null)}>Close</button>
          </div>
          <div className={styles.previewGrid}>
            <div className={styles.previewItem}>
              <span className={styles.previewLabel}>Total Users</span>
              <span className={styles.previewValue}>{previewData.total_users}</span>
            </div>
            <div className={styles.previewItem}>
              <span className={styles.previewLabel}>Active Users</span>
              <span className={styles.previewValue}>{previewData.active_users}</span>
            </div>
            <div className={styles.previewItem}>
              <span className={styles.previewLabel}>Total Admins</span>
              <span className={styles.previewValue}>{previewData.total_admins}</span>
            </div>
            <div className={styles.previewItem}>
              <span className={styles.previewLabel}>Mailboxes</span>
              <span className={styles.previewValue}>{previewData.total_mailboxes}</span>
            </div>
            <div className={styles.previewItem}>
              <span className={styles.previewLabel}>Emails Processed</span>
              <span className={styles.previewValue}>{previewData.total_emails_processed}</span>
            </div>
            <div className={styles.previewItem}>
              <span className={styles.previewLabel}>Clean</span>
              <span className={styles.previewValue} style={{ color: '#059669' }}>{previewData.total_clean}</span>
            </div>
            <div className={styles.previewItem}>
              <span className={styles.previewLabel}>Spam</span>
              <span className={styles.previewValue} style={{ color: '#D97706' }}>{previewData.total_spam}</span>
            </div>
            <div className={styles.previewItem}>
              <span className={styles.previewLabel}>Phishing</span>
              <span className={styles.previewValue} style={{ color: '#DC2626' }}>{previewData.total_phishing}</span>
            </div>
            <div className={styles.previewItem}>
              <span className={styles.previewLabel}>Malware</span>
              <span className={styles.previewValue} style={{ color: '#7C3AED' }}>{previewData.total_malware}</span>
            </div>
            <div className={styles.previewItem}>
              <span className={styles.previewLabel}>Quarantined</span>
              <span className={styles.previewValue} style={{ color: '#991B1B' }}>{previewData.total_quarantined}</span>
            </div>
          </div>
        </div>
      )}

      <div className={styles.infoCard}>
        <div className={styles.infoIcon}><Shield size={20} /></div>
        <div className={styles.infoBody}>
          <strong>Reports contain the following data:</strong>
          <ul>
            <li><Users size={14} /> User and admin hierarchy with email statistics per user</li>
            <li><Shield size={14} /> Threat breakdown: Spam, Phishing, Malware detection counts</li>
            <li><Activity size={14} /> Recent system activities with IP addresses and timestamps</li>
            <li><Mail size={14} /> Per-mailbox storage and email processing stats</li>
            <li>Organization-level email traffic summary</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
