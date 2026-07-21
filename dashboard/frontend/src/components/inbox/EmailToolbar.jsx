import { useEffect, useRef, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import { useTranslation } from '../../i18n/context'
import { ChevronDown, MailCheck, MailOpen, MoreVertical, Pencil, RefreshCw, Trash2 } from 'lucide-react'
import { useDeleteEmail, useToggleReadEmail } from '../../api/emails'
import { useToast } from '../../hooks/useToast'
import ConfirmDialog from '../common/ConfirmDialog'
import styles from './EmailToolbar.module.css'

const PAGE_SIZE = 50

export default function EmailToolbar({
  total,
  shown,
  page,
  view = '',
  onPageChange,
  selected,
  allIds,
  onSelectAll,
  onRefresh,
}) {
  const { t } = useTranslation()
  const [selectMenuOpen, setSelectMenuOpen] = useState(false)
  const [moreMenuOpen, setMoreMenuOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const selectMenuRef = useRef(null)
  const moreMenuRef = useRef(null)
  const allSelected = selected.size === allIds.length && allIds.length > 0
  const someSelected = selected.size > 0 && !allSelected
  const isTrashFolder = view === 'trash'
    || searchParams.get('folder') === 'trash'
    || location.pathname === '/trash'
    || /\/mail\/[^/]+\/trash$/.test(location.pathname)
  const isDraftPage = view === 'draft'
    || location.pathname === '/draft'
    || /\/mail\/[^/]+\/drafts$/.test(location.pathname)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const start = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const end = Math.min(page * PAGE_SIZE, total)

  const { mutateAsync: deleteEmail } = useDeleteEmail()
  const { mutateAsync: toggleRead } = useToggleReadEmail()
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
      showToast(t('toolbar.selectFirst'), 'info')
      return
    }
    setDeleteDialogOpen(true)
  }

  const confirmBulkDelete = async () => {
    try {
      const promises = Array.from(selected).map((id) => deleteEmail(id))
      await Promise.all(promises)
      if (isTrashFolder) showToast(t('toolbar.deletedPermanent').replace('{n}', selected.size), 'success')
      setDeleteDialogOpen(false)
      onSelectAll(false)
      onRefresh()
    } catch (err) {
      showToast(t('toolbar.deleteError'), 'error')
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

  const handleMark = async (isRead) => {
    if (selected.size === 0) {
      showToast(t('toolbar.selectFirst'), 'info')
      return
    }
    try {
      await Promise.all(Array.from(selected).map((id) => toggleRead({ emailId: id, isRead })))
      showToast(t(isRead ? 'toolbar.markedAsRead' : 'toolbar.markedAsUnread').replace('{n}', selected.size), 'success')
    } catch {
      showToast(t('toolbar.markReadError'), 'error')
    }
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
            title={t('toolbar.selectAll')}
          />
          <button
            className={styles.chevronBtn}
            title={t('toolbar.selectOptions')}
            onClick={(e) => { e.stopPropagation(); setSelectMenuOpen((v) => !v) }}
          >
            <ChevronDown size={14} />
          </button>
          {selectMenuOpen && (
            <div className={styles.menu} style={{ left: 0 }}>
              <button onClick={() => { onSelectAll(true); setSelectMenuOpen(false) }}>{t('toolbar.all')}</button>
              <button onClick={() => { onSelectAll(false); setSelectMenuOpen(false) }}>{t('toolbar.none')}</button>
              <button onClick={() => { onSelectAll(!allSelected); setSelectMenuOpen(false) }}>
                {allSelected ? t('toolbar.deselectPage') : t('toolbar.selectPage')}
              </button>
            </div>
          )}
        </div>

        <button
          className={`${styles.iconBtn} ${refreshing ? styles.spinning : ''}`}
          onClick={handleRefreshClick}
          title={t('toolbar.refresh')}
          id="toolbar-refresh-btn"
        >
          <RefreshCw size={16} />
        </button>

        <div className={styles.moreWrap} ref={moreMenuRef}>
          <button
            className={styles.iconBtn}
            onClick={(e) => { e.stopPropagation(); setMoreMenuOpen((v) => !v) }}
            title={t('toolbar.moreOptions')}
            id="toolbar-more-btn"
          >
            <MoreVertical size={16} />
          </button>
          {moreMenuOpen && (
            <div className={styles.menu}>
              <button onClick={() => { handleComposeClick(); setMoreMenuOpen(false) }}>
                <Pencil size={15} />
                {t('toolbar.compose')}
              </button>
              <button onClick={() => handleMark(true)}>
                <MailOpen size={15} />
                {t('toolbar.markAsRead')}
              </button>
              <button onClick={() => handleMark(false)}>
                <MailCheck size={15} />
                {t('toolbar.markAsUnread')}
              </button>
            </div>
          )}
        </div>

        {selected.size > 0 && (
          <div className={styles.bulkActions}>
            <div className={styles.divider} />
            <button
              className={styles.iconBtn}
              title={isTrashFolder ? t('toolbar.deletePermanent') : t('toolbar.moveToTrash')}
              id="toolbar-delete-btn"
              onClick={handleBulkDelete}
            >
              <Trash2 size={16} />
            </button>
            <span className={styles.selCount}>{selected.size} {t('toolbar.selected')}</span>
          </div>
        )}
      </div>

      <div className={styles.right}>
        <div className={styles.pagination}>
          <span className={styles.paginationInfo}>
            {total === 0 ? '0' : `${start}-${end}`} {t('toolbar.of')} {total.toLocaleString('id-ID')}
          </span>
          <button
            className={styles.iconBtn}
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            title={t('toolbar.prevPage')}
            id="toolbar-prev-btn"
          >
            {'<'}
          </button>
          <button
            className={styles.iconBtn}
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            title={t('toolbar.nextPage')}
            id="toolbar-next-btn"
          >
            {'>'}
          </button>
        </div>

        <button
          className={`${styles.iconBtn} ${styles.composeShortcut}`}
          onClick={handleComposeClick}
          title={t('toolbar.newEmail')}
          id="toolbar-compose-shortcut-btn"
        >
          <Pencil size={16} />
        </button>
      </div>
      </div>
      <ConfirmDialog
        open={deleteDialogOpen}
        title={t('toolbar.confirmDeleteTitle')}
        message={
          isTrashFolder
            ? t('toolbar.confirmDeletePermanent').replace('{n}', selected.size)
            : isDraftPage
            ? t('toolbar.confirmDeleteDraft').replace('{n}', selected.size)
            : t('toolbar.confirmDeleteTrash').replace('{n}', selected.size)
        }
        onCancel={() => setDeleteDialogOpen(false)}
        onConfirm={confirmBulkDelete}
      />
    </>
  )
}
