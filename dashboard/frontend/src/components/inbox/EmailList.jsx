import { useState, useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useEmails } from '../../api/emails'
import { useStats } from '../../api/metrics'
import StatsRibbon from './StatsRibbon'
import CategoryTabs from './CategoryTabs'
import EmailToolbar from './EmailToolbar'
import EmailRow from './EmailRow'
import styles from './EmailList.module.css'

const PAGE_SIZE = 50

export default function EmailList() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filter = searchParams.get('filter') || 'all'
  const category = searchParams.get('category') || ''
  const query = searchParams.get('q') || ''
  const page = parseInt(searchParams.get('page') || '1', 10)

  const { data, isLoading, isError, refetch } = useEmails(category || filter)
  const { data: stats } = useStats()

  const [selected, setSelected] = useState(new Set())

  const emails = data?.emails || []

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

  return (
    <div className={styles.wrapper}>
      <StatsRibbon stats={stats} />
      <CategoryTabs activeFilter={filter} quarantineCount={stats?.quarantine} warnCount={stats?.warn} cleanCount={stats?.clean} />
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
            isSelected={selected.has(email.email_id)}
            onToggleSelect={() => toggleSelect(email.email_id)}
          />
        ))}
      </div>
    </div>
  )
}
