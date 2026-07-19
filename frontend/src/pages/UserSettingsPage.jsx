import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  User, Mail, Bell, Save, Loader2, Shield, Moon, Globe, Eye, EyeOff
} from 'lucide-react'
import { useMe } from '../api/auth'
import { useUpdateProfile } from '../api/profile'
import api from '../api/client'
import { useToast } from '../hooks/useToast'
import styles from './SettingsPage.module.css'

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

export default function UserSettingsPage() {
  const { addToast } = useToast()
  const { data: me } = useMe()
  const { mutate: updateProfile, isPending: isUpdatingProfile } = useUpdateProfile()
  const navigate = useNavigate()

  const [accountUsername, setAccountUsername] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [notificationEmail, setNotificationEmail] = useState(true)
  const [dailySummary, setDailySummary] = useState(false)
  const [theme, setTheme] = useState('system')
  const [language, setLanguage] = useState('id')

  const [showPassword, setShowPassword] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (me?.user?.username) setAccountUsername(me.user.username)
  }, [me?.user?.username])

  useEffect(() => {
    api.get('/user/settings').then(({ data }) => {
      if (data.notification_email !== undefined) setNotificationEmail(data.notification_email)
      if (data.daily_summary !== undefined) setDailySummary(data.daily_summary)
      if (data.theme) setTheme(data.theme)
      if (data.language) setLanguage(data.language)
    }).catch(() => {})
  }, [])

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

  const handleSavePreferences = async () => {
    setSaving(true)
    try {
      await api.put('/user/settings', {
        notification_email: notificationEmail,
        daily_summary: dailySummary,
        theme,
        language,
      })
      addToast('Preferensi berhasil disimpan.', 'success')
    } catch {
      addToast('Gagal menyimpan preferensi.', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}><User size={22} /> Pengaturan Akun</h1>
          <p className={styles.subtitle}>Kelola profil, preferensi notifikasi, dan pengaturan aplikasi Anda.</p>
        </div>
      </div>

      <div className={styles.layoutBottom}>
        <Section icon={User} title="Informasi Profil">
          <FieldRow label="Username" hint="Nama pengguna Anda saat login.">
            <strong className={styles.readOnlyValue}>{me?.user?.username || '-'}</strong>
          </FieldRow>
          <FieldRow label="Role" hint="Hak akses akun Anda.">
            <strong className={styles.readOnlyValue}>{me?.user?.role || '-'}</strong>
          </FieldRow>
          <FieldRow label="Email" hint="Alamat email terdaftar.">
            <strong className={styles.readOnlyValue}>{me?.user?.email || '-'}</strong>
          </FieldRow>
        </Section>

        <Section icon={Mail} title="Mailbox">
          <FieldRow label="Akses Mailbox" hint="Kelola email dan kotak masuk Anda.">
            <button className={styles.btnOutline} onClick={() => navigate('/inbox')}>
              <Mail size={15} /> Buka Inbox
            </button>
          </FieldRow>
        </Section>
      </div>

      <Section icon={Lock} title="Ubah Akun Login">
        <FieldRow label="Username Baru" hint="Ganti nama pengguna Anda.">
          <input
            className={styles.input}
            value={accountUsername}
            onChange={(e) => setAccountUsername(e.target.value)}
            placeholder="Username baru"
          />
        </FieldRow>
        <FieldRow label="Password Saat Ini" hint="Wajib diisi untuk menyimpan perubahan.">
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              className={styles.input}
              type={showPassword ? 'text' : 'password'}
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Password saat ini"
            />
            <button
              className={styles.btnOutline}
              onClick={() => setShowPassword(!showPassword)}
              title={showPassword ? 'Sembunyikan' : 'Tampilkan'}
              style={{ padding: '8px 12px' }}
            >
              {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
        </FieldRow>
        <FieldRow label="Password Baru" hint="Kosongkan jika tidak ingin mengganti.">
          <input
            className={styles.input}
            type={showPassword ? 'text' : 'password'}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Password baru"
          />
        </FieldRow>
        <FieldRow label="Konfirmasi Password" hint="Ulangi password baru.">
          <input
            className={styles.input}
            type={showPassword ? 'text' : 'password'}
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

      <Section icon={Bell} title="Preferensi Notifikasi">
        <FieldRow label="Notifikasi Email" hint="Dapatkan pemberitahuan saat ada email masuk dikarantina">
          <label className={styles.toggle}>
            <input type="checkbox" checked={notificationEmail} onChange={(e) => setNotificationEmail(e.target.checked)} />
            <span className={styles.toggleSlider}></span>
          </label>
        </FieldRow>
        <FieldRow label="Ringkasan Harian" hint="Terima laporan ringkasan keamanan setiap hari">
          <label className={styles.toggle}>
            <input type="checkbox" checked={dailySummary} onChange={(e) => setDailySummary(e.target.checked)} />
            <span className={styles.toggleSlider}></span>
          </label>
        </FieldRow>
      </Section>

      <Section icon={Shield} title="Pengaturan Aplikasi">
        <FieldRow label="Tema" hint="Pilih tampilan antarmuka">
          <select className={styles.input} value={theme} onChange={(e) => setTheme(e.target.value)}>
            <option value="system">Ikuti Sistem</option>
            <option value="light">Terang</option>
            <option value="dark">Gelap</option>
          </select>
        </FieldRow>
        <FieldRow label="Bahasa" hint="Bahasa antarmuka">
          <select className={styles.input} value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="id">Bahasa Indonesia</option>
            <option value="en">English</option>
          </select>
        </FieldRow>
        <div className={styles.sectionActions}>
          <button className={styles.btnPrimary} onClick={handleSavePreferences} disabled={saving}>
            {saving ? <Loader2 size={15} className={styles.spin} /> : <Save size={15} />}
            {saving ? 'Menyimpan...' : 'Simpan Preferensi'}
          </button>
        </div>
      </Section>
    </div>
  )
}
