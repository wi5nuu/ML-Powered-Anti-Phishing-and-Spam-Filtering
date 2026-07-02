import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  User, Shield, Key, Clock, Copy, Check, Eye, EyeOff,
  Plus, Trash2, Loader2, Activity, ArrowLeft, Mail, Calendar
} from 'lucide-react'
import GmailShell from '../components/layout/GmailShell'
import { useMe } from '../api/auth'
import {
  useProfile, useChangePassword,
  useApiKeys, useCreateApiKey, useDeleteApiKey,
  useActivity
} from '../api/profile'
import { useToast } from '../hooks/useToast'
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
  const { showToast } = useToast()
  const { data: me } = useMe()
  const { data: profile, isLoading: profileLoading } = useProfile()
  const { data: apiKeys, isLoading: keysLoading } = useApiKeys()
  const { data: activity, isLoading: activityLoading } = useActivity()
  const { mutate: changePassword, isPending: changingPw } = useChangePassword()
  const { mutate: createKey, isPending: creatingKey } = useCreateApiKey()
  const { mutate: deleteKey } = useDeleteApiKey()

  const [pwSection, setPwSection] = useState(false)
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [pwError, setPwError] = useState('')

  const [keyName, setKeyName] = useState('')
  const [newKeyValue, setNewKeyValue] = useState(null)

  const [copied, setCopied] = useState(false)

  const handleChangePassword = (e) => {
    e.preventDefault()
    setPwError('')
    if (newPw !== confirmPw) {
      setPwError('New passwords do not match')
      return
    }
    if (newPw.length < 4) {
      setPwError('Password must be at least 4 characters')
      return
    }
    changePassword({ current_password: currentPw, new_password: newPw }, {
      onSuccess: () => {
        showToast('Password changed successfully', 'success')
        setCurrentPw('')
        setNewPw('')
        setConfirmPw('')
        setPwSection(false)
      },
      onError: (err) => {
        setPwError(err.response?.data?.detail || 'Failed to change password')
      },
    })
  }

  const handleCreateKey = () => {
    if (!keyName.trim()) return
    createKey({ name: keyName.trim(), rate_limit: 100 }, {
      onSuccess: (res) => {
        setNewKeyValue(res.data.key)
        setKeyName('')
        showToast('API key created. Copy it now — you won\'t see it again.', 'info')
      },
      onError: () => showToast('Failed to create API key', 'error'),
    })
  }

  const handleDeleteKey = (keyId) => {
    if (!window.confirm('Revoke this API key? This cannot be undone.')) return
    deleteKey(keyId, {
      onSuccess: () => showToast('API key revoked', 'success'),
      onError: () => showToast('Failed to revoke key', 'error'),
    })
  }

  const handleCopyKey = () => {
    if (newKeyValue) {
      navigator.clipboard.writeText(newKeyValue)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

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
        {/* Header */}
        <div className={styles.header}>
          <button className={styles.backBtn} onClick={() => navigate(-1)}>
            <ArrowLeft size={18} />
          </button>
          <div className={styles.headerInfo}>
            <h1 className={styles.title}>Account Settings</h1>
            <p className={styles.subtitle}>Manage your profile, security, and API keys</p>
          </div>
        </div>

        <div className={styles.layout}>
          {/* Left Column: Profile Info + Password */}
          <div className={styles.colLeft}>
            {/* Profile Card */}
            <div className={styles.card}>
              <div className={styles.profileHeader}>
                <div className={styles.profileAvatar}>
                  {displayInitial}
                </div>
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
                    ? new Date(profile.created_at).toLocaleDateString('id-ID', { year: 'numeric', month: 'long', day: 'numeric' })
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

            {/* Change Password */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <Key size={18} />
                <span>Security</span>
                {!pwSection && (
                  <button className={styles.btnGhost} onClick={() => setPwSection(true)}>
                    Change Password
                  </button>
                )}
              </div>
              {pwSection && (
                <form onSubmit={handleChangePassword} className={styles.pwForm}>
                  <div className={styles.field}>
                    <label>Current Password</label>
                    <div className={styles.pwInputWrap}>
                      <input
                        type={showPw ? 'text' : 'password'}
                        value={currentPw}
                        onChange={(e) => setCurrentPw(e.target.value)}
                        required
                        placeholder="Enter current password"
                      />
                      <button type="button" className={styles.pwToggle} onClick={() => setShowPw(!showPw)}>
                        {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>
                  <div className={styles.field}>
                    <label>New Password</label>
                    <input
                      type="password"
                      value={newPw}
                      onChange={(e) => setNewPw(e.target.value)}
                      required
                      placeholder="Min. 4 characters"
                    />
                  </div>
                  <div className={styles.field}>
                    <label>Confirm New Password</label>
                    <input
                      type="password"
                      value={confirmPw}
                      onChange={(e) => setConfirmPw(e.target.value)}
                      required
                      placeholder="Re-enter new password"
                    />
                  </div>
                  {pwError && <div className={styles.fieldError}>{pwError}</div>}
                  <div className={styles.pwActions}>
                    <button type="button" className={styles.btnOutline} onClick={() => { setPwSection(false); setPwError('') }}>
                      Cancel
                    </button>
                    <button type="submit" className={styles.btnPrimary} disabled={changingPw}>
                      {changingPw ? <Loader2 size={15} className={styles.spin} /> : null}
                      {changingPw ? 'Updating...' : 'Update Password'}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>

          {/* Right Column: API Keys + Activity */}
          <div className={styles.colRight}>
            {/* API Keys */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <Key size={18} />
                <span>API Keys</span>
              </div>

              {newKeyValue && (
                <div className={styles.newKeyBanner}>
                  <div className={styles.newKeyLabel}>New API Key Created</div>
                  <div className={styles.newKeyValue}>
                    <code>{newKeyValue}</code>
                    <button className={styles.btnGhost} onClick={handleCopyKey}>
                      {copied ? <Check size={15} /> : <Copy size={15} />}
                      {copied ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                  <div className={styles.newKeyWarning}>
                    Copy this key now. You won't be able to see it again.
                  </div>
                </div>
              )}

              <div className={styles.keyList}>
                {keysLoading ? (
                  <div className={styles.loadingRow}><Loader2 size={16} className={styles.spin} /> Loading...</div>
                ) : apiKeys?.length === 0 ? (
                  <div className={styles.emptyRow}>No API keys yet.</div>
                ) : (
                  apiKeys?.map((k) => (
                    <div key={k.id} className={styles.keyRow}>
                      <div className={styles.keyInfo}>
                        <span className={styles.keyName}>{k.name}</span>
                        <span className={styles.keyMeta}>
                          {k.is_active ? 'Active' : 'Inactive'} &middot; {k.rate_limit} req/min
                        </span>
                      </div>
                      <button
                        className={styles.btnDangerGhost}
                        onClick={() => handleDeleteKey(k.id)}
                        title="Revoke key"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))
                )}
              </div>

              <div className={styles.keyCreate}>
                <input
                  type="text"
                  placeholder="Key name (e.g. CI/CD Pipeline)"
                  value={keyName}
                  onChange={(e) => setKeyName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCreateKey()}
                />
                <button className={styles.btnPrimary} onClick={handleCreateKey} disabled={creatingKey || !keyName.trim()}>
                  {creatingKey ? <Loader2 size={15} className={styles.spin} /> : <Plus size={15} />}
                  {creatingKey ? 'Creating...' : 'Create Key'}
                </button>
              </div>
            </div>

            {/* Recent Activity */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <Activity size={18} />
                <span>Recent Activity</span>
              </div>
              <div className={styles.activityList}>
                {activityLoading ? (
                  <div className={styles.loadingRow}><Loader2 size={16} className={styles.spin} /> Loading...</div>
                ) : activity?.length === 0 ? (
                  <div className={styles.emptyRow}>No recent activity.</div>
                ) : (
                  activity?.map((a, i) => (
                    <div key={i} className={styles.activityRow}>
                      <div className={styles.activityDot} />
                      <div className={styles.activityContent}>
                        <span className={styles.activityAction}>{a.action}</span>
                        {a.details && <span className={styles.activityDetail}>{a.details}</span>}
                      </div>
                      <span className={styles.activityTime}>
                        {a.created_at ? new Date(a.created_at).toLocaleString('id-ID', { dateStyle: 'short', timeStyle: 'short' }) : ''}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </GmailShell>
  )
}
