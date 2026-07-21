import { useEmails } from '../api/emails'
import GmailShell from '../components/layout/GmailShell'
import EmailRow from '../components/inbox/EmailRow'
import EmailToolbar from '../components/inbox/EmailToolbar'
import styles from '../components/inbox/EmailList.module.css'
import { useCallback, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getActiveMailbox, getActiveMailboxId } from '../utils/mailbox'
import { useMe } from '../api/auth'
import { dedupeDrafts, displaySubject } from '../utils/threadUtils'
import { FileText } from 'lucide-react'
import { useTranslation } from '../i18n/context'

const PAGE_SIZE = 50

function cleanDraftPreview(value = '') {
  const text = String(value || '')
  const [body] = text.split(/\s*-{5,}\s*(?:Original|Forwarded) message\s*-{5,}\s*/i)
  return (body || text).trim()
}

export default function DraftPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: meData } = useMe()
  const { t } = useTranslation()
  const mailbox = getActiveMailbox(searchParams) || (meData?.user?.role === 'mailbox' ? meData.user.mailbox_email || meData.user.username || '' : '')
  const mailboxId = getActiveMailboxId(searchParams) || (meData?.user?.role === 'mailbox' ? meData.user.mailbox_id || '' : '')
  const query = searchParams.get('q') || ''
  const page = parseInt(searchParams.get('page') || '1', 10)
  const [selected, setSelected] = useState(new Set())

  const { data, isLoading, isError, refetch } = useEmails('draft', query, {
    mailbox,
    mailboxId,
    page,
    pageSize: PAGE_SIZE,
  })

  const emails = data?.emails || []

  const rawDrafts = emails.filter((e) => {
    const isDraft = e.label === 'DRAFT' || e.status === 'draft'
    if (!isDraft) return false
    if (!mailbox) return true
    const target = mailbox.toLowerCase()
    return String(e.sender || e.sender_email || '').toLowerCase() === target
  })

  const draftEmails = useMemo(() => {
    const deduped = dedupeDrafts(rawDrafts, mailboxId)
    return deduped.map((draft) => ({
      ...draft,
      subject: displaySubject(draft.subject),
      body_preview: cleanDraftPreview(draft.body_preview),
    }))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(rawDrafts.map((d) => d.email_id)), mailboxId])

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
    (checked) => setSelected(checked ? new Set(draftEmails.flatMap(rowIds)) : new Set()),
    [draftEmails, rowIds]
  )

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

  const handleRefresh = useCallback(() => {
    setSelected(new Set())
    return refetch()
  }, [refetch])

  return (
    <GmailShell>
      <div className={styles.wrapper}>
        <EmailToolbar
          total={data?.total ?? draftEmails.length}
          shown={draftEmails.length}
          page={page}
          onPageChange={handlePageChange}
          selected={selected}
          allIds={draftEmails.flatMap(rowIds)}
          onSelectAll={toggleSelectAll}
          onRefresh={handleRefresh}
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
              <p>{t('draft.loadError')}</p>
            </div>
          )}
          {!isLoading && !isError && draftEmails.length === 0 && (
            <div className={styles.empty}>
              <FileText size={40} strokeWidth={1.2} />
              <p style={{ margin: 0, fontWeight: 500 }}>{t('draft.empty')}</p>
              <p style={{ margin: 0, fontSize: '0.875rem' }}>{t('draft.emptyHint')}</p>
            </div>
          )}
          {!isLoading && !isError && draftEmails.map((email) => (
            <EmailRow
              key={email.email_id}
              email={email}
              openDraftMode={email._isReplyDraft ? 'detail' : 'compose'}
              isSelected={isThreadSelected(email)}
              onToggleSelect={() => toggleSelectThread(email)}
            />
          ))}
        </div>
      </div>
    </GmailShell>
  )
}
