import { useState, useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useEmails, useToggleStarred } from '../../api/emails'
import { useMe } from '../../api/auth'
import { useTranslation } from '../../i18n/context'
import EmailToolbar from './EmailToolbar'
import EmailRow from './EmailRow'
import { getActiveMailbox, getActiveMailboxId } from '../../utils/mailbox'
import { groupEmailsIntoThreads } from '../../utils/threadUtils'
import styles from './EmailList.module.css'

const PAGE_SIZE = 50

export default function EmailList({ view = '', activeEmailId = null }) {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const filter = searchParams.get('filter') || 'all'
  const folder = ['starred', 'allmail', 'trash'].includes(view) ? view : (searchParams.get('folder') || '')
  const category = ['spam', 'phishing', 'malware'].includes(view) ? view : (searchParams.get('category') || '')
  const query = searchParams.get('q') || ''
  const { data: meData, isLoading: meLoading } = useMe()
  const userRole = meData?.user?.role
  const rawMailboxId = getActiveMailboxId(searchParams)
  const urlIdIsEmail = rawMailboxId && rawMailboxId.includes('@')
  const rawMailbox = getActiveMailbox(searchParams)
  const mailbox = userRole === 'user'
    ? (meData?.user?.email || '')
    : (rawMailbox || (urlIdIsEmail ? rawMailboxId : '') || (userRole === 'mailbox' ? meData?.user?.mailbox_email || meData?.user?.username || '' : ''))
  const mailboxId = userRole === 'user'
    ? (meData?.user?.email || '')
    : (rawMailboxId || (userRole === 'mailbox' ? meData?.user?.mailbox_id || '' : ''))
  const page = parseInt(searchParams.get('page') || '1', 10)

  const apiFilter = category || folder || filter
  const emailResolved = userRole !== 'user' || Boolean(meData?.user?.email)
  const { data, isLoading, isError, refetch } = useEmails(apiFilter, query, {
    mailbox,
    mailboxId,
    page,
    pageSize: PAGE_SIZE,
    enabled: !meLoading && emailResolved,
  })
  const retentionLabel = folder === 'trash'
    ? t('gmail.trash')
    : category
      ? t(`gmail.${category}`)
      : ''

  const [selected, setSelected] = useState(new Set())
  const { mutate: toggleStarredMutate } = useToggleStarred()

  const emails = useMemo(() => {
    const list = data?.emails || []
    return [...list].sort((a, b) => {
      const aTime = new Date(a.received_at || a.timestamp || 0).getTime()
      const bTime = new Date(b.received_at || b.timestamp || 0).getTime()
      return (Number.isNaN(bTime) ? 0 : bTime) - (Number.isNaN(aTime) ? 0 : aTime)
    })
  }, [data, isLoading])


  // Group emails into conversation threads (Gmail-style)
  const threads = useMemo(() => {
    // In special folders that don't need thread grouping, return flat list
    const skipGrouping = folder === 'trash' || folder === 'starred' || category
    if (skipGrouping) return emails.map((e) => ({ ...e, _isThread: false, thread_email_ids: [e.email_id], messageCount: 1, hasDraft: false }))
    return groupEmailsIntoThreads(emails, mailboxId)
  }, [emails, folder, category, mailboxId])

  const filtered = threads
  const totalFiltered = data?.total ?? filtered.length
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
    const email = (data?.emails || []).find((e) => e.email_id === id)
    const nextVal = !(email?.is_starred ?? false)
    toggleStarredMutate({ emailId: id, isStarred: nextVal })
  }, [data, toggleStarredMutate])

  const setReadState = (emailId, shouldRead) => {
    // Left empty or we can keep the local state if needed. But EmailRow now handles the mutation and React Query handles the cache update.
  }

  return (
    <div className={styles.wrapper}>
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
              isStarred={rowEmail.is_starred ?? false}
              onToggleStar={toggleStar}
              onSetRead={setReadState}
              activeEmailId={activeEmailId}
            />
          )
        })}
      </div>
    </div>
  )
}
