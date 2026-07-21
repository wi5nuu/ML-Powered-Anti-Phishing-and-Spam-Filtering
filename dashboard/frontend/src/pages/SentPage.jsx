import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import GmailShell from '../components/layout/GmailShell'
import { useTranslation } from '../i18n/context'
import { useEmails } from '../api/emails'
import { useMe } from '../api/auth'
import EmailRow from '../components/inbox/EmailRow'
import EmailToolbar from '../components/inbox/EmailToolbar'
import { getActiveMailbox, getActiveMailboxId } from '../utils/mailbox'
import { Send } from 'lucide-react'
import styles from '../components/inbox/EmailList.module.css'

const PAGE_SIZE = 50

function normalizeThreadSubject(subject = '') {
  let value = String(subject || '').trim()
  while (/^(re|fw|fwd)\s*:/i.test(value)) {
    value = value.replace(/^(re|fw|fwd)\s*:\s*/i, '').trim()
  }
  return value.toLowerCase()
}

function threadKey(email) {
  return [
    normalizeThreadSubject(email.subject),
    String(email.sender || '').toLowerCase(),
    String(email.recipient_list || '').toLowerCase(),
  ].join('|')
}

export default function SentPage() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: meData } = useMe()
  const mailbox = getActiveMailbox(searchParams) || (meData?.user?.role === 'mailbox' ? meData.user.mailbox_email || meData.user.username || '' : '')
  const mailboxId = getActiveMailboxId(searchParams) || (meData?.user?.role === 'mailbox' ? meData.user.mailbox_id || '' : '')
  const query = searchParams.get('q') || ''
  const page = parseInt(searchParams.get('page') || '1', 10)
  const { data, isLoading, isError, refetch } = useEmails('sent', query, {
    mailbox,
    mailboxId,
    page,
    pageSize: PAGE_SIZE,
  })

  const [selected, setSelected] = useState(new Set())
  const [starred, setStarred] = useState(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem('cognimail_starred_ids') || '[]'))
    } catch {
      return new Set()
    }
  })
  const [readIds, setReadIds] = useState(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem('cognimail_read_ids') || '[]'))
    } catch {
      return new Set()
    }
  })

  useEffect(() => {
    localStorage.setItem('cognimail_starred_ids', JSON.stringify(Array.from(starred)))
    window.dispatchEvent(new Event('cognimail_starred_changed'))
  }, [starred])

  useEffect(() => {
    localStorage.setItem('cognimail_read_ids', JSON.stringify(Array.from(readIds)))
  }, [readIds])

  const sentRows = useMemo(() => {
    const rows = data?.emails || []
    if (!mailbox) return []
    const target = mailbox.toLowerCase()
    const sorted = rows
      .filter((email) => String(email.sender || email.sender_email || '').toLowerCase() === target)
      .sort((a, b) => {
        const aTime = new Date(a.received_at || a.timestamp || 0).getTime()
        const bTime = new Date(b.received_at || b.timestamp || 0).getTime()
        return (Number.isNaN(bTime) ? 0 : bTime) - (Number.isNaN(aTime) ? 0 : aTime)
      })
    const grouped = new Map()
    sorted.forEach((email) => {
      const key = threadKey(email)
      if (!grouped.has(key)) {
        grouped.set(key, { ...email, thread_email_ids: [email.email_id] })
      } else {
        const current = grouped.get(key)
        grouped.set(key, {
          ...current,
          thread_email_ids: [...(current.thread_email_ids || []), email.email_id],
        })
      }
    })
    return Array.from(grouped.values())
  }, [data, mailbox])

  const filtered = sentRows

  const paginated = filtered

  const handlePageChange = useCallback((newPage) => {
    setSelected(new Set())
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (newPage === 1) next.delete('page')
      else next.set('page', String(newPage))
      return next
    })
  }, [setSearchParams])

  const rowIds = useCallback((email) => (
    Array.isArray(email.thread_email_ids) && email.thread_email_ids.length > 0
      ? email.thread_email_ids
      : [email.email_id]
  ), [])

  const toggleSelectThread = useCallback((email) => {
    const ids = rowIds(email)
    setSelected((prev) => {
      const next = new Set(prev)
      const allSelected = ids.every((id) => next.has(id))
      ids.forEach((id) => {
        if (allSelected) next.delete(id)
        else next.add(id)
      })
      return next
    })
  }, [rowIds])

  const isThreadSelected = useCallback((email) => {
    const ids = rowIds(email)
    return ids.length > 0 && ids.every((id) => selected.has(id))
  }, [rowIds, selected])

  const toggleSelectAll = useCallback(
    (checked) => setSelected(checked ? new Set(paginated.flatMap(rowIds)) : new Set()),
    [paginated, rowIds]
  )

  const toggleStar = useCallback((id) => {
    setStarred((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const setReadState = useCallback((id, shouldRead = true) => {
    setReadIds((prev) => {
      const next = new Set(prev)
      if (shouldRead) next.add(id)
      else next.delete(id)
      return next
    })
  }, [])

  return (
    <GmailShell>
      <div className={styles.wrapper}>
        <EmailToolbar
          total={data?.total ?? filtered.length}
          shown={paginated.length}
          page={page}
          onPageChange={handlePageChange}
          selected={selected}
          allIds={paginated.flatMap(rowIds)}
          onSelectAll={toggleSelectAll}
          onRefresh={() => {
            setSelected(new Set())
            return refetch()
          }}
        />

        <div className={styles.list}>
          {isLoading && (
            Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className={styles.skeletonRow}>
                <div className={styles.skeletonInner} />
              </div>
            ))
          )}
          {isError && (
            <div className={styles.empty}>
              <p>{t('common.error')}</p>
            </div>
          )}
          {!isLoading && !isError && filtered.length === 0 && (
            <div className={styles.empty}>
              <Send size={40} strokeWidth={1.2} />
              <p style={{ margin: 0, fontWeight: 500 }}>{t('gmail.noMails')}</p>
              <p style={{ margin: 0, fontSize: '0.875rem' }}>Email yang Anda kirim akan muncul di sini.</p>
            </div>
          )}
          {!isLoading && paginated.map((email) => (
            <EmailRow
              key={email.email_id}
              email={email}
              senderLabel={`${t('common.recipient')}: ${email.recipient_list || t('common.na')}`}
              isRead={readIds.has(email.email_id)}
              isSelected={isThreadSelected(email)}
              onToggleSelect={() => toggleSelectThread(email)}
              isStarred={starred.has(email.email_id)}
              onToggleStar={toggleStar}
              onSetRead={setReadState}
            />
          ))}
        </div>
      </div>
    </GmailShell>
  )
}
