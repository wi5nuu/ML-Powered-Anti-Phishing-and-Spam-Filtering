import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronDown, MailCheck, MailOpen, MoreVertical, Pencil, RefreshCw, Trash2 } from 'lucide-react'
import { useDeleteEmail } from '../../api/emails'
import { useToast } from '../../hooks/useToast'
import ConfirmDialog from '../common/ConfirmDialog'
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
  const [selectMenuOpen, setSelectMenuOpen] = useState(false)
  const [moreMenuOpen, setMoreMenuOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [searchParams] = useSearchParams()
  const selectMenuRef = useRef(null)
  const moreMenuRef = useRef(null)
  const allSelected = selected.size === allIds.length && allIds.length > 0
  const someSelected = selected.size > 0 && !allSelected
  const isTrashFolder = searchParams.get('folder') === 'trash'

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const start = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const end = Math.min(page * PAGE_SIZE, total)

  const { mutateAsync: deleteEmail } = useDeleteEmail()
  const { showToast } = useToast()

  useEffect(() => {
    const closeMenus = (e) => {
      if (!selectMenuRef.current?.contains(e.target)) setSelectMenuOpen(false)
      if (!moreMenuRef.current?.contains(e.target)) setMoreMenuOpen(false)
    }
    document.addEventListener('mousedown', closeMenus)
    return () => document.removeEventListener('mousedown', closeMenus)
  }, [])

  const handleBulkDelete = async () => {
    if (selected.size === 0) {
      showToast('Pilih email terlebih dahulu', 'info')
      return
    }
    setDeleteDialogOpen(true)
  }

  const confirmBulkDelete = async () => {
    try {
      const promises = Array.from(selected).map((id) => deleteEmail(id))
      await Promise.all(promises)
      if (isTrashFolder) showToast(`${selected.size} email dihapus permanen`, 'success')
      setDeleteDialogOpen(false)
      onSelectAll(false)
      onRefresh()
    } catch (err) {
      showToast('Gagal menghapus beberapa email', 'error')
    }
  }

  const handleComposeClick = () => {
    window.dispatchEvent(new CustomEvent('open-compose'))
  }

  const handleRefreshClick = async () => {
    setRefreshing(true)
    try {
      await onRefresh?.()
    } finally {
      setTimeout(() => setRefreshing(false), 350)
    }
  }

  const handleMark = (type) => {
    if (selected.size === 0) {
      showToast('Pilih email terlebih dahulu', 'info')
      return
    }
    showToast(`${selected.size} email ditandai ${type}`, 'success')
    setMoreMenuOpen(false)
  }

  return (
    <>
      <div className={styles.toolbar}>
      <div className={styles.left}>
        <div className={styles.checkWrap} ref={selectMenuRef}>
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
            onClick={(e) => { e.stopPropagation(); setSelectMenuOpen((v) => !v) }}
          >
            <ChevronDown size={14} />
          </button>
          {selectMenuOpen && (
            <div className={styles.menu} style={{ left: 0 }}>
              <button onClick={() => { onSelectAll(true); setSelectMenuOpen(false) }}>Semua</button>
              <button onClick={() => { onSelectAll(false); setSelectMenuOpen(false) }}>Tidak ada</button>
              <button onClick={() => { onSelectAll(!allSelected); setSelectMenuOpen(false) }}>
                {allSelected ? 'Batal pilih halaman' : 'Pilih halaman ini'}
              </button>
            </div>
          )}
        </div>

        <button
          className={`${styles.iconBtn} ${refreshing ? styles.spinning : ''}`}
          onClick={handleRefreshClick}
          title="Refresh"
          id="toolbar-refresh-btn"
        >
          <RefreshCw size={16} />
        </button>

        <div className={styles.moreWrap} ref={moreMenuRef}>
          <button
            className={styles.iconBtn}
            onClick={(e) => { e.stopPropagation(); setMoreMenuOpen((v) => !v) }}
            title="Opsi lainnya"
            id="toolbar-more-btn"
          >
            <MoreVertical size={16} />
          </button>
          {moreMenuOpen && (
            <div className={styles.menu}>
              <button onClick={() => { handleComposeClick(); setMoreMenuOpen(false) }}>
                <Pencil size={15} />
                Tulis email
              </button>
              <button onClick={() => handleMark('sudah dibaca')}>
                <MailOpen size={15} />
                Tandai sudah dibaca
              </button>
              <button onClick={() => handleMark('belum dibaca')}>
                <MailCheck size={15} />
                Tandai belum dibaca
              </button>
            </div>
          )}
        </div>

        {selected.size > 0 && (
          <div className={styles.bulkActions}>
            <div className={styles.divider} />
            <button
              className={styles.iconBtn}
              title={isTrashFolder ? 'Hapus permanen yang dipilih' : 'Pindahkan ke Sampah'}
              id="toolbar-delete-btn"
              onClick={handleBulkDelete}
            >
              <Trash2 size={16} />
            </button>
            <span className={styles.selCount}>{selected.size} dipilih</span>
          </div>
        )}
      </div>

      <div className={styles.right}>
        <div className={styles.pagination}>
          <span className={styles.paginationInfo}>
            {total === 0 ? '0' : `${start}-${end}`} dari {total.toLocaleString('id-ID')}
          </span>
          <button
            className={styles.iconBtn}
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            title="Halaman sebelumnya"
            id="toolbar-prev-btn"
          >
            {'<'}
          </button>
          <button
            className={styles.iconBtn}
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            title="Halaman berikutnya"
            id="toolbar-next-btn"
          >
            {'>'}
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
      <ConfirmDialog
        open={deleteDialogOpen}
        title="Konfirmasi penghapusan pesan"
        message={
          isTrashFolder
            ? `Tindakan ini akan menghapus permanen ${selected.size} email terpilih. Apakah Anda yakin ingin melanjutkan?`
            : `Tindakan ini akan memindahkan ${selected.size} email terpilih ke Sampah. Apakah Anda yakin ingin melanjutkan?`
        }
        onCancel={() => setDeleteDialogOpen(false)}
        onConfirm={confirmBulkDelete}
      />
    </>
  )
}
