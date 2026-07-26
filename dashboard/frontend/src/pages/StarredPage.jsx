import { useEmails, useToggleStarred } from '../api/emails'
import GmailShell from '../components/layout/GmailShell'
import { useTranslation } from '../i18n/context'
import EmailRow from '../components/inbox/EmailRow'
import EmailToolbar from '../components/inbox/EmailToolbar'
import { Star } from 'lucide-react'
import { useCallback, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getActiveMailbox, getActiveMailboxId } from '../utils/mailbox'
import { useMe } from '../api/auth'

export default function StarredPage() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: meData } = useMe()
  const userRole = meData?.user?.role
  const mailbox = userRole === 'user'
    ? (meData?.user?.email || '')
    : (getActiveMailbox(searchParams) || (userRole === 'mailbox' ? meData?.user?.mailbox_email || meData?.user?.username || '' : ''))
  const mailboxId = userRole === 'user'
    ? (meData?.user?.email || '')
    : (getActiveMailboxId(searchParams) || (userRole === 'mailbox' ? meData?.user?.mailbox_id || '' : ''))

  const page = parseInt(searchParams.get('page') || '1', 10)
  const { data, isLoading, isError, refetch } = useEmails('starred', '', {
    mailbox,
    mailboxId,
    page,
    pageSize: 50,
  })
  const { mutate: toggleStarredMutate } = useToggleStarred()
  const [selected, setSelected] = useState(new Set())

  // Backend already filters is_starred=true, no need to re-filter
  const emails = data?.emails || []

  const toggleSelect = useCallback((id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const toggleStar = useCallback((id) => {
    const email = emails.find((e) => e.email_id === id)
    const nextVal = !(email?.is_starred ?? false)
    toggleStarredMutate({ emailId: id, isStarred: nextVal })
  }, [emails, toggleStarredMutate])

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
          <Star size={22} fill="#f29900" stroke="#f29900" />
          <h1 style={{ fontSize: '1.25rem', fontWeight: 500, margin: 0 }}>{t('gmail.starred')}</h1>
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
            <Star size={48} stroke="currentColor" opacity={0.25} style={{ marginBottom: '16px' }} />
            <h3 style={{ margin: '0 0 8px 0', fontWeight: 500, color: 'var(--text)' }}>{t('gmail.noMails')}</h3>
            <p style={{ margin: 0, fontSize: '0.875rem', maxWidth: '360px' }}>
              Bintangi email penting untuk menemukannya dengan mudah di sini nanti.
            </p>
          </div>
        )}

        {!isLoading && !isError && emails.length > 0 && (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden', margin: '0 24px' }}>
            {emails.map((email) => (
              <EmailRow
                key={email.email_id}
                email={email}
                isSelected={selected.has(email.email_id)}
                onToggleSelect={() => toggleSelect(email.email_id)}
                isStarred={email.is_starred ?? true}
                onToggleStar={toggleStar}
                isRead={email.is_read}
              />
            ))}
          </div>
        )}
      </div>
    </GmailShell>
  )
}
