import { useState, useCallback, useMemo, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useEmails } from '../../api/emails'
import { useStats } from '../../api/metrics'
import { useMe } from '../../api/auth'
import { useTranslation } from '../../i18n/context'
import CategoryTabs from './CategoryTabs'
import EmailToolbar from './EmailToolbar'
import EmailRow from './EmailRow'
import { getActiveMailbox, getActiveMailboxId } from '../../utils/mailbox'
import { groupEmailsIntoThreads } from '../../utils/threadUtils'
import styles from './EmailList.module.css'

const PAGE_SIZE = 50

export default function EmailList({ view = '' }) {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const filter = searchParams.get('filter') || 'all'
  const folder = ['starred', 'allmail', 'trash'].includes(view) ? view : (searchParams.get('folder') || '')
  const category = ['spam', 'phishing', 'malware'].includes(view) ? view : (searchParams.get('category') || '')
  const query = searchParams.get('q') || ''
  const { data: meData, isLoading: meLoading } = useMe()
  const userRole = meData?.user?.role
  // For role 'user', always use their own email — never trust URL mailboxId
  const mailbox = userRole === 'user'
    ? (meData?.user?.email || '')
    : (getActiveMailbox(searchParams) || (userRole === 'mailbox' ? meData?.user?.mailbox_email || meData?.user?.username || '' : ''))
  const mailboxId = userRole === 'user'
    ? (meData?.user?.email || '')
    : (getActiveMailboxId(searchParams) || (userRole === 'mailbox' ? meData?.user?.mailbox_id || '' : ''))
  const page = parseInt(searchParams.get('page') || '1', 10)

  const apiFilter = category || (folder === 'starred' ? 'allmail' : folder) || filter
  // For role 'user', wait until their email is resolved before fetching — otherwise
  // the API fires with an empty mailbox and returns no results.
  const emailResolved = userRole !== 'user' || Boolean(meData?.user?.email)
  const { data, isLoading, isError, refetch } = useEmails(apiFilter, query, {
    mailbox,
    mailboxId,
    page,
    pageSize: PAGE_SIZE,
    enabled: !meLoading && emailResolved,
  })
  const { data: stats } = useStats()
  const retentionLabel = folder === 'trash' ? t('gmail.trash') : t('gmail.' + category)

  const [selected, setSelected] = useState(new Set())
  const [starred, setStarred] = useState(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem('cognimail_starred_ids') || '[]'))
    } catch {
      return new Set()
    }
  })

  // Sync starred state when changed from other pages (EmailDetailPage, etc.)
  useEffect(() => {
    const handler = () => {
      try {
        setStarred(new Set(JSON.parse(localStorage.getItem('cognimail_starred_ids') || '[]')))
      } catch { /* ignore */ }
    }
    window.addEventListener('cognimail_starred_changed', handler)
    return () => window.removeEventListener('cognimail_starred_changed', handler)
  }, [])


  const emails = useMemo(() => {
    const list = data?.emails || []
    let next = list
    if (folder === 'starred') next = next.filter((e) => starred.has(e.email_id))
    // Note: mailbox filtering is already handled by the API backend
    // No need to filter again here — backend uses domain fallback for empty mailboxes
    return [...next].sort((a, b) => {
      const aTime = new Date(a.received_at || a.timestamp || 0).getTime()
      const bTime = new Date(b.received_at || b.timestamp || 0).getTime()
      return (Number.isNaN(bTime) ? 0 : bTime) - (Number.isNaN(aTime) ? 0 : aTime)
    })
  }, [data, folder, starred])

  // Group emails into conversation threads (Gmail-style)
  const threads = useMemo(() => {
    // In special folders that don't need thread grouping, return flat list
    const skipGrouping = folder === 'trash' || folder === 'starred' || category
    if (skipGrouping) return emails.map((e) => ({ ...e, _isThread: false, thread_email_ids: [e.email_id], messageCount: 1, hasDraft: false }))
    return groupEmailsIntoThreads(emails, mailboxId)
  }, [emails, folder, category, mailboxId])

  const filtered = threads
  const totalFiltered = folder === 'starred' ? filtered.length : (data?.total ?? filtered.length)
  const paginated = filtered

  const handlePageChange = useCallback((newPage) => {
    setSelected(new Set())
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (newPage === 1) next.delete('page')
      else next.set('page', String(newPage))
      return next
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [setSearchParams])

  const rowIds = useCallback((item) => (
    Array.isArray(item.thread_email_ids) && item.thread_email_ids.length > 0
      ? item.thread_email_ids
      : [item.email_id]
  ), [])

  const toggleSelect = useCallback((emailOrThread) => {
    // Accept either an id string or a thread/email object
    const ids = typeof emailOrThread === 'string'
      ? [emailOrThread]
      : rowIds(emailOrThread)
    setSelected((prev) => {
      const next = new Set(prev)
      const allSelected = ids.every((id) => next.has(id))
      ids.forEach((id) => { allSelected ? next.delete(id) : next.add(id) })
      return next
    })
  }, [rowIds])

  const toggleSelectAll = useCallback(
    (checked) => setSelected(checked ? new Set(paginated.flatMap(rowIds)) : new Set()),
    [paginated, rowIds]
  )

  const handleRefresh = useCallback(() => {
    setSelected(new Set())
    refetch()
  }, [refetch])

  const toggleStar = useCallback((id) => {
    setStarred((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      localStorage.setItem('cognimail_starred_ids', JSON.stringify(Array.from(next)))
      window.dispatchEvent(new Event('cognimail_starred_changed'))
      return next
    })
  }, [])

  const setReadState = (emailId, shouldRead) => {
    // Left empty or we can keep the local state if needed. But EmailRow now handles the mutation and React Query handles the cache update.
  }

  return (
    <div className={styles.wrapper}>
      {!folder && <CategoryTabs activeFilter={filter} />}
      {retentionLabel && (
        <div className={styles.trashNotice}>
          {t('emailList.retentionNotice').replace('{folder}', retentionLabel)}
        </div>
      )}
      <EmailToolbar
        total={totalFiltered}
        shown={paginated.length}
        page={page}
        view={folder || category || filter}
        onPageChange={handlePageChange}
        selected={selected}
        allIds={paginated.flatMap(rowIds)}
        onSelectAll={toggleSelectAll}
        onRefresh={handleRefresh}
      />

      <div className={styles.list}>
        {isLoading && (
          Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className={styles.skeletonRow}>
              <div className={styles.skeletonInner} />
            </div>
          ))
        )}
        {isError && (
          <div className={styles.empty}>
            <svg width="56" height="56" viewBox="0 0 24 24" opacity="0.25">
              <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
            </svg>
            <p>{t('emailList.loadError')}</p>
          </div>
        )}
        {!isLoading && !isError && filtered.length === 0 && (
          <div className={styles.empty}>
            <svg width="64" height="64" viewBox="0 0 24 24" opacity="0.2">
              <path fill="currentColor" d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
            </svg>
            <p>{t('gmail.noMails')}</p>
          </div>
        )}
        {!isLoading && paginated.map((emailOrThread) => {
          const isThreadGroup = emailOrThread._isThread && emailOrThread.messageCount > 1
          // Build the representative email object for EmailRow
          const rowEmail = isThreadGroup
            ? {
                ...emailOrThread,
                // Show combined sender info
                sender: emailOrThread.senders.length > 1
                  ? `${emailOrThread.senders[emailOrThread.senders.length - 1]} (${emailOrThread.senders.length})`
                  : (emailOrThread.senders[0] || emailOrThread.sender || ''),
                // Annotate subject with thread count badge via senderLabel trick
                _threadCount: emailOrThread.messageCount,
                _hasDraftInThread: emailOrThread.hasDraft,
              }
            : emailOrThread
          const isSelected = rowIds(emailOrThread).every((id) => selected.has(id))
          return (
            <EmailRow
              key={emailOrThread.email_id}
              email={rowEmail}
              isRead={emailOrThread.is_read}
              isSelected={isSelected}
              onToggleSelect={() => toggleSelect(emailOrThread)}
              isStarred={starred.has(emailOrThread.email_id)}
              onToggleStar={toggleStar}
              onSetRead={setReadState}
            />
          )
        })}
      </div>
    </div>
  )
}
