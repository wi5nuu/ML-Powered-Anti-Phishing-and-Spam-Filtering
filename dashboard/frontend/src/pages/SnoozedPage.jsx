import { useCallback, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from '../i18n/context'
import GmailShell from '../components/layout/GmailShell'
import EmailRow from '../components/inbox/EmailRow'
import EmailToolbar from '../components/inbox/EmailToolbar'
import { useEmails, useSnoozeEmail } from '../api/emails'
import { useMe } from '../api/auth'
import { getActiveMailbox, getActiveMailboxId } from '../utils/mailbox'
import { useToast } from '../hooks/useToast'
import { Clock } from 'lucide-react'

export default function SnoozedPage() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: meData } = useMe()
  const { showToast } = useToast()
  const userRole = meData?.user?.role
  const mailbox = userRole === 'user'
    ? (meData?.user?.email || '')
    : (getActiveMailbox(searchParams) || (userRole === 'mailbox' ? meData?.user?.mailbox_email || meData?.user?.username || '' : ''))
  const mailboxId = userRole === 'user'
    ? (meData?.user?.email || '')
    : (getActiveMailboxId(searchParams) || (userRole === 'mailbox' ? meData?.user?.mailbox_id || '' : ''))

  const page = parseInt(searchParams.get('page') || '1', 10)
  const { data, isLoading, isError, refetch } = useEmails('snoozed', '', {
    mailbox,
    mailboxId,
    page,
    pageSize: 50,
  })
  const { mutate: snoozeEmail } = useSnoozeEmail()
  const [selected, setSelected] = useState(new Set())

  const emails = data?.emails || []

  const toggleSelect = useCallback((id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const handleUnsnooze = useCallback((emailId) => {
    snoozeEmail({ emailId, snoozedUntil: null }, {
      onSuccess: () => showToast('Email tidak lagi di-snooze', 'success'),
      onError: () => showToast('Gagal membatalkan snooze', 'error'),
    })
  }, [snoozeEmail, showToast])

  const handlePageChange = useCallback((newPage) => {
    setSelected(new Set())
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (newPage === 1) next.delete('page')
      else next.set('page', String(newPage))
      return next
    })
  }, [setSearchParams])

  return (
    <GmailShell>
      <div style={{ fontFamily: 'Google Sans, Roboto, sans-serif' }}>
        <EmailToolbar
          total={data?.total ?? emails.length}
          shown={emails.length}
          page={page}
          onPageChange={handlePageChange}
          selected={selected}
          allIds={emails.map((e) => e.email_id)}
          onSelectAll={(checked) => setSelected(checked ? new Set(emails.map((e) => e.email_id)) : new Set())}
          onRefresh={() => { setSelected(new Set()); refetch() }}
        />

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '16px 24px 8px' }}>
          <Clock size={22} color="#f29900" />
          <h1 style={{ fontSize: '1.25rem', fontWeight: 500, margin: 0 }}>{t('snoozed.title')}</h1>
        </div>

        {isLoading && (
          <div style={{ color: 'var(--text-muted)', padding: '20px 24px' }}>{t('gmail.loading')}</div>
        )}

        {!isLoading && !isError && emails.length === 0 && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            padding: '80px 20px', color: 'var(--text-muted)', background: 'var(--surface)',
            border: '1px solid var(--border)', borderRadius: '8px', margin: '0 24px', textAlign: 'center',
          }}>
            <Clock size={48} stroke="currentColor" opacity={0.25} style={{ marginBottom: '16px' }} />
            <h3 style={{ margin: '0 0 8px 0', fontWeight: 500, color: 'var(--text)' }}>{t('snoozed.empty')}</h3>
            <p style={{ margin: 0, fontSize: '0.875rem', maxWidth: '360px' }}>{t('snoozed.hint')}</p>
          </div>
        )}

        {!isLoading && !isError && emails.length > 0 && (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden', margin: '0 24px' }}>
            {emails.map((email) => (
              <div key={email.email_id} style={{ position: 'relative' }}>
                <EmailRow
                  email={email}
                  isSelected={selected.has(email.email_id)}
                  onToggleSelect={() => toggleSelect(email.email_id)}
                  isRead={email.is_read}
                  isStarred={email.is_starred ?? false}
                />
                {email.snoozed_until && (
                  <div style={{
                    position: 'absolute', right: '80px', top: '50%', transform: 'translateY(-50%)',
                    display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem',
                    color: '#f29900', background: 'var(--surface)', padding: '2px 8px',
                    borderRadius: '12px', border: '1px solid #f29900',
                  }}>
                    <Clock size={12} />
                    {new Date(email.snoozed_until).toLocaleString('id-ID', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    <button
                      onClick={() => handleUnsnooze(email.email_id)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#f29900', padding: '0 2px', fontSize: '0.75rem' }}
                      title="Batalkan snooze"
                    >✕</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </GmailShell>
  )
}

