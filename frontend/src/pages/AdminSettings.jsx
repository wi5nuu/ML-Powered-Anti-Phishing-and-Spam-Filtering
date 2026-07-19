import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Settings, Save, Loader2, Shield, Mail, Users,
  Trash2, Plus, CheckCircle, AlertTriangle, Clock
} from 'lucide-react'
import { useMe } from '../api/auth'
import api from '../api/client'
import { useToast } from '../hooks/useToast'
import styles from './AdminSettings.module.css'

function Section({ icon: Icon, title, children }) {
  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}><Icon size={18} />{title}</h2>
      {children}
    </div>
  )
}

function FieldRow({ label, hint, children }) {
  return (
    <div className={styles.fieldRow}>
      <div className={styles.fieldLeft}>
        <label className={styles.fieldLabel}>{label}</label>
        {hint && <span className={styles.fieldHint}>{hint}</span>}
      </div>
      <div className={styles.fieldRight}>{children}</div>
    </div>
  )
}

function EditableList({ items, onAdd, onRemove, placeholder }) {
  const [draft, setDraft] = useState('')
  const handleAdd = () => {
    const v = draft.trim().toLowerCase()
    if (!v) return
    if (items.includes(v)) return
    onAdd(v)
    setDraft('')
  }
  return (
    <div className={styles.listWrap}>
      <div className={styles.listItems}>
        {items.length === 0 && (
          <span className={styles.listEmpty}>Belum ada item.</span>
        )}
        {items.map((item, i) => (
          <div key={i} className={styles.listChip}>
            <span>{item}</span>
            <button className={styles.chipRemove} onClick={() => onRemove(i)} title={`Hapus ${item}`}>
              <Trash2 size={12} />
            </button>
          </div>
        ))}
      </div>
      <div className={styles.listAdd}>
        <input
          className={styles.listInput}
          type="text"
          placeholder={placeholder}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
        />
        <button className={styles.listAddBtn} onClick={handleAdd}>
          <Plus size={14} /> Tambah
        </button>
      </div>
    </div>
  )
}

export default function AdminSettings() {
  const { addToast } = useToast()
  const { data: me } = useMe()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [orgName, setOrgName] = useState('')
  const [maxQuarantineDays, setMaxQuarantineDays] = useState(30)
  const [quarantineAction, setQuarantineAction] = useState('quarantine')
  const [notifyOnThreat, setNotifyOnThreat] = useState(true)
  const [allowSenderOverride, setAllowSenderOverride] = useState(false)
  const [defaultMailboxLimit, setDefaultMailboxLimit] = useState(50)
  const [retentionDays, setRetentionDays] = useState(90)

  const [whitelistSenders, setWhitelistSenders] = useState([])
  const [protectedDomains, setProtectedDomains] = useState([])

  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!me) return
    Promise.all([
      api.get('/admin/settings').catch(() => ({ data: {} })),
      api.get('/settings').catch(() => ({ data: {} })),
    ]).then(([orgRes, sysRes]) => {
      const org = orgRes.data || {}
      const sys = sysRes.data || {}
      setOrgName(org.org_name || '')
      setMaxQuarantineDays(org.max_quarantine_days ?? sys.max_quarantine_days ?? 30)
      setQuarantineAction(org.quarantine_action || 'quarantine')
      setNotifyOnThreat(org.notify_on_threat ?? true)
      setAllowSenderOverride(org.allow_sender_override ?? false)
      setDefaultMailboxLimit(org.default_mailbox_limit ?? 50)
      setRetentionDays(org.retention_days ?? 90)
      setWhitelistSenders(sys.whitelist_senders || [])
      setProtectedDomains(sys.protected_domains || [])
    }).finally(() => setLoading(false))
  }, [me])

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put('/admin/settings', {
        org_name: orgName,
        max_quarantine_days: maxQuarantineDays,
        quarantine_action: quarantineAction,
        notify_on_threat: notifyOnThreat,
        allow_sender_override: allowSenderOverride,
        default_mailbox_limit: defaultMailboxLimit,
        retention_days: retentionDays,
      })
      addToast('Pengaturan organisasi berhasil disimpan.', 'success')
    } catch {
      addToast('Gagal menyimpan pengaturan.', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className={styles.loading}>
        <Loader2 size={20} className={styles.spin} />
        Memuat pengaturan...
      </div>
    )
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}><Settings size={20} /> Pengaturan Organisasi</h1>
          <p className={styles.subtitle}>Kelola pengaturan organisasi, mailbox, whitelist, dan aturan karantina.</p>
        </div>
        <div className={styles.headerActions}>
          <button className={styles.btnPrimary} onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 size={15} className={styles.spin} /> : <Save size={15} />}
            {saving ? 'Menyimpan...' : 'Simpan'}
          </button>
        </div>
      </div>

      <div className={styles.layoutTop}>
        <Section icon={Users} title="Organisasi">
          <FieldRow label="Nama Organisasi" hint="Nama perusahaan atau instansi Anda.">
            <input className={styles.input} value={orgName} onChange={(e) => setOrgName(e.target.value)} placeholder="Nama organisasi" />
          </FieldRow>
          <FieldRow label="Retensi Data (hari)" hint="Berapa lama data log aktivitas disimpan.">
            <input className={styles.input} type="number" min={1} max={365} value={retentionDays} onChange={(e) => setRetentionDays(parseInt(e.target.value) || 90)} />
          </FieldRow>
        </Section>

        <Section icon={Mail} title="Pengaturan Mailbox">
          <FieldRow label="Batas Mailbox Default" hint="Jumlah maksimal mailbox per organisasi.">
            <input className={styles.input} type="number" min={1} max={500} value={defaultMailboxLimit} onChange={(e) => setDefaultMailboxLimit(parseInt(e.target.value) || 50)} />
          </FieldRow>
          <FieldRow label="Atur Mailbox" hint="Kelola mailbox organisasi Anda.">
            <button className={styles.btnOutline} onClick={() => setSearchParams({ tab: 'email' })}>
              <Mail size={15} /> Kelola Mailbox
            </button>
          </FieldRow>
        </Section>
      </div>

      <div className={styles.layoutBottom}>
        <Section icon={CheckCircle} title="Whitelist Pengirim">
          <p className={styles.hint}>
            Email dari pengirim berikut tidak akan dikarantina.
          </p>
          <EditableList
            items={whitelistSenders}
            onAdd={(v) => setWhitelistSenders([...whitelistSenders, v])}
            onRemove={(i) => setWhitelistSenders(whitelistSenders.filter((_, idx) => idx !== i))}
            placeholder="contoh: noreply@trusted.co.id"
          />
        </Section>

        <Section icon={Shield} title="Aturan Karantina">
          <FieldRow label="Aksi Default" hint="Tindakan default untuk email mencurigakan.">
            <select className={styles.input} value={quarantineAction} onChange={(e) => setQuarantineAction(e.target.value)}>
              <option value="quarantine">Karantina</option>
              <option value="warn">Peringatan Saja</option>
              <option value="skip">Lewati</option>
            </select>
          </FieldRow>
          <FieldRow label="Maks. Hari Karantina" hint="Email dikarantina akan otomatis dihapus setelah N hari.">
            <input className={styles.input} type="number" min={1} max={365} value={maxQuarantineDays} onChange={(e) => setMaxQuarantineDays(parseInt(e.target.value) || 30)} />
          </FieldRow>
          <FieldRow label="Notifikasi Ancaman" hint="Kirim notifikasi saat ada email berbahaya terdeteksi.">
            <label className={styles.toggle}>
              <input type="checkbox" checked={notifyOnThreat} onChange={(e) => setNotifyOnThreat(e.target.checked)} />
              <span className={styles.toggleSlider}></span>
            </label>
          </FieldRow>
          <FieldRow label="Override Pengirim" hint="Izinkan admin melepas email dari karantina secara manual.">
            <label className={styles.toggle}>
              <input type="checkbox" checked={allowSenderOverride} onChange={(e) => setAllowSenderOverride(e.target.checked)} />
              <span className={styles.toggleSlider}></span>
            </label>
          </FieldRow>
        </Section>
      </div>
    </div>
  )
}
