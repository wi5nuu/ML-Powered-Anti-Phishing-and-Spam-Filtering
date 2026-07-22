import { useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2, ArrowLeft, Camera, Activity, Shield, Mail, Calendar, Edit2, Check, X, Lock, Eye, EyeOff } from 'lucide-react'
import GmailShell from '../components/layout/GmailShell'
import { useProfile, useUploadProfileAvatar, useUpdateProfile, useChangePassword } from '../api/profile'
import { getActiveMailbox, getActiveMailboxId } from '../utils/mailbox'
import { avatarColor, avatarText, hasUploadedAvatar } from '../utils/avatar'
import { useTranslation } from '../i18n/context'
import { useToast } from '../hooks/useToast'
import styles from './ProfilePage.module.css'

const MAX_AVATAR_BYTES = 1024 * 1024
const ALLOWED_AVATAR_TYPES = new Set(['image/jpeg', 'image/png', 'image/gif', 'image/webp'])

function readImageSize(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const image = new Image()
    image.onload = () => {
      URL.revokeObjectURL(url)
      resolve({ width: image.naturalWidth, height: image.naturalHeight })
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('invalid-image'))
    }
    image.src = url
  })
}

export default function ProfilePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const fileInputRef = useRef(null)
  const { showToast } = useToast()

  // Avatar state
  const [avatarError, setAvatarError] = useState('')

  // Edit profile state
  const [editingName, setEditingName] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [editCurrentPw, setEditCurrentPw] = useState('')
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState('')

  // Change password state
  const [changingPw, setChangingPw] = useState(false)
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [showCurrentPw, setShowCurrentPw] = useState(false)
  const [showNewPw, setShowNewPw] = useState(false)
  const [showConfirmPw, setShowConfirmPw] = useState(false)
  const [pwSaving, setPwSaving] = useState(false)
  const [pwError, setPwError] = useState('')

  const activeMailbox = getActiveMailbox(searchParams)
  const activeMailboxId = getActiveMailboxId(searchParams)
  const { data: profile, isLoading: profileLoading, refetch } = useProfile(activeMailboxId)
  const uploadAvatar = useUploadProfileAvatar()
  const updateProfile = useUpdateProfile()
  const changePassword = useChangePassword()

  const displayEmail = profile?.mailbox_email || activeMailbox || profile?.email || profile?.username || t('common.na')
  const isMailboxProfile = Boolean(profile?.mailbox_email || activeMailboxId)
  const displayName = isMailboxProfile
    ? (profile?.sender_name || displayEmail)
    : (profile?.name || profile?.username || displayEmail)
  const avatarKey = isMailboxProfile ? displayEmail : profile?.username || displayName
  const displayInitial = avatarText(avatarKey || 'U', isMailboxProfile ? 1 : 2)
  const avatarUrl = profile?.avatar_url || ''
  const uploadedAvatar = hasUploadedAvatar(avatarUrl)
  const roleLabel = profile?.role || t('common.na')

  const handleAvatarChange = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    setAvatarError('')
    if (!ALLOWED_AVATAR_TYPES.has(file.type)) {
      setAvatarError('Format gambar tidak didukung. Gunakan JPEG, PNG, GIF, atau WEBP.')
      return
    }
    if (file.size > MAX_AVATAR_BYTES) {
      setAvatarError('Ukuran gambar maksimal 1 MB.')
      return
    }
    try {
      await readImageSize(file)
    } catch {
      setAvatarError('File gambar tidak valid.')
      return
    }
    try {
      await uploadAvatar.mutateAsync(
        activeMailboxId ? { file, mailboxId: activeMailboxId } : file
      )
      showToast('Avatar berhasil diperbarui', 'success')
      refetch()
    } catch (err) {
      setAvatarError(err?.response?.data?.detail || 'Gagal mengunggah avatar.')
    }
  }

  const startEditName = () => {
    setNewUsername(profile?.username || '')
    setEditCurrentPw('')
    setEditError('')
    setEditingName(true)
  }

  const cancelEditName = () => {
    setEditingName(false)
    setEditError('')
    setEditCurrentPw('')
  }

  const saveEditName = async () => {
    if (!newUsername.trim()) {
      setEditError('Username tidak boleh kosong.')
      return
    }
    if (!editCurrentPw) {
      setEditError('Masukkan password saat ini untuk konfirmasi.')
      return
    }
    setEditSaving(true)
    setEditError('')
    try {
      await updateProfile.mutateAsync({
        username: newUsername.trim(),
        current_password: editCurrentPw,
      })
      showToast('Profil berhasil diperbarui', 'success')
      setEditingName(false)
      refetch()
    } catch (err) {
      setEditError(err?.response?.data?.detail || 'Gagal memperbarui profil.')
    } finally {
      setEditSaving(false)
    }
  }

  const startChangePw = () => {
    setCurrentPw('')
    setNewPw('')
    setConfirmPw('')
    setPwError('')
    setChangingPw(true)
  }

  const cancelChangePw = () => {
    setChangingPw(false)
    setPwError('')
  }

  const saveChangePw = async () => {
    if (!currentPw) { setPwError('Masukkan password saat ini.'); return }
    if (!newPw) { setPwError('Masukkan password baru.'); return }
    if (newPw.length < 4) { setPwError('Password baru minimal 4 karakter.'); return }
    if (newPw !== confirmPw) { setPwError('Konfirmasi password tidak cocok.'); return }
    setPwSaving(true)
    setPwError('')
    try {
      await changePassword.mutateAsync({ current_password: currentPw, new_password: newPw })
      showToast('Password berhasil diubah', 'success')
      setChangingPw(false)
    } catch (err) {
      setPwError(err?.response?.data?.detail || 'Gagal mengubah password.')
    } finally {
      setPwSaving(false)
    }
  }

  if (profileLoading) {
    return (
      <GmailShell>
        <div className={styles.loading}>
          <Loader2 size={18} className={styles.spin} />
          Memuat profil...
        </div>
      </GmailShell>
    )
  }

  return (
    <GmailShell>
      <div className={styles.wrap}>
        {/* Header */}
        <div className={styles.header}>
          <button className={styles.backBtn} onClick={() => navigate(-1)} title="Kembali">
            <ArrowLeft size={18} />
          </button>
          <div className={styles.headerInfo}>
            <h1 className={styles.title}>Profil</h1>
            <p className={styles.subtitle}>Kelola informasi akun Anda</p>
          </div>
        </div>

        <div className={styles.layout}>
          {/* Profile card */}
          <div className={styles.card}>
            {/* Avatar + name */}
            <div className={styles.profileHeader}>
              <div className={styles.avatarField}>
                <button
                  className={styles.profileAvatar}
                  style={{ background: uploadedAvatar ? 'transparent' : avatarColor(avatarKey || 'U') }}
                  onClick={() => fileInputRef.current?.click()}
                  title="Ganti avatar"
                  type="button"
                >
                  {uploadedAvatar
                    ? <img src={avatarUrl} alt="avatar" style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }} />
                    : <span style={{ fontSize: '1.3rem', fontWeight: 600, color: '#fff' }}>{displayInitial}</span>
                  }
                </button>
                <button
                  className={styles.cameraBtn}
                  onClick={() => fileInputRef.current?.click()}
                  title="Ganti foto"
                  type="button"
                >
                  <Camera size={13} />
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/gif,image/webp"
                  style={{ display: 'none' }}
                  onChange={handleAvatarChange}
                />
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                {/* Username edit inline */}
                {editingName ? (
                  <div className={styles.editRow}>
                    <input
                      className={styles.editInput}
                      value={newUsername}
                      onChange={e => setNewUsername(e.target.value)}
                      placeholder="Username baru"
                      autoFocus
                    />
                    <input
                      className={styles.editInput}
                      type="password"
                      value={editCurrentPw}
                      onChange={e => setEditCurrentPw(e.target.value)}
                      placeholder="Password saat ini"
                    />
                    {editError && <p className={styles.fieldError}>{editError}</p>}
                    <div className={styles.editActions}>
                      <button className={styles.saveBtn} onClick={saveEditName} disabled={editSaving}>
                        {editSaving ? <Loader2 size={14} className={styles.spin} /> : <Check size={14} />}
                        Simpan
                      </button>
                      <button className={styles.cancelBtn} onClick={cancelEditName}>
                        <X size={14} /> Batal
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className={styles.nameRow}>
                    <span className={styles.displayName}>{displayName}</span>
                    {!isMailboxProfile && (
                      <button className={styles.editIconBtn} onClick={startEditName} title="Edit username">
                        <Edit2 size={14} />
                      </button>
                    )}
                  </div>
                )}
                <span className={styles.roleChip}>{roleLabel}</span>
              </div>
            </div>

            {avatarError && <p className={styles.fieldError} style={{ marginTop: 8 }}>{avatarError}</p>}
            {uploadAvatar.isPending && <p className={styles.fieldHint}>Mengunggah avatar...</p>}

            <div className={styles.divider} />

            {/* Info rows */}
            <div className={styles.infoGrid}>
              <div className={styles.infoRow}>
                <Mail size={15} className={styles.infoIcon} />
                <span className={styles.infoLabel}>Email</span>
                <span className={styles.infoValue}>{displayEmail}</span>
              </div>

              <div className={styles.infoRow}>
                <Shield size={15} className={styles.infoIcon} />
                <span className={styles.infoLabel}>Role</span>
                <span className={styles.infoValue}>{roleLabel}</span>
              </div>

              <div className={styles.infoRow}>
                <Calendar size={15} className={styles.infoIcon} />
                <span className={styles.infoLabel}>{t('profile.memberSince')}</span>
                <span className={styles.infoValue}>
                  {profile?.created_at
                    ? new Date(profile.created_at).toLocaleDateString('id-ID', {
                        year: 'numeric', month: 'long', day: 'numeric',
                      })
                    : t('common.na')}
                </span>
              </div>

              <div className={styles.infoRow}>
                <Activity size={15} className={styles.infoIcon} />
                <span className={styles.infoLabel}>{t('users.status')}</span>
                <span className={`${styles.infoValue} ${profile?.is_active ? styles.activeStatus : styles.inactiveStatus}`}>
                  {profile?.is_active ? t('label.active') : t('label.inactive')}
                </span>
              </div>
            </div>
          </div>

          {/* Change password card - only for dashboard users (not mailbox) */}
          {!isMailboxProfile && (
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <Lock size={16} />
                Ganti Password
              </div>

              {!changingPw ? (
                <button className={styles.startEditBtn} onClick={startChangePw}>
                  <Lock size={14} /> Ubah Password
                </button>
              ) : (
                <div className={styles.pwForm}>
                  {/* Current password */}
                  <div className={styles.pwField}>
                    <label className={styles.pwLabel}>Password saat ini</label>
                    <div className={styles.pwInputWrap}>
                      <input
                        className={styles.editInput}
                        type={showCurrentPw ? 'text' : 'password'}
                        value={currentPw}
                        onChange={e => setCurrentPw(e.target.value)}
                        placeholder="Password saat ini"
                        autoFocus
                      />
                      <button type="button" className={styles.eyeBtn} onClick={() => setShowCurrentPw(v => !v)}>
                        {showCurrentPw ? <EyeOff size={15} /> : <Eye size={15} />}
                      </button>
                    </div>
                  </div>

                  {/* New password */}
                  <div className={styles.pwField}>
                    <label className={styles.pwLabel}>Password baru</label>
                    <div className={styles.pwInputWrap}>
                      <input
                        className={styles.editInput}
                        type={showNewPw ? 'text' : 'password'}
                        value={newPw}
                        onChange={e => setNewPw(e.target.value)}
                        placeholder="Minimal 4 karakter"
                      />
                      <button type="button" className={styles.eyeBtn} onClick={() => setShowNewPw(v => !v)}>
                        {showNewPw ? <EyeOff size={15} /> : <Eye size={15} />}
                      </button>
                    </div>
                  </div>

                  {/* Confirm password */}
                  <div className={styles.pwField}>
                    <label className={styles.pwLabel}>Konfirmasi password baru</label>
                    <div className={styles.pwInputWrap}>
                      <input
                        className={styles.editInput}
                        type={showConfirmPw ? 'text' : 'password'}
                        value={confirmPw}
                        onChange={e => setConfirmPw(e.target.value)}
                        placeholder="Ulangi password baru"
                      />
                      <button type="button" className={styles.eyeBtn} onClick={() => setShowConfirmPw(v => !v)}>
                        {showConfirmPw ? <EyeOff size={15} /> : <Eye size={15} />}
                      </button>
                    </div>
                  </div>

                  {pwError && <p className={styles.fieldError}>{pwError}</p>}

                  <div className={styles.editActions}>
                    <button className={styles.saveBtn} onClick={saveChangePw} disabled={pwSaving}>
                      {pwSaving ? <Loader2 size={14} className={styles.spin} /> : <Check size={14} />}
                      Simpan Password
                    </button>
                    <button className={styles.cancelBtn} onClick={cancelChangePw}>
                      <X size={14} /> Batal
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </GmailShell>
  )
}
