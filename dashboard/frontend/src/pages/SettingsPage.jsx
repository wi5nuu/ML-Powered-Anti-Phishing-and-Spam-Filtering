import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Settings, Save, RefreshCw, TestTube, Plus, Trash2,
  Shield, Sliders, Wifi, CheckCircle, XCircle, Loader2,
  User, Bell, Lock, Mail
} from 'lucide-react'
import GmailShell from '../components/layout/GmailShell'
import { useMe } from '../api/auth'
import { useSettings, useUpdateSettings, useTestImap } from '../api/metrics'
import { useUpdateProfile } from '../api/profile'
import { useToast } from '../hooks/useToast'
import { getActiveMailbox, getMailDomain } from '../utils/mailbox'
import styles from './SettingsPage.module.css'

// ─── Section wrapper ─────────────────────────────────────────────────────────────
function Section({ icon: Icon, title, children }) {
  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}><Icon size={18} />{title}</h2>
      {children}
    </div>
  )
}

// ─── Field row ───────────────────────────────────────────────────────────────────
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

// ─── Threshold slider ─────────────────────────────────────────────────────────────
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

// ─── Editable list (domains / whitelist) ─────────────────────────────────────────
function EditableList({ items, onAdd, onRemove, placeholder, id }) {
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
            <button
              className={styles.chipRemove}
              onClick={() => onRemove(i)}
              title={`Hapus ${item}`}
              id={`${id}-remove-${i}`}
            >
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
          id={`${id}-input`}
        />
        <button
          className={styles.listAddBtn}
          onClick={handleAdd}
          id={`${id}-add-btn`}
        >
          <Plus size={14} /> Tambah
        </button>
      </div>
    </div>
  )
}

// ─── Main ────────────────────────────────────────────────────────────────────────
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
  protected_domains: ['lodaya.id', 'lodayatech.id', 'lodaya.co.id'],
  whitelist_senders: [],
  admin_alert_email: '',
  max_quarantine_days: 30,
}

export default function SettingsPage() {
  const { addToast } = useToast()
  const { data: me, isLoading: meLoading } = useMe()
  const { data: remoteSettings, isLoading, isError } = useSettings()
  const { mutate: saveSettings, isPending: isSaving } = useUpdateSettings()
  const { mutate: testImap, isPending: isTesting, data: imapTestResult } = useTestImap()
  const { mutate: updateProfile, isPending: isUpdatingProfile } = useUpdateProfile()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const role = me?.user?.role
  const isAdmin = role === 'admin' || role === 'superadmin'
  const isSuper = role === 'superadmin'
  const activeMailbox = getActiveMailbox(searchParams)
  const activeMailDomain = getMailDomain()

  const [local, setLocal] = useState(DEFAULTS)
  const [dirty, setDirty] = useState(false)
  const [accountUsername, setAccountUsername] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  useEffect(() => {
    if (me?.user?.username) setAccountUsername(me.user.username)
  }, [me?.user?.username])

  // Sync from server
  useEffect(() => {
    if (remoteSettings) {
      setLocal({ ...DEFAULTS, ...remoteSettings })
      setDirty(false)
    }
  }, [remoteSettings])

  const set = (key, val) => {
    setLocal(prev => ({ ...prev, [key]: val }))
    setDirty(true)
  }

  const handleSave = () => {
    // Validate weights sum to ~1
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
        addToast('Pengaturan berhasil disimpan.', 'success')
        setDirty(false)
      },
      onError: (err) => {
        const msg = err?.response?.data?.detail || 'Gagal menyimpan pengaturan.'
        addToast(msg, 'error')
      },
    })
  }

  const handleReset = () => {
    if (!window.confirm('Reset semua pengaturan ke nilai default? Perubahan yang belum disimpan akan hilang.')) return
    setLocal(DEFAULTS)
    setDirty(true)
    addToast('Pengaturan direset ke default.', 'info')
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

  const handleSaveAccount = () => {
    if (!currentPassword) {
      addToast('Masukkan password saat ini untuk menyimpan perubahan akun.', 'warning')
      return
    }
    if (newPassword && newPassword !== confirmPassword) {
      addToast('Konfirmasi password baru tidak cocok.', 'warning')
      return
    }
    updateProfile({
      username: accountUsername,
      current_password: currentPassword,
      new_password: newPassword,
    }, {
      onSuccess: () => {
        addToast('Akun berhasil diperbarui.', 'success')
        setCurrentPassword('')
        setNewPassword('')
        setConfirmPassword('')
      },
      onError: (err) => {
        addToast(err?.response?.data?.detail || 'Gagal memperbarui akun.', 'error')
      },
    })
  }

  const accountSection = (
    <Section icon={User} title="Akun Login">
      <FieldRow label="Username" hint="Username yang digunakan saat login.">
        <input
          className={styles.input}
          value={accountUsername}
          onChange={(e) => setAccountUsername(e.target.value)}
          placeholder="Username"
        />
      </FieldRow>
      <FieldRow label="Password Saat Ini" hint="Wajib diisi untuk mengganti username atau password.">
        <input
          className={styles.input}
          type="password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          placeholder="Password saat ini"
        />
      </FieldRow>
      <FieldRow label="Password Baru" hint="Kosongkan jika tidak ingin mengganti password.">
        <input
          className={styles.input}
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          placeholder="Password baru"
        />
      </FieldRow>
      <FieldRow label="Konfirmasi Password" hint="Ulangi password baru.">
        <input
          className={styles.input}
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          placeholder="Konfirmasi password baru"
        />
      </FieldRow>
      <div className={styles.sectionActions}>
        <button className={styles.btnPrimary} onClick={handleSaveAccount} disabled={isUpdatingProfile}>
          {isUpdatingProfile ? <Loader2 size={15} className={styles.spin} /> : <Save size={15} />}
          {isUpdatingProfile ? 'Menyimpan...' : 'Simpan Akun'}
        </button>
      </div>
    </Section>
  )

  if (meLoading || isLoading) {
    return (
      <GmailShell>
        <div className={styles.loading}>
          <Loader2 size={24} className={styles.spin} />
          Memuat pengaturan...
        </div>
      </GmailShell>
    )
  }

  // ── ANALYST / REGULAR USER ──
  if (!isAdmin && !isSuper) {
    return (
      <GmailShell>
        <div className={styles.wrap}>
          <div className={styles.header}>
            <div className={styles.headerLeft}>
              <h1 className={styles.title}><Settings size={22} /> Pengaturan Akun</h1>
              <p className={styles.subtitle}>Kelola preferensi notifikasi dan informasi akun Anda.</p>
            </div>
          </div>

          <div className={styles.layoutBottom}>
            {activeMailbox && (
              <Section icon={Mail} title="Mailbox Aktif">
                <FieldRow label="Email aktif" hint="Pengaturan sedang dibuka dari dashboard mailbox ini.">
                  <strong className={styles.readOnlyValue}>{activeMailbox}</strong>
                </FieldRow>
                <FieldRow label="Domain mailbox" hint="Domain perusahaan yang dipakai mailbox ini.">
                  <strong className={styles.readOnlyValue}>@{activeMailDomain}</strong>
                </FieldRow>
              </Section>
            )}
            {accountSection}
            <Section icon={User} title="Informasi Profil">
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}>Username</label>
                  <span className={styles.fieldHint}>{me?.user?.username || '-'}</span>
                </div>
                <div className={styles.fieldRight}>
                  <button className={styles.btnOutline} onClick={() => navigate('/profile')}>
                    <User size={15} /> Lihat Profil
                  </button>
                </div>
              </div>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}>Role</label>
                  <span className={styles.fieldHint}>{me?.user?.role || '-'}</span>
                </div>
              </div>
            </Section>

            <Section icon={Bell} title="Preferensi Notifikasi">
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}>Notifikasi Email</label>
                  <span className={styles.fieldHint}>Dapatkan pemberitahuan saat ada email masuk dikarantina</span>
                </div>
                <div className={styles.fieldRight}>
                  <label className={styles.toggle}>
                    <input type="checkbox" defaultChecked />
                    <span className={styles.toggleSlider}></span>
                  </label>
                </div>
              </div>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}>Ringkasan Harian</label>
                  <span className={styles.fieldHint}>Terima laporan ringkasan setiap hari</span>
                </div>
                <div className={styles.fieldRight}>
                  <label className={styles.toggle}>
                    <input type="checkbox" />
                    <span className={styles.toggleSlider}></span>
                  </label>
                </div>
              </div>
            </Section>
          </div>

          <div className={styles.footer}>
            <small style={{ color: 'var(--text-muted)', padding: '8px 0' }}>
              Pengaturan sistem hanya dapat diubah oleh Admin dan Super Admin.
            </small>
          </div>
        </div>
      </GmailShell>
    )
  }

  // ── ADMIN / SUPERADMIN — config error ──
  if (isError) {
    return (
      <GmailShell>
        <div className={styles.error}>
          Gagal memuat pengaturan sistem.
        </div>
      </GmailShell>
    )
  }

  const wsum = local.fusion_ml_weight + local.fusion_sa_weight + local.fusion_anomaly_weight

  return (
    <GmailShell>
      <div className={styles.wrap}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h1 className={styles.title}><Settings size={22} /> Pengaturan Sistem</h1>
            <p className={styles.subtitle}>Konfigurasi threshold, bobot model, dan parameter koneksi email.</p>
          </div>
          <div className={styles.headerActions}>
            <button
              className={styles.btnOutline}
              onClick={handleReset}
              disabled={isSaving}
              id="settings-reset-btn"
            >
              <RefreshCw size={15} /> Reset Default
            </button>
            <button
              className={`${styles.btnPrimary} ${dirty ? styles.btnDirty : ''}`}
              onClick={handleSave}
              disabled={isSaving}
              id="settings-save-btn"
            >
              {isSaving ? <Loader2 size={15} className={styles.spin} /> : <Save size={15} />}
              {isSaving ? 'Menyimpan...' : 'Simpan Pengaturan'}
            </button>
          </div>
        </div>

        {dirty && (
          <div className={styles.dirtyBanner}>
            ⚠ Ada perubahan yang belum disimpan.
          </div>
        )}

        {/* 3-column grid: Thresholds | Fusion Weights | IMAP */}
        <div className={styles.layoutBottom}>
          {activeMailbox && (
            <Section icon={Mail} title="Mailbox Aktif">
              <FieldRow label="Email aktif" hint="Pengaturan sedang dibuka dari dashboard mailbox ini.">
                <strong className={styles.readOnlyValue}>{activeMailbox}</strong>
              </FieldRow>
              <FieldRow label="Domain mailbox" hint="Domain perusahaan yang dipakai mailbox ini.">
                <strong className={styles.readOnlyValue}>@{activeMailDomain}</strong>
              </FieldRow>
            </Section>
          )}
          {accountSection}
          <Section icon={Lock} title="Role & Akses">
            <div className={styles.fieldRow}>
              <div className={styles.fieldLeft}>
                <label className={styles.fieldLabel}>Role</label>
                <span className={styles.fieldHint}>{me?.user?.role || '-'}</span>
              </div>
              <div className={styles.fieldRight}>
                <button className={styles.btnOutline} onClick={() => navigate('/profile')}>
                  <User size={15} /> Lihat Profil
                </button>
              </div>
            </div>
          </Section>
        </div>

        {/* 3-column grid: Thresholds | Fusion Weights | IMAP */}
        <div className={styles.layoutTop}>
          <Section icon={Sliders} title="Ambang Deteksi">
            <ThresholdSlider
              label="Ambang Karantina (QUARANTINE)"
              value={local.threshold_quarantine}
              onChange={(v) => set('threshold_quarantine', v)}
              color="var(--text-muted)"
            />
            <ThresholdSlider
              label="Ambang Peringatan (WARN)"
              value={local.threshold_warn}
              onChange={(v) => set('threshold_warn', v)}
              color="var(--text-muted)"
            />
            <p className={styles.hint}>
              Skor ≥ Karantina → QUARANTINE | Skor ≥ Peringatan → WARN | Skor lebih rendah → CLEAN
            </p>
          </Section>

          <Section icon={Sliders} title="Bobot Fusi Model (Total harus = 100%)">
            <ThresholdSlider
              label={`ML Supervised (XGBoost) — saat ini ${(local.fusion_ml_weight * 100).toFixed(0)}%`}
              value={local.fusion_ml_weight}
              onChange={(v) => set('fusion_ml_weight', Math.round(v * 100) / 100)}
              color="var(--text-muted)"
            />
            <ThresholdSlider
              label={`SpamAssassin — saat ini ${(local.fusion_sa_weight * 100).toFixed(0)}%`}
              value={local.fusion_sa_weight}
              onChange={(v) => set('fusion_sa_weight', Math.round(v * 100) / 100)}
              color="var(--text-muted)"
            />
            <ThresholdSlider
              label={`Anomali Unsupervised — saat ini ${(local.fusion_anomaly_weight * 100).toFixed(0)}%`}
              value={local.fusion_anomaly_weight}
              onChange={(v) => set('fusion_anomaly_weight', Math.round(v * 100) / 100)}
              color="var(--text-muted)"
            />
            <div className={`${styles.weightSum} ${Math.abs(wsum - 1) > 0.05 ? styles.weightBad : styles.weightGood}`}>
              Total: {(wsum * 100).toFixed(0)}%
              {Math.abs(wsum - 1) > 0.05 ? ' ⚠ Harus tepat 100%' : ' ✓'}
            </div>
          </Section>

          <Section icon={Wifi} title="Koneksi IMAP">
            <FieldRow label="IMAP Host" hint="Server email yang akan di-poll">
              <input
                className={styles.input}
                type="text"
                placeholder="imap.gmail.com"
                value={local.imap_host}
                onChange={(e) => set('imap_host', e.target.value)}
                id="settings-imap-host"
              />
            </FieldRow>
            <FieldRow label="Port" hint="993 untuk SSL, 143 untuk STARTTLS">
              <input
                className={styles.input}
                type="number"
                min={1} max={65535}
                value={local.imap_port}
                onChange={(e) => set('imap_port', parseInt(e.target.value) || 993)}
                id="settings-imap-port"
              />
            </FieldRow>
            <FieldRow label="Username" hint="Alamat email akun monitor">
              <input
                className={styles.input}
                type="text"
                placeholder="monitor@lodaya.id"
                value={local.imap_user}
                onChange={(e) => set('imap_user', e.target.value)}
                id="settings-imap-user"
              />
            </FieldRow>
            <FieldRow label="Poll Interval" hint="Seberapa sering email di-poll (detik)">
              <input
                className={styles.input}
                type="number"
                min={10} max={3600}
                value={local.poll_interval_seconds}
                onChange={(e) => set('poll_interval_seconds', parseInt(e.target.value) || 30)}
                id="settings-poll-interval"
              />
            </FieldRow>
            <div className={styles.imapTestRow}>
              <button
                className={styles.btnTest}
                onClick={handleTestImap}
                disabled={isTesting || !local.imap_host}
                id="settings-test-imap-btn"
              >
                {isTesting ? <Loader2 size={15} className={styles.spin} /> : <TestTube size={15} />}
                {isTesting ? 'Menguji...' : 'Uji Koneksi'}
              </button>
              {imapTestResult?.data && (
                <div className={`${styles.testResult} ${imapTestResult.data.ok ? styles.testOk : styles.testFail}`}>
                  {imapTestResult.data.ok
                    ? <><CheckCircle size={14} /> {imapTestResult.data.message}</>
                    : <><XCircle size={14} /> {imapTestResult.data.message}</>
                  }
                </div>
              )}
            </div>
          </Section>
        </div>

        {/* 2-column grid: Domains | Whitelist */}
        <div className={styles.layoutBottom}>
          <Section icon={Shield} title="Domain Terlindungi">
            <p className={styles.hint}>
              Domain-domain berikut akan dimonitor untuk serangan lookalike / typosquatting.
            </p>
            <EditableList
              id="settings-domains"
              items={local.protected_domains || []}
              onAdd={(v) => set('protected_domains', [...(local.protected_domains || []), v])}
              onRemove={(i) => set('protected_domains', local.protected_domains.filter((_, idx) => idx !== i))}
              placeholder="contoh: lodaya.id"
            />
          </Section>

          <Section icon={CheckCircle} title="Whitelist Pengirim Terpercaya">
            <p className={styles.hint}>
              Email dari pengirim di daftar ini tidak akan dikarantina (dikecualikan dari filter).
            </p>
            <EditableList
              id="settings-whitelist"
              items={local.whitelist_senders || []}
              onAdd={(v) => set('whitelist_senders', [...(local.whitelist_senders || []), v])}
              onRemove={(i) => set('whitelist_senders', local.whitelist_senders.filter((_, idx) => idx !== i))}
              placeholder="contoh: noreply@trusted-bank.co.id"
            />
          </Section>
        </div>

        {/* Misc */}
        <Section icon={Settings} title="Pengaturan Lainnya">
          <FieldRow label="Email Notifikasi Admin" hint="Alert dikirim ke alamat ini saat ada ancaman">
            <input
              className={styles.input}
              type="email"
              placeholder="admin@lodaya.id"
              value={local.admin_alert_email}
              onChange={(e) => set('admin_alert_email', e.target.value)}
              id="settings-alert-email"
            />
          </FieldRow>
          <FieldRow label="Retensi Karantina (hari)" hint="Email karantina dihapus otomatis setelah N hari">
            <input
              className={styles.input}
              type="number"
              min={1} max={365}
              value={local.max_quarantine_days}
              onChange={(e) => set('max_quarantine_days', parseInt(e.target.value) || 30)}
              id="settings-retention-days"
            />
          </FieldRow>
        </Section>

        {/* Superadmin-only: User Management */}
        {isSuper && (
          <Section icon={Lock} title="Manajemen Super Admin">
            <p className={styles.hint}>
              Kelola pengguna, kebijakan keamanan, dan konfigurasi tingkat sistem lainnya.
            </p>
            <div className={styles.fieldRow}>
              <div className={styles.fieldLeft}>
                <label className={styles.fieldLabel}>Panel Admin</label>
                <span className={styles.fieldHint}>Kelola user, laporan, dan aktivitas sistem</span>
              </div>
              <div className={styles.fieldRight}>
                <button className={styles.btnPrimary} onClick={() => navigate(isSuper ? '/super-admin/dashboard' : '/admin/dashboard')}>
                  <Lock size={15} /> Buka Admin Panel
                </button>
              </div>
            </div>
          </Section>
        )}

        {/* Save footer */}
        <div className={styles.footer}>
          <button
            className={styles.btnOutline}
            onClick={handleReset}
            disabled={isSaving}
            id="settings-reset-footer-btn"
          >
            <RefreshCw size={15} /> Reset Default
          </button>
          <button
            className={`${styles.btnPrimary} ${dirty ? styles.btnDirty : ''}`}
            onClick={handleSave}
            disabled={isSaving}
            id="settings-save-footer-btn"
          >
            {isSaving ? <Loader2 size={15} className={styles.spin} /> : <Save size={15} />}
            {isSaving ? 'Menyimpan...' : 'Simpan Pengaturan'}
          </button>
        </div>
      </div>
    </GmailShell>
  )
}
