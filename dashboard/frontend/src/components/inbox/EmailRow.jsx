import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { Mail, MailOpen, Paperclip, RotateCcw, Star, Trash2, Archive } from 'lucide-react'
import { useDeleteEmail, useReleaseEmail, useRestoreEmail, useToggleReadEmail, useToggleStarred } from '../../api/emails'
import { useToast } from '../../hooks/useToast'
import { useTranslation } from '../../i18n/context'
import api from '../../api/client'
import ConfirmDialog from '../common/ConfirmDialog'
import { APP_TIME_ZONE, formatAppDate } from '../../utils/time'
import { getActiveMailboxId } from '../../utils/mailbox'
import { useMe } from '../../api/auth'
import styles from './EmailRow.module.css'

function timeAgo(date) {
  const value = new Date(date)
  if (Number.isNaN(value.getTime())) return ''
  const now = new Date()
  const sameDay = value.toLocaleDateString('en-CA', { timeZone: APP_TIME_ZONE }) === now.toLocaleDateString('en-CA', { timeZone: APP_TIME_ZONE })
  if (sameDay) {
    return value.toLocaleTimeString('id-ID', { timeZone: APP_TIME_ZONE, hour: '2-digit', minute: '2-digit' }).replace(':', '.')
  }
  if (value.toLocaleDateString('en-CA', { timeZone: APP_TIME_ZONE, year: 'numeric' }) === now.toLocaleDateString('en-CA', { timeZone: APP_TIME_ZONE, year: 'numeric' })) {
    return formatAppDate(value, { day: '2-digit', month: 'short' })
  }
  return formatAppDate(value, { day: '2-digit', month: 'short', year: 'numeric' })
}

export default function EmailRow({
  email,
  isRead,
  isSelected,
  onToggleSelect,
  isStarred,
  onToggleStar,
  onSetRead,
  senderLabel,
  openDraftMode = 'compose',
  activeEmailId = null,
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { data: meData } = useMe()
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const { mutateAsync: deleteEmail } = useDeleteEmail()
  const { mutateAsync: releaseEmail } = useReleaseEmail()
  const { mutateAsync: restoreEmail } = useRestoreEmail()
  const { mutateAsync: toggleRead } = useToggleReadEmail()
  const { mutate: toggleStarred } = useToggleStarred()
  const { showToast } = useToast()

  const verdict = (email.label || email.final_verdict || email.ensemble_verdict || 'clean').toLowerCase()
  const isDraft = (email.label || '').toUpperCase() === 'DRAFT' || email.status === 'draft'
  const effectiveIsRead = typeof isRead === 'boolean' ? isRead : email.is_read
  const isTrash = email.status === 'trash'
  const draftRecipients = String(email.recipient_list || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .join(', ')
  const displaySender = senderLabel || (isDraft ? draftRecipients : (email.sender || email.sender_email || ''))

  const setRead = (shouldRead) => {
    if (effectiveIsRead === shouldRead) return
    toggleRead({ emailId: email.email_id, isRead: shouldRead }).catch(() => {})
    onSetRead?.(email.email_id, shouldRead)
  }

  const markAsRead = () => {
    setRead(true)
  }

  const handleQuickToggleRead = (e) => {
    e.stopPropagation()
    const nextRead = !effectiveIsRead
    setRead(nextRead)
    showToast(nextRead ? t('emailRow.markAsRead') : t('emailRow.markAsUnread'), 'info')
  }

  const handleToggleStar = (e) => {
    e.stopPropagation()
    if (onToggleStar) {
      onToggleStar(email.email_id)
      return
    }
    toggleStarred({ emailId: email.email_id, isStarred: !isStarred })
  }

  const handleRowClick = () => {
    markAsRead()
    const search = window.location.search || ''
    const params = new URLSearchParams(search)

    if (isDraft) {
      window.dispatchEvent(new CustomEvent('open-compose', {
        detail: {
          draft_id: email.email_id,
          to: email.recipient_list || '',
          subject: email.subject === '(tanpa subjek)' ? '' : email.subject || '',
          body: email.raw_content || email.body_text || '',
          attachments: (email.attachments || []).map((file) => ({
            name: file.filename,
            size: file.size,
            type: file.content_type,
            index: file.index,
            stored: file.stored,
            existing: true,
          })),
          thread_id: email.thread_id || '',
          parent_email_id: email.parent_email_id || '',
          compose_mode: openDraftMode,
        },
      }))
      return
    }

    const fromPath = `${window.location.pathname}${window.location.search}`
    params.set('from', fromPath)
    const activeMId = getActiveMailboxId(params)
    if (activeMId) params.set('mailbox_id', activeMId)

    const targetUrl = activeMId
      ? `/mail/${encodeURIComponent(activeMId)}/email/${email.email_id}?${params.toString()}`
      : `/email/${email.email_id}?${params.toString()}`
    navigate(targetUrl)
  }

  const handleQuickDelete = (e) => {
    e.stopPropagation()
    setDeleteDialogOpen(true)
  }

  const confirmQuickDelete = async () => {
    try {
      await deleteEmail(email.email_id)
      showToast(isTrash ? t('emailRow.deletedPermanent') : t('emailRow.movedToTrash'), 'success')
      setDeleteDialogOpen(false)
    } catch (err) {
      showToast(err.response?.data?.detail || t('emailRow.deleteError'), 'error')
    }
  }

  const handleQuickRestore = async (e) => {
    e.stopPropagation()
    try {
      await restoreEmail(email.email_id)
      showToast(t('emailRow.restoreSuccess'), 'success')
    } catch { showToast(t('emailRow.restoreError'), 'error') }
  }

  const handleQuickRelease = async (e) => {
    e.stopPropagation()
    try {
      await releaseEmail(email.email_id)
      showToast(t('emailRow.releaseSuccess'), 'success')
    } catch { showToast(t('emailRow.releaseError'), 'error') }
  }

  return (
    <>
      <div
        className={`${styles.row} ${effectiveIsRead ? styles.read : ''} ${isSelected ? styles.selected : ''} ${activeEmailId && (email.email_id === activeEmailId || (email.thread_email_ids || []).includes(activeEmailId)) ? styles.activeRow : ''}`}
        onClick={handleRowClick}
      >
        <div className={styles.actions}>
          <input
            type="checkbox"
            checked={isSelected}
            onChange={(e) => { e.stopPropagation(); onToggleSelect(email.email_id) }}
            className={styles.checkbox}
          />
          {!isTrash && (
            <button
              className={`${styles.starBtn} ${isStarred ? styles.starActive : ''}`}
              onClick={handleToggleStar}
              title={isStarred ? t('emailRow.unmarkImportant') : t('emailRow.markImportant')}
            >
              <Star size={15} fill={isStarred ? '#f2c94c' : 'none'} color={isStarred ? '#f2c94c' : '#5f6368'} />
            </button>
          )}
        </div>

        <div className={styles.senderCol}>
          <span className={styles.sender}>{displaySender}</span>
        </div>

        <div className={styles.body}>
          <span className={styles.subject}>
            {email.subject || t('common.noSubject')}
            {email._threadCount > 1 && (
              <span className={styles.threadCountBadge}>{email._threadCount}</span>
            )}
            {email._hasDraftInThread && (
              <span className={styles.threadDraftIndicator}>{t('emailRow.draftLabel')}</span>
            )}
          </span>
          <span className={styles.separator}>-</span>
          <span className={styles.preview}>
            {email.body_preview || email.body_text?.slice(0, 120) || ''}
          </span>
        </div>

        <div className={styles.quickActions}>
          {isTrash && (
            <button className={styles.quickBtn} onClick={handleQuickRestore} title={t('emailRow.restore')}>
              <RotateCcw size={18} />
            </button>
          )}
          {verdict === 'quarantine' && (
            <button className={styles.quickBtn} onClick={handleQuickRelease} title={t('emailRow.release')}>
              <Archive size={18} />
            </button>
          )}
          <button
            className={styles.quickBtn}
            onClick={handleQuickToggleRead}
            title={effectiveIsRead ? t('emailRow.markAsUnreadBtn') : t('emailRow.markAsReadBtn')}
            aria-label={effectiveIsRead ? t('emailRow.markAsUnreadBtn') : t('emailRow.markAsReadBtn')}
          >
            {effectiveIsRead ? <Mail size={18} /> : <MailOpen size={18} />}
          </button>
          {!isTrash && (
            <button className={styles.quickBtn} onClick={handleQuickDelete} title={t('emailRow.delete')}>
              <Trash2 size={18} />
            </button>
          )}
        </div>

        <span className={styles.time}>
          {email.has_attachments && <Paperclip size={14} className={styles.attachmentIcon} />}
          {timeAgo(email.timestamp || email.received_at)}
        </span>
      </div>
      <ConfirmDialog
        open={deleteDialogOpen}
        title={t('emailRow.confirmDeleteTitle')}
        message={isDraft
          ? t('emailRow.confirmDeleteDraft')
          : t('emailRow.confirmDeleteEmail')}
        onCancel={() => setDeleteDialogOpen(false)}
        onConfirm={confirmQuickDelete}
      />
    </>
  )
}
