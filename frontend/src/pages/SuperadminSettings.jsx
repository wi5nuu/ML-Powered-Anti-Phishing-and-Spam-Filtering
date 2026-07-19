import { useState, useEffect } from 'react'
import {
  Settings, Save, Loader2, Shield, Sliders, Wifi,
  Users, Globe, Server, Plus, Trash2, TestTube,
  CheckCircle, XCircle, RefreshCw
} from 'lucide-react'
import { useMe } from '../api/auth'
import { useSettings, useUpdateSettings, useTestImap } from '../api/metrics'
import api from '../api/client'
import { useToast } from '../hooks/useToast'
import styles from './SuperadminSettings.module.css'

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

function ThresholdSlider({ label, value, onChange, min = 0, max = 1, step = 0.01, color }) {
  return (
    <div className={styles.sliderWrap}>
      <div className={styles.sliderTop}>
        <span className={styles.sliderLabel}>{label}</span>
        <span className={styles.sliderVal} style={{ color }}>{(value * 100).toFixed(0)}%</span>
      </div>
      <input
        type="range"
        className={styles.slider}
        min={min} max={max} step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        style={{ '--track-color': color }}
      />
      <div className={styles.sliderMarks}>
        <span>0%</span><span>50%</span><span>100%</span>
      </div>
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

const DEFAULTS = {
  threshold_quarantine: 0.70,
  threshold_warn: 0.30,
  fusion_ml_weight: 0.50,
  fusion_sa_weight: 0.25,
  fusion_anomaly_weight: 0.25,
  imap_host: '',
  imap_port: 993,
  imap_user: '',
  poll_interval_seconds: 30,
  protected_domains: [],
  whitelist_senders: [],
  admin_alert_email: '',
  max_quarantine_days: 30,
}

export default function SuperadminSettings() {
  const { addToast } = useToast()
  const { data: me } = useMe()
  const { data: remoteSettings, isLoading, isError } = useSettings()
  const { mutate: saveSettings, isPending: isSaving } = useUpdateSettings()
  const { mutate: testImap, isPending: isTesting, data: imapTestResult } = useTestImap()

  const [local, setLocal] = useState(DEFAULTS)
  const [dirty, setDirty] = useState(false)

  const [roleSettings, setRoleSettings] = useState(null)
  const [roleDirty, setRoleDirty] = useState(false)

  useEffect(() => {
    if (remoteSettings) {
      setLocal({ ...DEFAULTS, ...remoteSettings })
      setDirty(false)
    }
  }, [remoteSettings])

  useEffect(() => {
    api.get('/superadmin/settings/roles').then(({ data }) => {
      setRoleSettings(data)
    }).catch(() => {})
  }, [])

  const set = (key, val) => {
    setLocal(prev => ({ ...prev, [key]: val }))
    setDirty(true)
  }

  const setRole = (key, val) => {
    setRoleSettings(prev => ({ ...prev, [key]: val }))
    setRoleDirty(true)
  }

  const handleSave = () => {
    const wsum = local.fusion_ml_weight + local.fusion_sa_weight + local.fusion_anomaly_weight
    if (Math.abs(wsum - 1.0) > 0.05) {
      addToast(`Total bobot fusi harus = 100% (sekarang ${(wsum * 100).toFixed(0)}%)`, 'warning')
      return
    }
    if (local.threshold_warn >= local.threshold_quarantine) {
      addToast('Ambang karantina harus lebih besar dari ambang peringatan.', 'warning')
      return
    }
    saveSettings(local, {
      onSuccess: () => {
        addToast('Pengaturan sistem berhasil disimpan.', 'success')
        setDirty(false)
      },
      onError: (err) => {
        addToast(err?.response?.data?.detail || 'Gagal menyimpan pengaturan.', 'error')
      },
    })
  }

  const handleReset = () => {
    if (!window.confirm('Reset semua pengaturan ke nilai default?')) return
    setLocal(DEFAULTS)
    setDirty(true)
  }

  const handleTestImap = () => {
    testImap(undefined, {
      onSuccess: (data) => {
        if (data?.data?.ok) addToast(data.data.message, 'success')
        else addToast(data?.data?.message || 'Koneksi gagal.', 'error')
      },
      onError: () => addToast('Gagal menguji koneksi IMAP.', 'error'),
    })
  }

  const handleSaveRoles = async () => {
    try {
      await api.put('/superadmin/settings/roles', {
        allow_admin_user_management: roleSettings?.allow_admin_user_management ?? true,
        allow_admin_mailbox_management: roleSettings?.allow_admin_mailbox_management ?? true,
        allow_admin_quarantine_review: roleSettings?.allow_admin_quarantine_review ?? true,
        self_registration: roleSettings?.self_registration ?? false,
        default_user_role: roleSettings?.default_user_role ?? 'user',
        session_timeout_minutes: roleSettings?.session_timeout_minutes ?? 60,
      })
      addToast('Pengaturan role berhasil disimpan.', 'success')
      setRoleDirty(false)
    } catch {
      addToast('Gagal menyimpan pengaturan role.', 'error')
    }
  }

  if (isLoading) {
    return (
      <div className={styles.loading}>
        <Loader2 size={20} className={styles.spin} />
        Memuat pengaturan sistem...
      </div>
    )
  }

  if (isError) {
    return <div className={styles.error}>Gagal memuat pengaturan sistem.</div>
  }

  const wsum = local.fusion_ml_weight + local.fusion_sa_weight + local.fusion_anomaly_weight

  return (
    <div className={styles.wrap}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}><Settings size={20} /> Pengaturan Sistem Global</h1>
          <p className={styles.subtitle}>Konfigurasi threshold, bobot model, domain, dan kebijakan role.</p>
        </div>
        <div className={styles.headerActions}>
          <button className={styles.btnOutline} onClick={handleReset} disabled={isSaving}>
            <RefreshCw size={15} /> Reset
          </button>
          <button className={`${styles.btnPrimary} ${dirty ? styles.btnDirty : ''}`} onClick={handleSave} disabled={isSaving}>
            {isSaving ? <Loader2 size={15} className={styles.spin} /> : <Save size={15} />}
            {isSaving ? 'Menyimpan...' : 'Simpan Global'}
          </button>
        </div>
      </div>

      {dirty && (
        <div className={styles.dirtyBanner}>
          Ada perubahan yang belum disimpan.
        </div>
      )}

      {/* Thresholds & Weights & IMAP */}
      <div className={styles.layoutTop}>
        <Section icon={Sliders} title="Threshold Keamanan">
          <ThresholdSlider
            label="Ambang Karantina (QUARANTINE)"
            value={local.threshold_quarantine}
            onChange={(v) => set('threshold_quarantine', v)}
            color="#c5221f"
          />
          <ThresholdSlider
            label="Ambang Peringatan (WARN)"
            value={local.threshold_warn}
            onChange={(v) => set('threshold_warn', v)}
            color="#856404"
          />
          <p className={styles.hint}>
            Skor ≥ Karantina → QUARANTINE | Skor ≥ Peringatan → WARN | Skor lebih rendah → CLEAN
          </p>
        </Section>

        <Section icon={Sliders} title="Bobot Fusi Model (Total = 100%)">
          <ThresholdSlider
            label="ML Supervised (XGBoost)"
            value={local.fusion_ml_weight}
            onChange={(v) => set('fusion_ml_weight', Math.round(v * 100) / 100)}
            color="#1a73e8"
          />
          <ThresholdSlider
            label="SpamAssassin"
            value={local.fusion_sa_weight}
            onChange={(v) => set('fusion_sa_weight', Math.round(v * 100) / 100)}
            color="#34a853"
          />
          <ThresholdSlider
            label="Anomali Unsupervised"
            value={local.fusion_anomaly_weight}
            onChange={(v) => set('fusion_anomaly_weight', Math.round(v * 100) / 100)}
            color="#ea4335"
          />
          <div className={`${styles.weightSum} ${Math.abs(wsum - 1) > 0.05 ? styles.weightBad : styles.weightGood}`}>
            Total: {(wsum * 100).toFixed(0)}%
            {Math.abs(wsum - 1) > 0.05 ? ' Harus tepat 100%' : ''}
          </div>
        </Section>

        <Section icon={Wifi} title="Koneksi IMAP">
          <FieldRow label="IMAP Host" hint="Server email untuk polling">
            <input className={styles.input} type="text" placeholder="imap.gmail.com"
              value={local.imap_host} onChange={(e) => set('imap_host', e.target.value)} />
          </FieldRow>
          <FieldRow label="Port" hint="993 untuk SSL, 143 untuk STARTTLS">
            <input className={styles.input} type="number" min={1} max={65535}
              value={local.imap_port} onChange={(e) => set('imap_port', parseInt(e.target.value) || 993)} />
          </FieldRow>
          <FieldRow label="Username" hint="Akun email monitor">
            <input className={styles.input} type="text" placeholder="monitor@domain.com"
              value={local.imap_user} onChange={(e) => set('imap_user', e.target.value)} />
          </FieldRow>
          <FieldRow label="Poll Interval" hint="Seberapa sering email di-poll (detik)">
            <input className={styles.input} type="number" min={10} max={3600}
              value={local.poll_interval_seconds} onChange={(e) => set('poll_interval_seconds', parseInt(e.target.value) || 30)} />
          </FieldRow>
          <div className={styles.imapTestRow}>
            <button className={styles.btnTest} onClick={handleTestImap} disabled={isTesting || !local.imap_host}>
              {isTesting ? <Loader2 size={15} className={styles.spin} /> : <TestTube size={15} />}
              {isTesting ? 'Menguji...' : 'Uji Koneksi'}
            </button>
            {imapTestResult?.data && (
              <div className={`${styles.testResult} ${imapTestResult.data.ok ? styles.testOk : styles.testFail}`}>
                {imapTestResult.data.ok
                  ? <><CheckCircle size={14} /> {imapTestResult.data.message}</>
                  : <><XCircle size={14} /> {imapTestResult.data.message}</>}
              </div>
            )}
          </div>
        </Section>
      </div>

      {/* Domains & Whitelist */}
      <div className={styles.layoutBottom}>
        <Section icon={Globe} title="Domain Terlindungi">
          <p className={styles.hint}>
            Domain berikut akan dimonitor untuk serangan lookalike / typosquatting.
          </p>
          <EditableList
            items={local.protected_domains || []}
            onAdd={(v) => set('protected_domains', [...(local.protected_domains || []), v])}
            onRemove={(i) => set('protected_domains', local.protected_domains.filter((_, idx) => idx !== i))}
            placeholder="contoh: domain.com"
          />
        </Section>

        <Section icon={CheckCircle} title="Pengaturan Lainnya">
          <FieldRow label="Email Notifikasi Admin" hint="Alert dikirim ke alamat ini saat ada ancaman">
            <input className={styles.input} type="email" placeholder="admin@domain.com"
              value={local.admin_alert_email} onChange={(e) => set('admin_alert_email', e.target.value)} />
          </FieldRow>
          <FieldRow label="Retensi Karantina (hari)" hint="Email karantina dihapus setelah N hari">
            <input className={styles.input} type="number" min={1} max={365}
              value={local.max_quarantine_days} onChange={(e) => set('max_quarantine_days', parseInt(e.target.value) || 30)} />
          </FieldRow>
        </Section>
      </div>

      {/* Role Settings */}
      {roleSettings && (
        <Section icon={Users} title="Pengaturan Role & Kebijakan">
          <div className={styles.roleGrid}>
            <FieldRow label="Manajemen User oleh Admin" hint="Izinkan admin mengelola user di organisasinya.">
              <label className={styles.toggle}>
                <input type="checkbox" checked={!!roleSettings.allow_admin_user_management}
                  onChange={(e) => setRole('allow_admin_user_management', e.target.checked)} />
                <span className={styles.toggleSlider}></span>
              </label>
            </FieldRow>
            <FieldRow label="Manajemen Mailbox oleh Admin" hint="Izinkan admin mengelola mailbox organisasi.">
              <label className={styles.toggle}>
                <input type="checkbox" checked={!!roleSettings.allow_admin_mailbox_management}
                  onChange={(e) => setRole('allow_admin_mailbox_management', e.target.checked)} />
                <span className={styles.toggleSlider}></span>
              </label>
            </FieldRow>
            <FieldRow label="Review Karantina oleh Admin" hint="Izinkan admin mereview email terkaranina.">
              <label className={styles.toggle}>
                <input type="checkbox" checked={!!roleSettings.allow_admin_quarantine_review}
                  onChange={(e) => setRole('allow_admin_quarantine_review', e.target.checked)} />
                <span className={styles.toggleSlider}></span>
              </label>
            </FieldRow>
            <FieldRow label="Registrasi Mandiri" hint="Izinkan pengguna mendaftar sendiri tanpa undangan.">
              <label className={styles.toggle}>
                <input type="checkbox" checked={!!roleSettings.self_registration}
                  onChange={(e) => setRole('self_registration', e.target.checked)} />
                <span className={styles.toggleSlider}></span>
              </label>
            </FieldRow>
            <FieldRow label="Role Default" hint="Role yang diberikan saat pengguna mendaftar.">
              <select className={styles.input} value={roleSettings.default_user_role || 'user'}
                onChange={(e) => setRole('default_user_role', e.target.value)}>
                {(roleSettings.available_roles || []).map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </FieldRow>
            <FieldRow label="Sesi Timeout (menit)" hint="Waktu sesi login sebelum kadaluarsa.">
              <input className={styles.input} type="number" min={5} max={480}
                value={roleSettings.session_timeout_minutes ?? 60}
                onChange={(e) => setRole('session_timeout_minutes', parseInt(e.target.value) || 60)} />
            </FieldRow>
          </div>
          <div className={styles.sectionActions}>
            <button className={styles.btnPrimary} onClick={handleSaveRoles}>
              <Save size={15} /> Simpan Pengaturan Role
            </button>
          </div>
        </Section>
      )}
    </div>
  )
}
