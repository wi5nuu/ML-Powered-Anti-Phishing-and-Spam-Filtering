import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from '../i18n/context'
import { KeyRound, Plus, Trash2, Copy, Check, Loader2, RefreshCw } from 'lucide-react'
import AdminShell from '../components/layout/AdminShell'
import api from '../api/client'
import { useToast } from '../hooks/useToast'
import styles from './SettingsPage.module.css'

export default function ApiKeysPage() {
  const { t } = useTranslation()
  const { showToast } = useToast()
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [showNewKey, setShowNewKey] = useState(false)
  const [newKeyValue, setNewKeyValue] = useState('')
  const [copied, setCopied] = useState(false)

  const fetchKeys = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/auth/api-keys')
      setKeys(data || [])
    } catch {
      showToast(t('apiKeys.loadError'), 'error')
    } finally {
      setLoading(false)
    }
  }, [showToast, t])

  useEffect(() => {
    fetchKeys()
  }, [fetchKeys])

  const handleCreate = async () => {
    const name = newKeyName.trim()
    if (!name) return
    setCreating(true)
    try {
      const { data } = await api.post('/auth/api-keys', { name })
      setNewKeyValue(data.key)
      setShowNewKey(true)
      setNewKeyName('')
      showToast(t('apiKeys.created'), 'success')
      fetchKeys()
    } catch {
      showToast(t('apiKeys.createError'), 'error')
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (keyId) => {
    if (!window.confirm(t('apiKeys.deleteConfirm'))) return
    try {
      await api.delete(`/auth/api-keys/${keyId}`)
      showToast(t('apiKeys.deleted'), 'success')
      fetchKeys()
    } catch {
      showToast(t('apiKeys.deleteError'), 'error')
    }
  }

  const handleCopyKey = () => {
    navigator.clipboard.writeText(newKeyValue)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDismissNewKey = () => {
    setShowNewKey(false)
    setNewKeyValue('')
  }

  return (
    <AdminShell>
      <div className={styles.wrap}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h1 className={styles.title}><KeyRound size={22} /> {t('apiKeys.title')}</h1>
            <p className={styles.subtitle}>{t('apiKeys.subtitle')}</p>
          </div>
          <div className={styles.headerActions}>
            <button className={styles.btnOutline} onClick={fetchKeys} disabled={loading}>
              <RefreshCw size={15} className={loading ? styles.spin : ''} /> {t('common.refresh')}
            </button>
          </div>
        </div>

        {showNewKey && newKeyValue && (
          <div style={{ background: '#e8f5e9', border: '1px solid #a5d6a7', borderRadius: 8, padding: 16, marginBottom: 24 }}>
            <h3 style={{ margin: '0 0 8px', color: '#2e7d32', fontSize: '0.95rem' }}>{t('apiKeys.keyGenerated')}</h3>
            <p style={{ margin: '0 0 12px', color: '#555', fontSize: '0.85rem' }}>{t('apiKeys.keyGeneratedHint')}</p>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <code style={{ flex: 1, padding: '10px 14px', background: '#fff', borderRadius: 6, border: '1px solid #c8e6c9', fontSize: '0.85rem', wordBreak: 'break-all' }}>
                {newKeyValue}
              </code>
              <button className={styles.btnPrimary} onClick={handleCopyKey} title={t('common.copy')}>
                {copied ? <Check size={15} /> : <Copy size={15} />}
              </button>
              <button className={styles.btnOutline} onClick={handleDismissNewKey}>{t('common.close')}</button>
            </div>
          </div>
        )}

        <div className={styles.layoutBottom}>
          <div className={styles.section}>
            <h2 className={styles.sectionTitle}>{t('apiKeys.createKey')}</h2>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
              <input
                className={styles.input}
                type="text"
                placeholder={t('apiKeys.namePlaceholder')}
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                style={{ flex: 1 }}
              />
              <button className={styles.btnPrimary} onClick={handleCreate} disabled={creating || !newKeyName.trim()}>
                {creating ? <Loader2 size={15} className={styles.spin} /> : <Plus size={15} />}
                {creating ? t('common.creating') : t('apiKeys.createBtn')}
              </button>
            </div>
          </div>

          <div className={styles.section}>
            <h2 className={styles.sectionTitle}>{t('apiKeys.existingKeys')}</h2>
            {loading ? (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                <Loader2 size={24} className={styles.spin} />
              </div>
            ) : keys.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', padding: 16 }}>{t('apiKeys.noKeys')}</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
                {keys.map((key) => (
                  <div key={key.id} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '12px 16px', background: 'var(--surface)', borderRadius: 8,
                    border: '1px solid var(--border)'
                  }}>
                    <div>
                      <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>{key.name}</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 2 }}>
                        {t('apiKeys.status')}: {key.is_active ? 'Active' : 'Inactive'} | {t('apiKeys.rateLimit')}: {key.rate_limit}/h | {t('apiKeys.createdLabel')}: {key.created_at ? new Date(key.created_at).toLocaleDateString() : '-'}
                      </div>
                    </div>
                    <button className={styles.trashBtn} onClick={() => handleDelete(key.id)} title={t('common.delete')}>
                      <Trash2 size={15} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AdminShell>
  )
}