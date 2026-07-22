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
import { useTranslation } from '../i18n/context'
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

function EditableList({ items, onAdd, onRemove, placeholder, id }) {
  const { t } = useTranslation()
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
          <span className={styles.listEmpty}>{t('settings.noItems')}</span>
        )}
        {items.map((item, i) => (
          <div key={i} className={styles.listChip}>
            <span>{item}</span>
            <button
              className={styles.chipRemove}
              onClick={() => onRemove(i)}
              title={`${t('common.delete')} ${item}`}
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
          <Plus size={14} /> {t('common.add')}
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
  protected_domains: ['lodaya.id', 'lodayatech.id', 'lodaya.co.id'],
  whitelist_senders: [],
  admin_alert_email: '',
  max_quarantine_days: 30,
}

export default function SettingsPage() {
  const { t } = useTranslation()
  const { showToast: addToast } = useToast()
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
  const isMailbox = role === 'mailbox'
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
    const wsum = local.fusion_ml_weight + local.fusion_sa_weight + local.fusion_anomaly_weight
    if (Math.abs(wsum - 1.0) > 0.05) {
      addToast(`${t('msg.settings.weightSum')} (${(wsum * 100).toFixed(0)}%)`, 'warning')
      return
    }
    if (local.threshold_warn >= local.threshold_quarantine) {
      addToast(t('msg.settings.quarantineGtWarn'), 'warning')
      return
    }
    saveSettings(local, {
      onSuccess: () => {
        addToast(t('msg.settings.saved'), 'success')
        setDirty(false)
      },
      onError: (err) => {
        const msg = err?.response?.data?.detail || t('msg.settings.saveError')
        addToast(msg, 'error')
      },
    })
  }

  const handleReset = () => {
    if (!window.confirm(t('msg.settings.resetConfirm'))) return
    setLocal(DEFAULTS)
    setDirty(true)
    addToast(t('msg.settings.resetDone'), 'info')
  }

  const handleTestImap = () => {
    testImap(undefined, {
      onSuccess: (data) => {
        if (data?.data?.ok) addToast(data.data.message, 'success')
        else addToast(data?.data?.message || t('msg.settings.imapTestFail'), 'error')
      },
      onError: () => addToast(t('msg.settings.imapTestError'), 'error'),
    })
  }

  const handleSaveAccount = () => {
    if (!currentPassword) {
      addToast(t('msg.settings.accountPasswordRequired'), 'warning')
      return
    }
    if (newPassword && newPassword !== confirmPassword) {
      addToast(t('msg.settings.accountPasswordMismatch'), 'warning')
      return
    }
    updateProfile({
      username: accountUsername,
      current_password: currentPassword,
      new_password: newPassword,
    }, {
      onSuccess: () => {
        addToast(t('msg.settings.accountUpdated'), 'success')
        setCurrentPassword('')
        setNewPassword('')
        setConfirmPassword('')
      },
      onError: (err) => {
        addToast(err?.response?.data?.detail || t('msg.settings.accountUpdateError'), 'error')
      },
    })
  }

  const accountSection = !isMailbox ? (
    <Section icon={User} title={t('settings.accountLogin')}>
      <FieldRow label={t('users.username')} hint={t('settings.usernameHint')}>
        <input
          className={styles.input}
          value={accountUsername}
          onChange={(e) => setAccountUsername(e.target.value)}
          placeholder={t('users.username')}
        />
      </FieldRow>
      <FieldRow label={t('settings.currentPassword')} hint={t('settings.currentPasswordHint')}>
        <input
          className={styles.input}
          type="password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          placeholder={t('settings.currentPassword')}
        />
      </FieldRow>
      <FieldRow label={t('settings.newPassword')} hint={t('settings.newPasswordHint')}>
        <input
          className={styles.input}
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          placeholder={t('settings.newPassword')}
        />
      </FieldRow>
      <FieldRow label={t('settings.confirmPassword')} hint={t('settings.confirmPasswordHint')}>
        <input
          className={styles.input}
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          placeholder={t('settings.confirmPassword')}
        />
      </FieldRow>
      <div className={styles.sectionActions}>
        <button className={styles.btnPrimary} onClick={handleSaveAccount} disabled={isUpdatingProfile}>
          {isUpdatingProfile ? <Loader2 size={15} className={styles.spin} /> : <Save size={15} />}
          {isUpdatingProfile ? t('common.saving') : t('settings.saveAccount')}
        </button>
      </div>
    </Section>
  ) : null

  if (meLoading || isLoading) {
    return (
      <GmailShell>
        <div className={styles.loading}>
          <Loader2 size={24} className={styles.spin} />
          {t('settings.loading')}
        </div>
      </GmailShell>
    )
  }

  if (!isAdmin && !isSuper) {
    return (
      <GmailShell>
        <div className={styles.wrap}>
          <div className={styles.header}>
            <div className={styles.headerLeft}>
              <h1 className={styles.title}><Settings size={22} /> {t('settings.accountTitle')}</h1>
              <p className={styles.subtitle}>{t('settings.accountSubtitle')}</p>
            </div>
          </div>

          <div className={styles.layoutBottom}>
            {activeMailbox && (
              <Section icon={Mail} title={t('settings.activeMailbox')}>
                <FieldRow label={t('profile.activeEmail')} hint={t('settings.activeEmailHint')}>
                  <strong className={styles.readOnlyValue}>{activeMailbox}</strong>
                </FieldRow>
                <FieldRow label={t('settings.mailboxDomain')} hint={t('settings.mailboxDomainHint')}>
                  <strong className={styles.readOnlyValue}>@{activeMailDomain}</strong>
                </FieldRow>
                {isMailbox && (
                  <div className={styles.fieldRow}>
                    <div className={styles.fieldLeft}>
                      <label className={styles.fieldLabel}>{t('settings.accessAccount')}</label>
                      <span className={styles.fieldHint}>{t('settings.accessAccountHint')}</span>
                    </div>
                  </div>
                )}
              </Section>
            )}
            {accountSection}
            <Section icon={User} title={t('settings.profileInfo')}>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}>{t('users.username')}</label>
                  <span className={styles.fieldHint}>{me?.user?.username || '-'}</span>
                </div>
                <div className={styles.fieldRight}>
                  <button className={styles.btnOutline} onClick={() => navigate('/profile')}>
                    <User size={15} /> {t('profile.view')}
                  </button>
                </div>
              </div>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}>{t('users.role')}</label>
                  <span className={styles.fieldHint}>{me?.user?.role || '-'}</span>
                </div>
              </div>
            </Section>

            <Section icon={Bell} title={t('settings.notifPreferences')}>
              <div className={styles.fieldRow}>
                <div className={styles.fieldLeft}>
                  <label className={styles.fieldLabel}>{t('settings.notifEmail')}</label>
                  <span className={styles.fieldHint}>{t('settings.notifEmailHint')}</span>
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
                  <label className={styles.fieldLabel}>{t('settings.notifDaily')}</label>
                  <span className={styles.fieldHint}>{t('settings.notifDailyHint')}</span>
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
              {t('settings.footerNote')}
            </small>
          </div>
        </div>
      </GmailShell>
    )
  }

  if (isError) {
    return (
      <GmailShell>
        <div className={styles.error}>
          {t('settings.loadError')}
        </div>
      </GmailShell>
    )
  }

  const wsum = local.fusion_ml_weight + local.fusion_sa_weight + local.fusion_anomaly_weight

  return (
    <GmailShell>
      <div className={styles.wrap}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h1 className={styles.title}><Settings size={22} /> {t('settings.systemTitle')}</h1>
            <p className={styles.subtitle}>{t('settings.systemSubtitle')}</p>
          </div>
          <div className={styles.headerActions}>
            <button
              className={styles.btnOutline}
              onClick={handleReset}
              disabled={isSaving}
              id="settings-reset-btn"
            >
              <RefreshCw size={15} /> {t('settings.resetDefault')}
            </button>
            <button
              className={`${styles.btnPrimary} ${dirty ? styles.btnDirty : ''}`}
              onClick={handleSave}
              disabled={isSaving}
              id="settings-save-btn"
            >
              {isSaving ? <Loader2 size={15} className={styles.spin} /> : <Save size={15} />}
              {isSaving ? t('common.saving') : t('settings.saveSettings')}
            </button>
          </div>
        </div>

        {dirty && (
          <div className={styles.dirtyBanner}>
            ⚠ {t('settings.unsavedChanges')}
          </div>
        )}

        <div className={styles.layoutBottom}>
          {activeMailbox && (
            <Section icon={Mail} title={t('settings.activeMailbox')}>
              <FieldRow label={t('profile.activeEmail')} hint={t('settings.activeEmailHint')}>
                <strong className={styles.readOnlyValue}>{activeMailbox}</strong>
              </FieldRow>
              <FieldRow label={t('settings.mailboxDomain')} hint={t('settings.mailboxDomainHint')}>
                <strong className={styles.readOnlyValue}>@{activeMailDomain}</strong>
              </FieldRow>
            </Section>
          )}
          {accountSection}
          <Section icon={Lock} title={t('settings.roleAccess')}>
            <div className={styles.fieldRow}>
              <div className={styles.fieldLeft}>
                <label className={styles.fieldLabel}>{t('users.role')}</label>
                <span className={styles.fieldHint}>{me?.user?.role || '-'}</span>
              </div>
              <div className={styles.fieldRight}>
                <button className={styles.btnOutline} onClick={() => navigate('/profile')}>
                  <User size={15} /> {t('profile.view')}
                </button>
              </div>
            </div>
          </Section>
        </div>

        <div className={styles.layoutTop}>
          <Section icon={Sliders} title={t('settings.detectionThresholds')}>
            <ThresholdSlider
              label={t('settings.quarantineThreshold')}
              value={local.threshold_quarantine}
              onChange={(v) => set('threshold_quarantine', v)}
              color="var(--text-muted)"
            />
            <ThresholdSlider
              label={t('settings.warnThreshold')}
              value={local.threshold_warn}
              onChange={(v) => set('threshold_warn', v)}
              color="var(--text-muted)"
            />
            <p className={styles.hint}>
              {t('settings.thresholdHint')}
            </p>
          </Section>

          <Section icon={Sliders} title={t('settings.fusionWeights')}>
            <ThresholdSlider
              label={`${t('settings.fusionMlLabel')} ${(local.fusion_ml_weight * 100).toFixed(0)}%`}
              value={local.fusion_ml_weight}
              onChange={(v) => set('fusion_ml_weight', Math.round(v * 100) / 100)}
              color="var(--text-muted)"
            />
            <ThresholdSlider
              label={`${t('settings.fusionSaLabel')} ${(local.fusion_sa_weight * 100).toFixed(0)}%`}
              value={local.fusion_sa_weight}
              onChange={(v) => set('fusion_sa_weight', Math.round(v * 100) / 100)}
              color="var(--text-muted)"
            />
            <ThresholdSlider
              label={`${t('settings.fusionAnomalyLabel')} ${(local.fusion_anomaly_weight * 100).toFixed(0)}%`}
              value={local.fusion_anomaly_weight}
              onChange={(v) => set('fusion_anomaly_weight', Math.round(v * 100) / 100)}
              color="var(--text-muted)"
            />
            <div className={`${styles.weightSum} ${Math.abs(wsum - 1) > 0.05 ? styles.weightBad : styles.weightGood}`}>
              {t('settings.fusionTotal')} {(wsum * 100).toFixed(0)}%
              {Math.abs(wsum - 1) > 0.05 ? ` ⚠ ${t('settings.fusionMustBe100')}` : ' ✓'}
            </div>
          </Section>

          <Section icon={Wifi} title={t('settings.imapConnection')}>
            <FieldRow label={t('settings.imapHost')} hint={t('settings.imapHostHint')}>
              <input
                className={styles.input}
                type="text"
                placeholder="imap.gmail.com"
                value={local.imap_host}
                onChange={(e) => set('imap_host', e.target.value)}
                id="settings-imap-host"
              />
            </FieldRow>
            <FieldRow label={t('settings.imapPort')} hint={t('settings.imapPortHint')}>
              <input
                className={styles.input}
                type="number"
                min={1} max={65535}
                value={local.imap_port}
                onChange={(e) => set('imap_port', parseInt(e.target.value) || 993)}
                id="settings-imap-port"
              />
            </FieldRow>
            <FieldRow label={t('settings.imapUsername')} hint={t('settings.imapUsernameHint')}>
              <input
                className={styles.input}
                type="text"
                placeholder="monitor@lodaya.id"
                value={local.imap_user}
                onChange={(e) => set('imap_user', e.target.value)}
                id="settings-imap-user"
              />
            </FieldRow>
            <FieldRow label={t('settings.imapPollInterval')} hint={t('settings.imapPollIntervalHint')}>
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
                {isTesting ? t('settings.testing') : t('settings.testConnection')}
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

        <div className={styles.layoutBottom}>
          <Section icon={Shield} title={t('settings.protectedDomains')}>
            <p className={styles.hint}>
              {t('settings.protectedDomainsHint')}
            </p>
            <EditableList
              id="settings-domains"
              items={local.protected_domains || []}
              onAdd={(v) => set('protected_domains', [...(local.protected_domains || []), v])}
              onRemove={(i) => set('protected_domains', local.protected_domains.filter((_, idx) => idx !== i))}
              placeholder={t('settings.domainPlaceholder')}
            />
          </Section>

          <Section icon={CheckCircle} title={t('settings.whitelistSenders')}>
            <p className={styles.hint}>
              {t('settings.whitelistSendersHint')}
            </p>
            <EditableList
              id="settings-whitelist"
              items={local.whitelist_senders || []}
              onAdd={(v) => set('whitelist_senders', [...(local.whitelist_senders || []), v])}
              onRemove={(i) => set('whitelist_senders', local.whitelist_senders.filter((_, idx) => idx !== i))}
              placeholder={t('settings.whitelistPlaceholder')}
            />
          </Section>
        </div>

        <Section icon={Settings} title={t('settings.otherSettings')}>
          <FieldRow label={t('settings.adminNotifEmail')} hint={t('settings.adminNotifEmailHint')}>
            <input
              className={styles.input}
              type="email"
              placeholder="admin@lodaya.id"
              value={local.admin_alert_email}
              onChange={(e) => set('admin_alert_email', e.target.value)}
              id="settings-alert-email"
            />
          </FieldRow>
          <FieldRow label={t('settings.quarantineRetention')} hint={t('settings.quarantineRetentionHint')}>
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

        {isSuper && (
          <Section icon={Lock} title={t('settings.superadminManagement')}>
            <p className={styles.hint}>
              {t('settings.superadminHint')}
            </p>
            <div className={styles.fieldRow}>
              <div className={styles.fieldLeft}>
                <label className={styles.fieldLabel}>{t('settings.adminPanel')}</label>
                <span className={styles.fieldHint}>{t('settings.adminPanelHint')}</span>
              </div>
              <div className={styles.fieldRight}>
                <button className={styles.btnPrimary} onClick={() => navigate(isSuper ? '/super-admin/dashboard' : '/admin/dashboard')}>
                  <Lock size={15} /> {t('settings.openAdminPanel')}
                </button>
              </div>
            </div>
          </Section>
        )}

        <div className={styles.footer}>
          <button
            className={styles.btnOutline}
            onClick={handleReset}
            disabled={isSaving}
            id="settings-reset-footer-btn"
          >
            <RefreshCw size={15} /> {t('settings.resetDefault')}
          </button>
          <button
            className={`${styles.btnPrimary} ${dirty ? styles.btnDirty : ''}`}
            onClick={handleSave}
            disabled={isSaving}
            id="settings-save-footer-btn"
          >
            {isSaving ? <Loader2 size={15} className={styles.spin} /> : <Save size={15} />}
            {isSaving ? t('common.saving') : t('settings.saveSettings')}
          </button>
        </div>
      </div>
    </GmailShell>
  )
}
