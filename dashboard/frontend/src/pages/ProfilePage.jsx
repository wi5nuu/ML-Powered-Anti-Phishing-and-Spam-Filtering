import { useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2, ArrowLeft, Camera, Activity, Shield, Mail, Calendar, ClipboardList, MessageSquareText } from 'lucide-react'
import GmailShell from '../components/layout/GmailShell'
import { useProfile, useReportHistory, useUploadProfileAvatar } from '../api/profile'
import { getActiveMailbox, getActiveMailboxId, setMailboxSession } from '../utils/mailbox'
import { avatarColor, avatarText, hasUploadedAvatar, readAvatarDimensions } from '../utils/avatar'
import { useTranslation } from '../i18n/context'
import styles from './ProfilePage.module.css'

const MAX_AVATAR_BYTES = 1024 * 1024
const ALLOWED_AVATAR_TYPES = new Set(['image/jpeg', 'image/png', 'image/gif', 'image/webp'])
const REPORT_STATUS = {
  open: { label: 'Diterima', progress: 25, className: 'reportOpen' },
  in_progress: { label: 'Sedang diproses', progress: 65, className: 'reportProgress' },
  resolved: { label: 'Selesai', progress: 100, className: 'reportResolved' },
}
const REPORT_CATEGORY = {
  bug: 'Kendala sistem',
  question: 'Pertanyaan',
  access: 'Akses akun',
  false_positive: 'Kesalahan deteksi',
  other: 'Lainnya',
}

export default function ProfilePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const fileInputRef = useRef(null)
  const [avatarError, setAvatarError] = useState('')
  const activeMailbox = getActiveMailbox(searchParams)
  const activeMailboxId = getActiveMailboxId(searchParams)
  const { data: profile, isLoading: profileLoading } = useProfile(activeMailboxId)
  const { data: reports = [], isLoading: reportsLoading, isError: reportsError } = useReportHistory(activeMailboxId)
  const uploadAvatar = useUploadProfileAvatar()
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
      setAvatarError(t('profile.avatarTypeError'))
      return
    }
    if (file.size > MAX_AVATAR_BYTES) {
      setAvatarError(t('profile.avatarSizeError'))
      return
    }
    try {
      const { width, height } = await readAvatarDimensions(file)
      if (width !== height) {
        setAvatarError(t('profile.avatarRatioError'))
        return
      }
    } catch {
      setAvatarError(t('profile.avatarDimError'))
      return
    }

    uploadAvatar.mutate({ file, mailboxId: activeMailboxId }, {
      onSuccess: (response) => {
        if (activeMailboxId && displayEmail) {
          setMailboxSession({
            id: activeMailboxId,
            email: displayEmail,
            avatar_url: response?.data?.avatar_url || '',
          })
        }
      },
      onError: (error) => {
        setAvatarError(error.response?.data?.detail || t('profile.avatarUploadError'))
      },
    })
  }

  if (profileLoading) {
    return (
      <GmailShell>
        <div className={styles.loading}>
          <Loader2 size={24} className={styles.spin} />
          {t('profile.loading')}
        </div>
      </GmailShell>
    )
  }

  return (
    <GmailShell>
      <div className={styles.wrap}>
        <div className={styles.header}>
          <button className={styles.backBtn} onClick={() => navigate(-1)}>
            <ArrowLeft size={18} />
          </button>
          <div className={styles.headerInfo}>
            <h1 className={styles.title}>{t('profile.title')}</h1>
            <p className={styles.subtitle}>{t('profile.subtitle')}</p>
          </div>
        </div>

        <div className={styles.layout}>
          <div className={styles.colLeft}>
            <div className={styles.card}>
              <div className={styles.profileHeader}>
                <div className={styles.avatarField}>
                  <button
                    type="button"
                    className={styles.profileAvatar}
                    onClick={() => fileInputRef.current?.click()}
                    title={t('profile.uploadAvatar')}
                    aria-label={t('profile.uploadAvatar')}
                    disabled={uploadAvatar.isPending}
                    style={!uploadedAvatar ? { background: avatarColor(avatarKey) } : undefined}
                  >
                    {uploadedAvatar ? (
                      <img src={avatarUrl} alt="" className={styles.avatarImage} />
                    ) : (
                      displayInitial
                    )}
                    <span className={styles.avatarBadge}>
                      {uploadAvatar.isPending ? <Loader2 size={15} className={styles.spin} /> : <Camera size={15} />}
                    </span>
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/gif,image/webp"
                    className={styles.avatarInput}
                    onChange={handleAvatarChange}
                  />
                </div>
                <div>
                  <div className={styles.profileName}>{displayName}</div>
                  <div className={styles.profileEmail}>{displayEmail}</div>
                  {avatarError && <div className={styles.avatarError}>{avatarError}</div>}
                </div>
            </div>

              <div className={styles.divider} />

              {activeMailbox && (
                <div className={styles.infoRow}>
                  <Mail size={15} className={styles.infoIcon} />
                  <span className={styles.infoLabel}>{t('profile.activeEmail')}</span>
                  <span className={styles.infoValue}>{activeMailbox}</span>
                </div>
              )}

              <div className={styles.infoRow}>
                <Mail size={15} className={styles.infoIcon} />
                <span className={styles.infoLabel}>{t('profile.operatorLogin')}</span>
                <span className={styles.infoValue}>{profile?.username}</span>
              </div>

              <div className={styles.infoRow}>
                <Shield size={15} className={styles.infoIcon} />
                <span className={styles.infoLabel}>{t('users.role')}</span>
                <span className={styles.infoValue}>{roleLabel}</span>
              </div>

              <div className={styles.infoRow}>
                <Calendar size={15} className={styles.infoIcon} />
                <span className={styles.infoLabel}>{t('profile.memberSince')}</span>
                <span className={styles.infoValue}>
                  {profile?.created_at
                    ? new Date(profile.created_at).toLocaleDateString('id-ID', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
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

            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <ClipboardList size={18} />
                <div>
                  <div>Riwayat Laporan</div>
                  <div className={styles.cardSubtitle}>Progres laporan masalah yang Anda kirim</div>
                </div>
              </div>

              {reportsLoading ? (
                <div className={styles.reportState}><Loader2 size={18} className={styles.spin} /> Memuat riwayat laporan...</div>
              ) : reportsError ? (
                <div className={`${styles.reportState} ${styles.reportError}`}>Riwayat laporan gagal dimuat.</div>
              ) : reports.length === 0 ? (
                <div className={styles.reportEmpty}>
                  <ClipboardList size={28} />
                  <strong>Belum ada laporan</strong>
                  <span>Laporan yang dikirim melalui menu Lapor Masalah akan tampil di sini.</span>
                </div>
              ) : (
                <div className={styles.reportList}>
                  {reports.map((report) => {
                    const state = REPORT_STATUS[report.status] || REPORT_STATUS.open
                    return (
                      <article className={styles.reportItem} key={report.id}>
                        <div className={styles.reportTopRow}>
                          <div className={styles.reportIdentity}>
                            <span className={styles.reportNumber}>Laporan #{report.id}</span>
                            <h3>{report.subject}</h3>
                          </div>
                          <span className={`${styles.reportBadge} ${styles[state.className]}`}>{state.label}</span>
                        </div>
                        <div className={styles.reportMeta}>
                          <span>{REPORT_CATEGORY[report.category] || REPORT_CATEGORY.other}</span>
                          <span>•</span>
                          <time>{new Date(report.created_at).toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' })}</time>
                        </div>
                        <p className={styles.reportMessage}>{report.message}</p>
                        <div className={styles.progressHeader}>
                          <span>Progres penanganan</span>
                          <strong>{state.progress}%</strong>
                        </div>
                        <div className={styles.progressTrack} aria-label={`Progres ${state.progress}%`}>
                          <span style={{ width: `${state.progress}%` }} />
                        </div>
                        {report.admin_reply && (
                          <div className={styles.adminReply}>
                            <MessageSquareText size={16} />
                            <div><strong>Balasan admin</strong><p>{report.admin_reply}</p></div>
                          </div>
                        )}
                      </article>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </GmailShell>
  )
}
