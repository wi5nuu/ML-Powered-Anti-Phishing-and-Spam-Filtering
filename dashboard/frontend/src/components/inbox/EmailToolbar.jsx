import { RefreshCw, Trash2, Archive, MoreVertical, ChevronDown, Pencil } from 'lucide-react'
import { useDeleteEmail, useReleaseEmail } from '../../api/emails'
import { useMe } from '../../api/auth'
import { useToast } from '../../hooks/useToast'
import styles from './EmailToolbar.module.css'

const PAGE_SIZE = 50

export default function EmailToolbar({
  total,
  shown,
  page,
  onPageChange,
  selected,
  allIds,
  onSelectAll,
  onRefresh,
}) {
  const allSelected = selected.size === allIds.length && allIds.length > 0
  const someSelected = selected.size > 0 && !allSelected

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const start = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const end = Math.min(page * PAGE_SIZE, total)

  const { data: meData } = useMe()
  const { mutateAsync: deleteEmail } = useDeleteEmail()
  const { mutateAsync: releaseEmail } = useReleaseEmail()
  const { showToast } = useToast()

  const role = meData?.user?.role || 'user'

  const handleBulkDelete = async () => {
    if (role !== 'superadmin' && role !== 'admin') {
      showToast('Aksi ditolak: Hanya Super Admin & Admin yang dapat menghapus email', 'error')
      return
    }
    if (window.confirm(`Apakah Anda yakin ingin menghapus ${selected.size} email terpilih secara permanen?`)) {
      try {
        const promises = Array.from(selected).map(id => deleteEmail(id))
        await Promise.all(promises)
        showToast(`🗑️ ${selected.size} email berhasil dihapus`, 'success')
        onSelectAll(false)
        onRefresh()
      } catch (err) {
        showToast('❌ Gagal menghapus beberapa email', 'error')
      }
    }
  }

  const handleBulkArchive = async () => {
    if (role !== 'superadmin' && role !== 'admin') {
      showToast('Aksi ditolak: Peran user tidak memiliki izin untuk mengelola karantina', 'error')
      return
    }
    try {
      const promises = Array.from(selected).map(id => releaseEmail(id))
      await Promise.all(promises)
      showToast(`✅ ${selected.size} email dilepaskan ke inbox`, 'success')
      onSelectAll(false)
      onRefresh()
    } catch (err) {
      showToast('❌ Gagal melepaskan beberapa email', 'error')
    }
  }

  const handleComposeClick = () => {
    window.dispatchEvent(new CustomEvent('open-compose'))
  }

  const handleMoreActions = () => {
    showToast('Opsi tambahan disimulasikan', 'info')
  }

  return (
    <div className={styles.toolbar}>
      {/* LEFT: checkbox + refresh + bulk actions */}
      <div className={styles.left}>
        <div className={styles.checkWrap}>
          <input
            type="checkbox"
            id="select-all-checkbox"
            checked={allSelected}
            ref={(el) => { if (el) el.indeterminate = someSelected }}
            onChange={(e) => onSelectAll(e.target.checked)}
            title="Pilih semua"
          />
          <button
            className={styles.chevronBtn}
            title="Opsi pilih"
            onClick={() => onSelectAll(!allSelected)}
          >
            <ChevronDown size={14} />
          </button>
        </div>

        <button
          className={styles.iconBtn}
          onClick={onRefresh}
          title="Refresh"
          id="toolbar-refresh-btn"
        >
          <RefreshCw size={16} />
        </button>

        <button
          className={styles.iconBtn}
          onClick={handleMoreActions}
          title="Opsi lainnya"
          id="toolbar-more-btn"
        >
          <MoreVertical size={16} />
        </button>

        {selected.size > 0 && (
          <div className={styles.bulkActions}>
            <div className={styles.divider} />
            <button
              className={styles.iconBtn}
              title="Hapus yang dipilih"
              id="toolbar-delete-btn"
              onClick={handleBulkDelete}
            >
              <Trash2 size={16} />
            </button>
            <button
              className={styles.iconBtn}
              title="Arsipkan/Rilis yang dipilih"
              id="toolbar-archive-btn"
              onClick={handleBulkArchive}
            >
              <Archive size={16} />
            </button>
            <span className={styles.selCount}>{selected.size} dipilih</span>
          </div>
        )}
      </div>

      {/* RIGHT: pagination + compose shortcut */}
      <div className={styles.right}>
        <div className={styles.pagination}>
          <span className={styles.paginationInfo}>
            {total === 0 ? '0' : `${start}–${end}`} dari {total.toLocaleString('id-ID')}
          </span>
          <button
            className={styles.iconBtn}
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            title="Halaman sebelumnya"
            id="toolbar-prev-btn"
          >
            ‹
          </button>
          <button
            className={styles.iconBtn}
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            title="Halaman berikutnya"
            id="toolbar-next-btn"
          >
            ›
          </button>
        </div>

        <button
          className={`${styles.iconBtn} ${styles.composeShortcut}`}
          onClick={handleComposeClick}
          title="Tulis email baru"
          id="toolbar-compose-shortcut-btn"
        >
          <Pencil size={16} />
        </button>
      </div>
    </div>
  )
}
