import { useState, useCallback, useMemo, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useEmails } from '../../api/emails'
import { useStats } from '../../api/metrics'
import CategoryTabs from './CategoryTabs'
import EmailToolbar from './EmailToolbar'
import EmailRow from './EmailRow'
import styles from './EmailList.module.css'

const PAGE_SIZE = 50

export default function EmailList() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filter = searchParams.get('filter') || 'all'
  const folder = searchParams.get('folder') || ''
  const category = searchParams.get('category') || ''
  const query = searchParams.get('q') || ''
  const mailbox = searchParams.get('mailbox') || ''
  const page = parseInt(searchParams.get('page') || '1', 10)

  const apiFilter = category || (folder === 'starred' ? 'allmail' : folder) || filter
  const { data, isLoading, isError, refetch } = useEmails(apiFilter)
  const { data: stats } = useStats()

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

  const emails = useMemo(() => {
    const list = data?.emails || []
    let next = list
    if (folder === 'starred') next = next.filter((e) => starred.has(e.email_id))
    if (mailbox) {
      const target = mailbox.toLowerCase()
      next = next.filter((e) =>
        String(e.recipient_list || '').toLowerCase().includes(target) ||
        String(e.sender || e.sender_email || '').toLowerCase() === target
      )
    }
    return next
  }, [data, folder, mailbox, starred])

  // Client-side search filter
  const filtered = useMemo(() =>
    query
      ? emails.filter((e) =>
          (e.subject || '').toLowerCase().includes(query.toLowerCase()) ||
          (e.sender || '').toLowerCase().includes(query.toLowerCase())
        )
      : emails,
    [emails, query]
  )

  // Client-side pagination
  const totalFiltered = filtered.length
  const paginated = useMemo(() =>
    filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
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
    window.scrollTo({ top: 0, behavior: 'smooth' })
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

  const handleRefresh = useCallback(() => {
    setSelected(new Set())
    refetch()
  }, [refetch])

  useEffect(() => {
    localStorage.setItem('cognimail.starred', JSON.stringify(Array.from(starred)))
  }, [starred])

  useEffect(() => {
    localStorage.setItem('cognimail.read', JSON.stringify(Array.from(readIds)))
  }, [readIds])

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
    <div className={styles.wrapper}>
      {!folder && <CategoryTabs activeFilter={filter} />}
      {folder === 'trash' && (
        <div className={styles.trashNotice}>
          Pesan yang ada di Sampah selama lebih dari 30 hari akan dihapus secara otomatis.
        </div>
      )}
      <EmailToolbar
        total={totalFiltered}
        shown={paginated.length}
        page={page}
        onPageChange={handlePageChange}
        selected={selected}
        allIds={paginated.map((e) => e.email_id)}
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
            <p>❌ Gagal memuat email. Cek koneksi server.</p>
          </div>
        )}
        {!isLoading && !isError && filtered.length === 0 && (
          <div className={styles.empty}>
            <svg width="64" height="64" viewBox="0 0 24 24" opacity="0.2">
              <path fill="currentColor" d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
            </svg>
            <p>Tidak ada email ditemukan</p>
          </div>
        )}
        {!isLoading && paginated.map((email) => (
          <EmailRow
            key={email.email_id}
            email={email}
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
  )
}
