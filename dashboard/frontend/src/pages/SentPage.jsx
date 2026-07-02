import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import GmailShell from '../components/layout/GmailShell'
import { useEmails } from '../api/emails'
import EmailRow from '../components/inbox/EmailRow'
import EmailToolbar from '../components/inbox/EmailToolbar'
import styles from '../components/inbox/EmailList.module.css'

const PAGE_SIZE = 50

export default function SentPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const mailbox = searchParams.get('mailbox') || ''
  const page = parseInt(searchParams.get('page') || '1', 10)
  const { data, isLoading, isError, refetch } = useEmails('sent')

  const [selected, setSelected] = useState(new Set())
  const [starred, setStarred] = useState(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem('cognimail.starred') || '[]'))
    } catch {
      return new Set()
    }
  })
  const [readIds, setReadIds] = useState(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem('cognimail.read') || '[]'))
    } catch {
      return new Set()
    }
  })

  useEffect(() => {
    localStorage.setItem('cognimail.starred', JSON.stringify(Array.from(starred)))
  }, [starred])

  useEffect(() => {
    localStorage.setItem('cognimail.read', JSON.stringify(Array.from(readIds)))
  }, [readIds])

  const sentRows = useMemo(() => {
    const rows = data?.emails || []
    if (!mailbox) return []
    const target = mailbox.toLowerCase()
    return rows.filter((email) =>
      String(email.sender || email.sender_email || '').toLowerCase() === target
    )
  }, [data, mailbox])

  const filtered = sentRows

  const paginated = useMemo(
    () => filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [filtered, page]
  )

  const handlePageChange = useCallback((newPage) => {
    setSelected(new Set())
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (newPage === 1) next.delete('page')
      else next.set('page', String(newPage))
      return next
    })
  }, [setSearchParams])

  const toggleSelect = useCallback((id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const toggleSelectAll = useCallback(
    (checked) => setSelected(checked ? new Set(paginated.map((e) => e.email_id)) : new Set()),
    [paginated]
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
          total={filtered.length}
          shown={paginated.length}
          page={page}
          onPageChange={handlePageChange}
          selected={selected}
          allIds={paginated.map((e) => e.email_id)}
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
              <p>Gagal memuat email terkirim. Cek koneksi server.</p>
            </div>
          )}
          {!isLoading && !isError && filtered.length === 0 && (
            <div className={styles.empty}>
              <p>Tidak ada email terkirim</p>
            </div>
          )}
          {!isLoading && paginated.map((email) => (
            <EmailRow
              key={email.email_id}
              email={email}
              senderLabel={`Kepada: ${email.recipient_list || 'Penerima tidak diketahui'}`}
              isRead={readIds.has(email.email_id)}
              isSelected={selected.has(email.email_id)}
              onToggleSelect={() => toggleSelect(email.email_id)}
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
