import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { Archive, Mail, MailOpen, Paperclip, RotateCcw, Star, Trash2 } from 'lucide-react'
import { useDeleteEmail, useReleaseEmail, useRestoreEmail } from '../../api/emails'
import { useToast } from '../../hooks/useToast'
import api from '../../api/client'
import ConfirmDialog from '../common/ConfirmDialog'
import styles from './EmailRow.module.css'

function timeAgo(date) {
  const value = new Date(date)
  if (Number.isNaN(value.getTime())) return ''
  const now = new Date()
  const sameDay = value.toDateString() === now.toDateString()
  if (sameDay) {
    return value.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }).replace(':', '.')
  }
  if (value.getFullYear() === now.getFullYear()) {
    return value.toLocaleDateString('id-ID', { day: '2-digit', month: 'short' })
  }
  return value.toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' })
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
}) {
  const navigate = useNavigate()
  const [localReadIds, setLocalReadIds] = useState(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem('cognimail.read') || '[]'))
    } catch {
      return new Set()
    }
  })
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const { mutateAsync: deleteEmail } = useDeleteEmail()
  const { mutateAsync: releaseEmail } = useReleaseEmail()
  const { mutateAsync: restoreEmail } = useRestoreEmail()
  const { showToast } = useToast()

  const verdict = (email.label || email.final_verdict || email.ensemble_verdict || 'clean').toLowerCase()
  const isDraft = (email.label || '').toUpperCase() === 'DRAFT' || email.status === 'draft'
  const effectiveIsRead = typeof isRead === 'boolean' ? isRead : localReadIds.has(email.email_id)
  const isTrash = email.status === 'trash'
  const displaySender = senderLabel || email.sender || email.sender_email || 'unknown'

  const setRead = (shouldRead) => {
    setLocalReadIds((prev) => {
      const next = new Set(prev)
      if (shouldRead) next.add(email.email_id)
      else next.delete(email.email_id)
      try {
        localStorage.setItem('cognimail.read', JSON.stringify(Array.from(next)))
      } catch {
        // Some restricted browser contexts can block localStorage writes.
      }
      return next
    })
    onSetRead?.(email.email_id, shouldRead)
  }

  const markAsRead = () => {
    setRead(true)
  }

  const handleQuickToggleRead = (e) => {
    e.stopPropagation()
    const nextRead = !effectiveIsRead
    setRead(nextRead)
    showToast(nextRead ? 'Email ditandai sudah dibaca' : 'Email ditandai belum dibaca', 'info')
  }

  const htmlToPlainText = (value) => {
    const normalized = String(value || '')
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<\/p>/gi, '\n')
      .replace(/<\/div>/gi, '\n')
    const element = document.createElement('div')
    element.innerHTML = normalized
    return (element.textContent || element.innerText || '').replace(/\n{3,}/g, '\n\n').trim()
  }

  const fileFromAttachment = async (attachment) => {
    if (!attachment?.stored) return null
    const response = await api.get(`/emails/${email.email_id}/attachments/${attachment.index}`, {
      responseType: 'blob',
    })
    return new File(
      [response.data],
      attachment.filename || `attachment-${attachment.index + 1}`,
      { type: attachment.content_type || response.data.type || 'application/octet-stream' }
    )
  }

  const openDraftCompose = async () => {
    try {
      const { data } = await api.get(`/emails/${email.email_id}`)
      const files = (await Promise.all((data.attachments || []).map(fileFromAttachment))).filter(Boolean)
      window.dispatchEvent(new CustomEvent('open-compose', {
        detail: {
          draft_id: data.email_id,
          to: data.recipient_list || '',
          subject: data.subject === '(tanpa subjek)' ? '' : data.subject || '',
          body: htmlToPlainText(data.raw_content || ''),
          attachments: files,
        },
      }))
    } catch (err) {
      showToast(err.response?.data?.detail || 'Gagal membuka draf', 'error')
    }
  }

  const handleRowClick = (e) => {
    if (e.target.closest(`.${styles.checkboxWrap}, .${styles.starBtn}, .${styles.quickBtn}`)) return
    if (isDraft) {
      openDraftCompose()
      return
    }
    markAsRead()
    const from = `${window.location.pathname}${window.location.search}`
    const currentParams = new URLSearchParams(window.location.search)
    const detailParams = new URLSearchParams({ from })
    const mailbox = currentParams.get('mailbox')
    const mailboxId = currentParams.get('mailbox_id')
    if (mailbox) detailParams.set('mailbox', mailbox)
    if (mailboxId) detailParams.set('mailbox_id', mailboxId)
    navigate(`/email/${email.email_id}?${detailParams.toString()}`)
  }

  const handleQuickDelete = async (e) => {
    e.stopPropagation()
    setDeleteDialogOpen(true)
  }

  const confirmQuickDelete = async () => {
    try {
      await deleteEmail(email.email_id)
      setDeleteDialogOpen(false)
    } catch (err) {
      showToast(err.response?.data?.detail || 'Gagal menghapus email', 'error')
    }
  }

  const handleQuickRestore = async (e) => {
    e.stopPropagation()
    try {
      await restoreEmail(email.email_id)
      showToast('Email dipulihkan', 'success')
    } catch { showToast('Gagal memulihkan email', 'error') }
  }

  const handleQuickRelease = async (e) => {
    e.stopPropagation()
    try {
      await releaseEmail(email.email_id)
      showToast('Email dirilis ke inbox', 'success')
    } catch { showToast('Gagal melepas', 'error') }
  }

  return (
    <>
      <div
        className={`${styles.row} ${effectiveIsRead ? styles.read : ''} ${isSelected ? styles.selected : ''}`}
        onClick={handleRowClick}
      >
      <div className={styles.actions}>
        <div className={styles.checkboxWrap}>
          <input
            type="checkbox"
            checked={isSelected}
            onChange={() => onToggleSelect(email.email_id)}
            className={styles.checkbox}
          />
        </div>
        {!isTrash && (
          <button
            className={`${styles.starBtn} ${isStarred ? styles.starActive : ''}`}
            onClick={(e) => { e.stopPropagation(); onToggleStar?.(email.email_id) }}
            title={isStarred ? 'Batal penting' : 'Tandai penting'}
          >
            <Star size={15} fill={isStarred ? 'var(--star-color, #f2c94c)' : 'none'} />
          </button>
        )}
      </div>

      <div className={styles.senderCol}>
        <span className={styles.sender}>{displaySender}</span>
      </div>

      <div className={styles.body}>
        <span className={styles.subject}>{email.subject || '(no subject)'}</span>
        <span className={styles.separator}>-</span>
        <span className={styles.preview}>
          {email.body_preview || email.body_text?.slice(0, 120) || ''}
        </span>
      </div>

      <div className={styles.quickActions}>
        {isTrash && (
          <button className={styles.quickBtn} onClick={handleQuickRestore} title="Pulihkan">
            <RotateCcw size={18} />
          </button>
        )}
        {verdict === 'quarantine' && (
          <button className={styles.quickBtn} onClick={handleQuickRelease} title="Rilis ke inbox">
            <Archive size={18} />
          </button>
        )}
        <button
          className={styles.quickBtn}
          onClick={handleQuickToggleRead}
          title={effectiveIsRead ? 'Tandai belum dibaca' : 'Tandai sudah dibaca'}
          aria-label={effectiveIsRead ? 'Tandai belum dibaca' : 'Tandai sudah dibaca'}
        >
          {effectiveIsRead ? <Mail size={18} /> : <MailOpen size={18} />}
        </button>
        {!isTrash && (
          <button className={styles.quickBtn} onClick={handleQuickDelete} title="Hapus">
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
        title="Konfirmasi penghapusan pesan"
        message="Email ini akan dipindahkan ke Sampah. Anda yakin ingin melanjutkan?"
        onCancel={() => setDeleteDialogOpen(false)}
        onConfirm={confirmQuickDelete}
      />
    </>
  )
}
