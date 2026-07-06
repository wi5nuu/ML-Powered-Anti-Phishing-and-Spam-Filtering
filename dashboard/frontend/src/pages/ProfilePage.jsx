import { useNavigate, useSearchParams } from 'react-router-dom'
import { Shield, Loader2, Activity, ArrowLeft, Mail, Calendar } from 'lucide-react'
import GmailShell from '../components/layout/GmailShell'
import { useMe } from '../api/auth'
import { useProfile } from '../api/profile'
import { getActiveMailbox } from '../utils/mailbox'
import styles from './ProfilePage.module.css'

const ROLE_LABELS = {
  superadmin: 'Super Admin',
  admin: 'Admin',
  user: 'User',
}

export default function ProfilePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { data: me } = useMe()
  const { data: profile, isLoading: profileLoading } = useProfile()

  const role = me?.user?.role || 'user'
  const roleLabel = ROLE_LABELS[role] || role
  const activeMailbox = getActiveMailbox(searchParams)
  const displayName = activeMailbox || profile?.username || 'N/A'
  const displayRole = activeMailbox ? 'Mailbox perusahaan' : roleLabel
  const displayInitial = (displayName || 'U')[0].toUpperCase()

  if (profileLoading) {
    return (
      <GmailShell>
        <div className={styles.loading}>
          <Loader2 size={24} className={styles.spin} />
          Loading profile...
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
            <h1 className={styles.title}>Account Settings</h1>
            <p className={styles.subtitle}>Manage your profile</p>
          </div>
        </div>

        <div className={styles.layout}>
          <div className={styles.colLeft}>
            <div className={styles.card}>
              <div className={styles.profileHeader}>
                <div className={styles.profileAvatar}>{displayInitial}</div>
                <div>
                  <div className={styles.profileName}>{displayName}</div>
                  <div className={styles.profileRole}>
                    <Shield size={14} />
                    {displayRole}
                  </div>
                </div>
              </div>

              <div className={styles.divider} />

              {activeMailbox && (
                <div className={styles.infoRow}>
                  <Mail size={15} className={styles.infoIcon} />
                  <span className={styles.infoLabel}>Email Aktif</span>
                  <span className={styles.infoValue}>{activeMailbox}</span>
                </div>
              )}

              <div className={styles.infoRow}>
                <Mail size={15} className={styles.infoIcon} />
                <span className={styles.infoLabel}>Operator Login</span>
                <span className={styles.infoValue}>{profile?.username}</span>
              </div>

              <div className={styles.infoRow}>
                <Shield size={15} className={styles.infoIcon} />
                <span className={styles.infoLabel}>Role</span>
                <span className={styles.infoValue}>{roleLabel}</span>
              </div>

              <div className={styles.infoRow}>
                <Calendar size={15} className={styles.infoIcon} />
                <span className={styles.infoLabel}>Member since</span>
                <span className={styles.infoValue}>
                  {profile?.created_at
                    ? new Date(profile.created_at).toLocaleDateString('id-ID', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                      })
                    : 'N/A'}
                </span>
              </div>

              <div className={styles.infoRow}>
                <Activity size={15} className={styles.infoIcon} />
                <span className={styles.infoLabel}>Status</span>
                <span className={`${styles.infoValue} ${profile?.is_active ? styles.activeStatus : styles.inactiveStatus}`}>
                  {profile?.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </GmailShell>
  )
}
