import { useState, useEffect } from 'react'
import api from '../api/client'
import {
  Building2, Plus, X, Check, Edit3, Trash2, Users, Mail,
  Shield, Search, AlertCircle, CheckCircle2, Building
} from 'lucide-react'
import styles from './SuperadminCompanies.module.css'

export default function SuperadminCompanies() {
  const [orgs, setOrgs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [msg, setMsg] = useState('')
  const [msgType, setMsgType] = useState('success')
  const [showForm, setShowForm] = useState(false)
  const [editOrg, setEditOrg] = useState(null)
  const [formName, setFormName] = useState('')
  const [formDomain, setFormDomain] = useState('')
  const [searchTerm, setSearchTerm] = useState('')

  const showMsg = (text, type = 'success') => {
    setMsg(text); setMsgType(type)
    setTimeout(() => setMsg(''), 5000)
  }

  const fetchOrgs = async () => {
    setLoading(true)
    try {
      const r = await api.get('/admin/organizations')
      setOrgs(Array.isArray(r.data?.organizations) ? r.data.organizations : [])
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    }
    setLoading(false)
  }

  useEffect(() => { fetchOrgs() }, [])

  const openCreate = () => {
    setEditOrg(null)
    setFormName('')
    setFormDomain('')
    setShowForm(true)
  }

  const openEdit = (org) => {
    setEditOrg(org)
    setFormName(org.name)
    setFormDomain(org.config?.domain || '')
    setShowForm(true)
  }

  const handleSave = async () => {
    if (!formName.trim()) { showMsg('Nama perusahaan harus diisi', 'error'); return }
    try {
      if (editOrg) {
        await api.put(`/admin/organizations/${editOrg.id}`, { name: formName.trim(), domain: formDomain.trim() })
        showMsg(`Perusahaan "${formName}" diperbarui`)
      } else {
        await api.post('/admin/organizations', { name: formName.trim(), domain: formDomain.trim() })
        showMsg(`Perusahaan "${formName}" dibuat`)
      }
      setShowForm(false)
      setEditOrg(null)
      fetchOrgs()
    } catch (err) {
      showMsg(err.response?.data?.detail || 'Gagal menyimpan perusahaan', 'error')
    }
  }

  const handleDelete = async (org) => {
    if (!window.confirm(`Hapus perusahaan "${org.name}"? Semua data akan terlepas.`)) return
    try {
      await api.delete(`/admin/organizations/${org.id}`)
      showMsg(`Perusahaan "${org.name}" dihapus`)
      fetchOrgs()
    } catch (err) {
      showMsg(err.response?.data?.detail || 'Gagal menghapus perusahaan', 'error')
    }
  }

  const filtered = orgs.filter(o =>
    o.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    o.admins?.some(a => a.username.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  if (loading && orgs.length === 0) {
    return (
      <div className={styles.page}>
        <div className={styles.loadingState}>
          <div className={styles.spinner} />
          <span>Memuat perusahaan...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.page}>
        <div className={styles.errorState}>
          <X size={32} />
          <h3>Gagal Memuat Data</h3>
          <p>{error}</p>
          <button className={styles.retryBtn} onClick={fetchOrgs}>Coba Lagi</button>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}><Building2 size={22} /> Companies</h1>
          <p className={styles.subtitle}>Manage organizations/companies, their admins, and email data.</p>
        </div>
        <button className={styles.addBtn} onClick={openCreate}>
          <Plus size={15} /> New Company
        </button>
      </div>

      {msg && (
        <div className={`${styles.msg} ${msgType === 'error' ? styles.msgError : styles.msgSuccess}`}>
          {msgType === 'error' ? <AlertCircle size={15} /> : <CheckCircle2 size={15} />}
          {msg}
        </div>
      )}

      {/* Search */}
      <div className={styles.searchBar}>
        <Search size={14} />
        <input
          type="text"
          placeholder="Cari perusahaan atau admin..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className={styles.searchInput}
        />
        <span className={styles.searchCount}>{filtered.length} companies</span>
      </div>

      {/* Modal Form */}
      {showForm && (
        <div className={styles.modalOverlay} onClick={() => setShowForm(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>{editOrg ? 'Edit Company' : 'New Company'}</h3>
              <button className={styles.modalClose} onClick={() => setShowForm(false)}><X size={18} /></button>
            </div>
            <div className={styles.modalBody}>
              <label className={styles.fieldLabel}>Company Name *</label>
              <input
                type="text"
                className={styles.fieldInput}
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. PT Maju Jaya"
              />
              <label className={styles.fieldLabel}>Domain (optional)</label>
              <input
                type="text"
                className={styles.fieldInput}
                value={formDomain}
                onChange={(e) => setFormDomain(e.target.value)}
                placeholder="e.g. majujaya.com"
              />
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.cancelBtn} onClick={() => setShowForm(false)}>Cancel</button>
              <button className={styles.saveBtn} onClick={handleSave}>
                <Check size={14} /> {editOrg ? 'Update' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Company Cards */}
      <div className={styles.grid}>
        {filtered.length === 0 ? (
          <div className={styles.emptyState}>
            <Building size={40} />
            <h3>Tidak ada perusahaan</h3>
            <p>Buat perusahaan baru untuk memulai.</p>
          </div>
        ) : (
          filtered.map((org) => (
            <div key={org.id} className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardAvatar} style={{ background: '#EEF2FF', color: '#4F46E5' }}>
                  {org.name.slice(0, 2).toUpperCase()}
                </div>
                <div className={styles.cardInfo}>
                  <span className={styles.cardName}>{org.name}</span>
                  <span className={styles.cardDomain}>{org.config?.domain || 'No domain'}</span>
                </div>
                <div className={styles.cardActions}>
                  <button className={styles.actionBtn} onClick={() => openEdit(org)} title="Edit"><Edit3 size={14} /></button>
                  <button className={styles.actionBtn} onClick={() => handleDelete(org)} title="Delete"><Trash2 size={14} /></button>
                </div>
              </div>
              <div className={styles.cardStats}>
                <div className={styles.cardStat}>
                  <Users size={13} />
                  <span>{org.admin_count} admin{org.admin_count !== 1 ? 's' : ''}</span>
                </div>
                <div className={styles.cardStat}>
                  <Users size={13} />
                  <span>{org.user_count} user{org.user_count !== 1 ? 's' : ''}</span>
                </div>
                <div className={styles.cardStat}>
                  <Mail size={13} />
                  <span>{org.mailbox_count} mailbox{org.mailbox_count !== 1 ? 'es' : ''}</span>
                </div>
                <div className={styles.cardStat}>
                  <Shield size={13} />
                  <span>{org.email_count} emails</span>
                </div>
              </div>
              {org.admins?.length > 0 && (
                <div className={styles.cardAdmins}>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600 }}>ADMINS</span>
                  {org.admins.map((a) => (
                    <div key={a.username} className={styles.adminChip}>
                      <Shield size={10} />
                      {a.username} {a.email ? `<${a.email}>` : ''}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
