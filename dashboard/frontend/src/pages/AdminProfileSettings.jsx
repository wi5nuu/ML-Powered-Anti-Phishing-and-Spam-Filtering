import { useEffect, useRef, useState } from 'react'
import { Camera, CheckCircle2, Eye, EyeOff, Loader2, LockKeyhole, Save, Shield, UserRound } from 'lucide-react'
import { useProfile, useUpdateProfile, useUploadProfileAvatar } from '../api/profile'
import { useTranslation } from '../i18n/context'
import { avatarColor, avatarText, hasUploadedAvatar, readAvatarDimensions } from '../utils/avatar'
import styles from './AdminProfileSettings.module.css'

const MAX_AVATAR_BYTES = 1024 * 1024
const ALLOWED_AVATAR_TYPES = new Set(['image/jpeg', 'image/png', 'image/gif', 'image/webp'])
const USERNAME_PATTERN = /^[A-Za-z0-9._-]{3,64}$/

function PasswordField({ id, label, hint, value, onChange, visible, onToggle, autoComplete }) {
  return (
    <label className={styles.field} htmlFor={id}>
      <span>{label}</span>
      <div className={styles.passwordWrap}>
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          autoComplete={autoComplete}
        />
        <button type="button" onClick={onToggle} aria-label={visible ? 'Sembunyikan password' : 'Tampilkan password'}>
          {visible ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
      <small>{hint}</small>
    </label>
  )
}

export default function AdminProfileSettings({ superadminOnly = false }) {
  const { t } = useTranslation()
  const { data: profile, isLoading } = useProfile()
  const updateProfile = useUpdateProfile()
  const uploadAvatar = useUploadProfileAvatar()
  const fileInput = useRef(null)
  const [username, setUsername] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [notice, setNotice] = useState(null)
  const [avatarFailed, setAvatarFailed] = useState(false)

  useEffect(() => {
    if (profile?.username) setUsername(profile.username)
  }, [profile?.username])

  const fail = (message) => setNotice({ type: 'error', message })

  const handleAvatar = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setNotice(null)
    if (!ALLOWED_AVATAR_TYPES.has(file.type)) return fail(t('profile.avatarTypeError'))
    if (file.size > MAX_AVATAR_BYTES) return fail(t('profile.avatarSizeError'))
    try {
      const dimensions = await readAvatarDimensions(file)
      if (dimensions.width !== dimensions.height) return fail(t('profile.avatarRatioError'))
    } catch {
      return fail(t('profile.avatarDimError'))
    }
    uploadAvatar.mutate({ file }, {
      onSuccess: () => {
        setAvatarFailed(false)
        setNotice({ type: 'success', message: t('settings.avatarUpdated') })
      },
      onError: (error) => fail(error.response?.data?.detail || t('profile.avatarUploadError')),
    })
  }

  const submit = (event) => {
    event.preventDefault()
    setNotice(null)
    const cleanUsername = username.trim()
    if (!USERNAME_PATTERN.test(cleanUsername)) return fail(t('settings.usernameValidation'))
    if (newPassword) {
      if (!currentPassword) return fail(t('msg.settings.accountPasswordRequired'))
      const strong = newPassword.length >= 8
        && /[A-Z]/.test(newPassword)
        && /[a-z]/.test(newPassword)
        && /[0-9]/.test(newPassword)
      if (!strong) return fail(t('settings.passwordValidation'))
      if (newPassword !== confirmPassword) return fail(t('msg.settings.accountPasswordMismatch'))
    }
    updateProfile.mutate({
      username: cleanUsername,
      current_password: currentPassword,
      new_password: newPassword,
    }, {
      onSuccess: () => {
        setCurrentPassword('')
        setNewPassword('')
        setConfirmPassword('')
        setNotice({ type: 'success', message: t('msg.settings.accountUpdated') })
      },
      onError: (error) => fail(error.response?.data?.detail || t('msg.settings.accountUpdateError')),
    })
  }

  if (isLoading) {
    return <div className={styles.loading}><Loader2 className={styles.spin} size={22} /> {t('profile.loading')}</div>
  }

  const avatarUrl = profile?.avatar_url || ''
  const uploadedAvatar = hasUploadedAvatar(avatarUrl) && !avatarFailed
  const avatarKey = profile?.username || 'A'

  return (
    <div className={`${styles.wrap} ${superadminOnly ? styles.superadminWrap : ''}`}>
      {!superadminOnly && <div className={styles.pageHeader}>
        <h1><UserRound size={22} /> {t('settings.accountTitle')}</h1>
        <p>{t('settings.profileSubtitle')}</p>
      </div>}

      {notice && (
        <div className={`${styles.notice} ${notice.type === 'success' ? styles.success : styles.error}`}>
          {notice.type === 'success' && <CheckCircle2 size={17} />}
          {notice.message}
        </div>
      )}

      <div className={`${styles.grid} ${superadminOnly ? styles.superadminGrid : ''}`}>
        <section className={styles.card}>
          <div className={styles.cardTitle}><UserRound size={18} /> {t('settings.profileInfo')}</div>
          <div className={styles.identity}>
            <button
              type="button"
              className={styles.avatar}
              style={!uploadedAvatar ? { background: avatarColor(avatarKey) } : undefined}
              onClick={() => fileInput.current?.click()}
              disabled={uploadAvatar.isPending}
              title={t('profile.uploadAvatar')}
            >
              {uploadedAvatar
                ? <img src={avatarUrl} alt="" onError={() => setAvatarFailed(true)} />
                : avatarText(avatarKey, 2)}
              <span>{uploadAvatar.isPending ? <Loader2 className={styles.spin} size={15} /> : <Camera size={15} />}</span>
            </button>
            <input
              ref={fileInput}
              type="file"
              accept="image/png,image/jpeg,image/gif,image/webp"
              hidden
              onChange={handleAvatar}
            />
            <div>
              <strong>{profile?.username}</strong>
              <p>{profile?.role === 'superadmin' ? 'Superadmin' : 'Admin'}</p>
              <button type="button" className={styles.changeAvatar} onClick={() => fileInput.current?.click()}>
                {t('settings.changeAvatar')}
              </button>
            </div>
          </div>
          <dl className={styles.details}>
            <div><dt>{t('users.role')}</dt><dd className={styles.role}><Shield size={14} /> {profile?.role || t('common.na')}</dd></div>
            <div><dt>{t('users.status')}</dt><dd>{profile?.is_active ? t('label.active') : t('label.inactive')}</dd></div>
            <div><dt>{t('profile.memberSince')}</dt><dd>{profile?.created_at ? new Date(profile.created_at).toLocaleDateString('id-ID') : t('common.na')}</dd></div>
          </dl>
          <p className={styles.avatarHint}>{t('settings.avatarHint')}</p>
        </section>

        {!superadminOnly && <section className={styles.card}>
          <div className={styles.cardTitle}><LockKeyhole size={18} /> {t('settings.accountLogin')}</div>
          <form className={styles.form} onSubmit={submit}>
            <label className={styles.field} htmlFor="profile-username">
              <span>{t('users.username')}</span>
              <input id="profile-username" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
              <small>{t('settings.usernameHint')}</small>
            </label>
            <PasswordField id="current-password" label={t('settings.currentPassword')} hint={t('settings.currentPasswordHint')} value={currentPassword} onChange={setCurrentPassword} visible={showCurrent} onToggle={() => setShowCurrent((value) => !value)} autoComplete="current-password" />
            <PasswordField id="new-password" label={t('settings.newPassword')} hint={t('settings.passwordValidation')} value={newPassword} onChange={setNewPassword} visible={showNew} onToggle={() => setShowNew((value) => !value)} autoComplete="new-password" />
            <PasswordField id="confirm-password" label={t('settings.confirmPassword')} hint={t('settings.confirmPasswordHint')} value={confirmPassword} onChange={setConfirmPassword} visible={showConfirm} onToggle={() => setShowConfirm((value) => !value)} autoComplete="new-password" />
            <div className={styles.actions}>
              <button type="submit" disabled={updateProfile.isPending}>
                {updateProfile.isPending ? <Loader2 className={styles.spin} size={17} /> : <Save size={17} />}
                {t('settings.saveAccount')}
              </button>
            </div>
          </form>
        </section>}
      </div>
    </div>
  )
}
