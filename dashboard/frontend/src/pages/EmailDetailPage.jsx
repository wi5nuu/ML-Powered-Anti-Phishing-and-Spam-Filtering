import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Reply, MoreVertical, Trash2, Mail,
  Printer, ExternalLink, Star, ShieldAlert,
  ChevronLeft, ChevronRight, CornerUpRight, ChevronDown, ChevronRight as ChevronRightIcon, X, Paperclip, Download,
  Ban, Code2, Link, Image
} from 'lucide-react'
import api from '../api/client'
import GmailShell from '../components/layout/GmailShell'
import ConfirmDialog from '../components/common/ConfirmDialog'
import {
  useEmail,
  useEmails,
  useReleaseEmail,
  useConfirmSpam,
  useReportFalsePositive,
  useDeleteEmail
} from '../api/emails'
import { useMe } from '../api/auth'
import { useToast } from '../hooks/useToast'
import { useEffect, useRef, useState } from 'react'
import { getActiveMailbox, getActiveMailboxId } from '../utils/mailbox'
import { formatAppDateTime } from '../utils/time'
import { findExistingDraft } from '../utils/threadUtils'
import styles from './EmailDetailPage.module.css'

const BADGE_CFG = {
  quarantine: { text: 'KARANTINA', cls: styles.badgeQ },
  warn: { text: 'PERINGATAN', cls: styles.badgeW },
  clean: { text: 'BERSIH', cls: styles.badgeC },
}

function formatBytes(bytes = 0) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / Math.pow(1024, index)).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

function escapeHtml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function decodeHtmlEntities(value = '') {
  if (typeof window === 'undefined' || typeof document === 'undefined') return String(value || '')
  const textarea = document.createElement('textarea')
  textarea.innerHTML = String(value || '')
  return textarea.value
}

function looksLikeHtml(value = '') {
  return /<(html|body|table|tbody|tr|td|div|p|span|a|img|br|font|center|head|title)\b[\s\S]*>/i.test(value)
}

function looksLikeEscapedHtml(value = '') {
  return /&lt;(?:!doctype\s+html|html|head|body|table|tbody|tr|td|div|p|span|img|font|center)\b/i.test(value)
}

function findHtmlDocumentStart(value = '') {
  const match = String(value || '').match(/<!doctype\s+html\b|<(?:html|head|body|table|center|div|p|font)\b/i)
  return match ? match.index : -1
}

function removeGeneratedLinks(value = '') {
  return String(value || '').replace(/<a\b[^>]*>([\s\S]*?)<\/a>/gi, '$1')
}

function sanitizeEmailHtml(value = '') {
  if (typeof window === 'undefined' || typeof DOMParser === 'undefined') return escapeHtml(value)
  const parser = new DOMParser()
  const doc = parser.parseFromString(String(value || ''), 'text/html')

  doc.querySelectorAll('script, iframe, object, embed, form, input, button, textarea, select, meta, link').forEach((node) => node.remove())
  doc.querySelectorAll('*').forEach((node) => {
    Array.from(node.attributes).forEach((attr) => {
      const name = attr.name.toLowerCase()
      const attrValue = attr.value || ''
      if (name.startsWith('on')) {
        node.removeAttribute(attr.name)
        return
      }
      if ((name === 'href' || name === 'src') && /^\s*javascript:/i.test(attrValue)) {
        node.removeAttribute(attr.name)
        return
      }
      if (name === 'srcset') node.removeAttribute(attr.name)
    })

    if (node.tagName?.toLowerCase() === 'a') {
      node.setAttribute('target', '_blank')
      node.setAttribute('rel', 'noopener noreferrer')
    }
  })

  return doc.body.innerHTML
}

function safeFilename(value = 'email') {
  return `${(value || 'email').replace(/[\\/:*?"<>|]+/g, '_').slice(0, 120)}.eml`
}

function normalizeRecipients(value) {
  if (Array.isArray(value)) return value.filter(Boolean)
  if (typeof value === 'string') {
    const emails = value.match(/[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}/gi)
    if (emails?.length) return Array.from(new Set(emails.map((item) => item.toLowerCase())))
    return value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
  }
  return []
}

function parseEmailIdentity(value = '') {
  const text = String(value || '').trim()
  const angleMatch = text.match(/^(.*?)\s*<([^>]+)>$/)
  if (angleMatch) {
    return {
      name: angleMatch[1].trim().replace(/^"|"$/g, '') || angleMatch[2].trim(),
      email: angleMatch[2].trim(),
    }
  }
  const emailMatch = text.match(/[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}/i)
  return {
    name: emailMatch ? text.replace(emailMatch[0], '').replace(/[<>]/g, '').trim() || emailMatch[0] : text,
    email: emailMatch ? emailMatch[0] : '',
  }
}

function stripRawHeaders(value = '') {
  const text = String(value || '')
  const normalized = text.replace(/\r\n/g, '\n')
  const splitAt = normalized.indexOf('\n\n')
  if (splitAt === -1) return text
  const firstBlock = normalized.slice(0, splitAt)
  const looksLikeHtmlHeader = firstBlock
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .some((line) => /^(from|to|subject|date|message-id|reply-to|cc|bcc|spf|dkim|dmarc):\s*/i.test(line))
  return looksLikeHtmlHeader ? normalized.slice(splitAt + 2) : text
}

function renderEmailBody(value = '', fallback = '') {
  const body = stripRawHeaders(value || fallback)
  if (looksLikeEscapedHtml(body)) {
    const normalized = removeGeneratedLinks(body)
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/\r\n/g, '\n')
      .replace(/\r/g, '\n')
    const decoded = decodeHtmlEntities(normalized)
    const htmlStart = findHtmlDocumentStart(decoded)
    if (htmlStart > 0) {
      const intro = decoded.slice(0, htmlStart).trim()
      const htmlPart = decoded.slice(htmlStart)
      const introHtml = intro ? `${escapeHtml(intro).replace(/\n/g,'<br />')}<br /><br />` : ''
      return `${introHtml}${sanitizeEmailHtml(htmlPart)}`
    }
    if (htmlStart === 0 || looksLikeHtml(decoded)) return sanitizeEmailHtml(decoded)
  }
  if (looksLikeHtml(body)) return sanitizeEmailHtml(body)
  const decoded = decodeHtmlEntities(body)
  if (decoded !== body && looksLikeHtml(decoded)) {
    const firstTagIndex = findHtmlDocumentStart(decoded)
    if (firstTagIndex > 0) {
      const intro = decoded.slice(0, firstTagIndex).trim()
      const htmlPart = decoded.slice(firstTagIndex)
      const introHtml = intro ? `${escapeHtml(intro).replace(/\n/g,'<br />')}<br /><br />` : ''
      return `${introHtml}${sanitizeEmailHtml(htmlPart)}`
    }
    return sanitizeEmailHtml(decoded)
  }
  return escapeHtml(body).replace(/\n/g, '<br />')
}

function plainFromHtmlish(value = '') {
  return String(value || '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
}

function stripQuotedThread(value = '') {
  const plain = plainFromHtmlish(stripRawHeaders(value))
  const metadataQuoteIndex = plain.search(/\n?\s*(?:Dari:\s*.+\n)?Tanggal:\s*.+\nSubjek:\s*.+\nKepada:\s*/i)
  if (metadataQuoteIndex >= 0) return plain.slice(0, metadataQuoteIndex).trim()
  const [body] = plain.split(/\n\s*-{5,}\s*(?:Original|Forwarded) message\s*-{5,}\s*/i)
  return (body || plain).trim()
}

function splitQuotedThread(value = '') {
  const plain = plainFromHtmlish(stripRawHeaders(value))
  const match = plain.match(/\n\s*(-{5,}\s*(?:Original|Forwarded) message\s*-{5,}\s*[\s\S]*)/i)
  if (!match) return { body: plain.trim(), quote: '' }
  return { body: plain.slice(0, match.index).trim(), quote: match[1].trim() }
}

function attachmentUrl(emailId, attachment, download = false) {
  const suffix = download ? '?download=true' : ''
  return `/api/emails/${encodeURIComponent(emailId)}/attachments/${attachment.index}${suffix}`
}

function attachmentKind(attachment) {
  const type = String(attachment?.content_type || '').toLowerCase()
  const name = String(attachment?.filename || '').toLowerCase()
  if (type.startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp)$/i.test(name)) return 'image'
  if (type === 'application/pdf' || name.endsWith('.pdf')) return 'pdf'
  if (type.startsWith('text/') || /\.(txt|log|csv|md)$/i.test(name)) return 'text'
  return 'file'
}

const getMockBody = (subject, sender) => `
  <div style="font-family:'Google Sans',Roboto,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e0e0e0;border-radius:8px;padding:24px;background:#ffffff;">
    <div style="border-bottom:1px solid #eeeeee;padding-bottom:16px;margin-bottom:20px;">
      <h2 style="margin:0 0 8px 0;font-size:18px;color:#202124;">${subject || '(Tanpa Subjek)'}</h2>
      <div style="font-size:13px;color:#5f6368;">Dari: <strong>${sender || 'Pengirim tidak diketahui'}</strong></div>
    </div>
    <div style="line-height:1.6;color:#202124;font-size:14px;">
      <p>Halo,</p>
      <p>Pesan ini dikirimkan oleh <strong>${sender || 'sistem luar'}</strong> dan telah dievaluasi oleh CogniMail.</p>
      <p style="padding:16px;background:#f8f9fa;border-radius:4px;border-left:4px solid #1a73e8;font-style:italic;color:#3c4043;">
        Jika ini adalah email ancaman karantina, silakan periksa parameter deteksi ML dan rincian SHAP di panel keamanan kanan.
      </p>
    </div>
  </div>
`


function SecuritySection({ id, title, isOpen, onToggle, children }) {
  return (
    <div className={`${styles.card} ${!isOpen ? styles.cardClosed : ''}`}>
      <button className={styles.cardToggle} onClick={() => onToggle(id)}>
        <span>{title}</span>
        {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
      </button>
      {isOpen && <div className={styles.cardBody}>{children}</div>}
    </div>
  )
}

function SecurityPanelWrapper({ onClose, children }) {
  return (
    <div className={styles.securityWrapper}>
      <div className={styles.securityWrapperHeader}>
        <span>Panel Deteksi Keamanan</span>
        <button className={styles.securityCloseBtn} onClick={onClose} title="Tutup panel">
          <X size={18} />
        </button>
      </div>
      <div className={styles.securityWrapperBody}>
        {children}
      </div>
    </div>
  )
}

export default function EmailDetailPage() {
  const { emailId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const { showToast } = useToast()
  const fromPath = searchParams.get('from') || ''
  const originalView = searchParams.get('original') === '1'
  const fromParams = new URLSearchParams(fromPath.split('?')[1] || '')
  const activeMailboxId = getActiveMailboxId(searchParams) || getActiveMailboxId(fromParams)
  const activeMailbox = getActiveMailbox(searchParams) || getActiveMailbox(fromParams)

  const getListFilter = (source) => {
    const mailSection = source.match(/^\/mail\/[^/]+\/([^/?]+)/)?.[1] || ''
    if (mailSection === 'sent') return 'sent'
    if (mailSection === 'drafts') return 'draft'
    if (mailSection === 'all') return 'allmail'
    if (mailSection === 'trash') return 'trash'
    if (['spam', 'phishing', 'malware'].includes(mailSection)) return mailSection
    if (source.startsWith('/sent')) return 'sent'
    if (!source.startsWith('/inbox')) return 'all'
    const query = source.split('?')[1] || ''
    const params = new URLSearchParams(query)
    const folder = params.get('folder')
    const category = params.get('category')
    if (folder === 'allmail') return 'allmail'
    if (folder === 'trash') return 'trash'
    if (folder === 'draft') return 'draft'
    if (category) return category
    return 'all'
  }

  const { data: email, isLoading, isError } = useEmail(emailId)
  const listFilter = getListFilter(fromPath)
  const { data: emailsData } = useEmails(listFilter)
  const { data: allDraftsData } = useEmails('draft')
  const { data: meData } = useMe()

  const { mutate: release, isPending: releasing } = useReleaseEmail()
  const { mutate: confirmSpam, isPending: spamming } = useConfirmSpam()
  const { mutate: reportFP, isPending: reporting } = useReportFalsePositive()
  const { mutate: deleteEmail, isPending: deleting } = useDeleteEmail()

  const [fpNotes, setFpNotes] = useState('')
  const [threadRecipientDetailId, setThreadRecipientDetailId] = useState(null)
  const [replyMode, setReplyMode] = useState(null)
  const [replyTargetMessage, setReplyTargetMessage] = useState(null)
  const [replyTo, setReplyTo] = useState('')
  const [replySubject, setReplySubject] = useState('')
  const [replyBody, setReplyBody] = useState('')
  const [messageMenuAnchor, setMessageMenuAnchor] = useState(null)
  const [replyActionMenuOpen, setReplyActionMenuOpen] = useState(false)
  const [replyLinkOpen, setReplyLinkOpen] = useState(false)
  const [replyLinkText, setReplyLinkText] = useState('')
  const [replyLinkUrl, setReplyLinkUrl] = useState('')
  const [replyAttachments, setReplyAttachments] = useState([])
  const [replyQuoteExpanded, setReplyQuoteExpanded] = useState(false)
  const [expandedQuoteIds, setExpandedQuoteIds] = useState(() => new Set())
  const [previewAttachment, setPreviewAttachment] = useState(null)
  const [savingReplyDraft, setSavingReplyDraft] = useState(false)
  const [replyDraftId, setReplyDraftId] = useState('')
  const [hydratedDraftId, setHydratedDraftId] = useState('')
  const [inlineSentReplies, setInlineSentReplies] = useState([])
  const replyAutosaveTimerRef = useRef(null)
  const replyAutosaveSignatureRef = useRef('')
  const replyDraftIdRef = useRef('')
  const [securityPanelOpen, setSecurityPanelOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [openPanels, setOpenPanels] = useState({ actions: true, scores: true, xai: true, metadata: false })
  const [localStarred, setLocalStarred] = useState(null)
  const [isUnread, setIsUnread] = useState(false)

  useEffect(() => {
    try {
      const readIds = new Set(JSON.parse(localStorage.getItem('cognimail.read') || '[]'))
      setIsUnread(!readIds.has(emailId))
    } catch { setIsUnread(false) }
  }, [emailId])

  useEffect(() => {
    setInlineSentReplies([])
    setHydratedDraftId('')
    setExpandedQuoteIds(new Set())
    setReplyQuoteExpanded(false)
    setThreadRecipientDetailId(null)
  }, [emailId])

  // Hydrate reply composer from a draft email opened directly
  useEffect(() => {
    if (!email) return
    const isDraftEmail = String(email.label || '').toUpperCase() === 'DRAFT' || email.status === 'draft'
    if (!isDraftEmail || hydratedDraftId === email.email_id) return
    const messages = Array.isArray(email.thread_messages) && email.thread_messages.length > 0
      ? email.thread_messages : [email]
    const nonDraftMessages = messages.filter((m) =>
      String(m.label || '').toUpperCase() !== 'DRAFT' && m.direction !== 'draft'
    )
    const targetMessage = nonDraftMessages[nonDraftMessages.length - 1] || email
    const nextMode = /^fwd\s*:/i.test(email.subject || '') ? 'forward' : 'reply'
    const nextBody = stripQuotedThread(email.raw_content || '')
    const nextTo = normalizeRecipients(email.recipient_list).join(', ') || email.recipient_list || ''
    const nextSubject = email.subject === '(tanpa subjek)' ? '' : email.subject || ''
    setReplyTargetMessage(targetMessage)
    setReplyMode(nextMode)
    setReplyTo(nextTo)
    setReplySubject(nextSubject)
    setReplyBody(nextBody)
    setReplyDraftId(email.email_id)
    replyDraftIdRef.current = email.email_id
    replyAutosaveSignatureRef.current = JSON.stringify({ mode: nextMode, target: targetMessage.email_id || email.email_id, to: nextTo, subject: nextSubject, body: nextBody, attachments: [] })
    setHydratedDraftId(email.email_id)
  }, [email, hydratedDraftId])

  // Hydrate from latest draft in thread
  useEffect(() => {
    if (!email || replyMode) return
    const messages = Array.isArray(email.thread_messages) ? email.thread_messages : []
    const latestDraft = [...messages].reverse().find((m) =>
      String(m.label || '').toUpperCase() === 'DRAFT' || m.direction === 'draft'
    )
    if (!latestDraft || hydratedDraftId === latestDraft.email_id) return
    const nonDraftMessages = messages.filter((m) =>
      String(m.label || '').toUpperCase() !== 'DRAFT' && m.direction !== 'draft'
    )
    const targetMessage = nonDraftMessages[nonDraftMessages.length - 1] || email
    const nextMode = /^fwd\s*:/i.test(latestDraft.subject || '') ? 'forward' : 'reply'
    const nextBody = stripQuotedThread(latestDraft.raw_content || '')
    const nextTo = normalizeRecipients(latestDraft.recipient_list).join(', ') || latestDraft.recipient_list || ''
    const nextSubject = latestDraft.subject === '(tanpa subjek)' ? '' : latestDraft.subject || ''
    setReplyTargetMessage(targetMessage)
    setReplyMode(nextMode)
    setReplyTo(nextTo)
    setReplySubject(nextSubject)
    setReplyBody(nextBody)
    setReplyDraftId(latestDraft.email_id)
    replyDraftIdRef.current = latestDraft.email_id
    replyAutosaveSignatureRef.current = JSON.stringify({ mode: nextMode, target: targetMessage.email_id || email.email_id, to: nextTo, subject: nextSubject, body: nextBody, attachments: [] })
    setHydratedDraftId(latestDraft.email_id)
  }, [email, hydratedDraftId, replyMode])

  // Auto-restore draft if navigated here from DraftPage (open_draft_id in URL)
  const openDraftIdParam = searchParams.get('open_draft_id') || ''
  useEffect(() => {
    if (!openDraftIdParam || !email || hydratedDraftId === openDraftIdParam) return
    api.get(`/emails/${openDraftIdParam}`).then(({ data: draftData }) => {
      if (!draftData) return
      const msgs = (Array.isArray(email.thread_messages) ? email.thread_messages : [email])
        .filter((m) => String(m.label || '').toUpperCase() !== 'DRAFT' && m.direction !== 'draft')
      const targetMessage = msgs[msgs.length - 1] || email
      const nextMode = /^fwd\s*:/i.test(draftData.subject || '') ? 'forward' : 'reply'
      const nextBody = stripQuotedThread(draftData.raw_content || '')
      const nextTo = normalizeRecipients(draftData.recipient_list).join(', ') || draftData.recipient_list || ''
      const nextSubject = draftData.subject === '(tanpa subjek)' ? '' : draftData.subject || ''
      setReplyTargetMessage(targetMessage)
      setReplyMode(nextMode)
      setReplyTo(nextTo)
      setReplySubject(nextSubject)
      setReplyBody(nextBody)
      setReplyDraftId(draftData.email_id)
      replyDraftIdRef.current = draftData.email_id
      replyAutosaveSignatureRef.current = JSON.stringify({ mode: nextMode, target: targetMessage.email_id || email.email_id, to: nextTo, subject: nextSubject, body: nextBody, attachments: [] })
      setHydratedDraftId(openDraftIdParam)
    }).catch(() => {})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openDraftIdParam, email, hydratedDraftId])

  // Auto-save reply draft
  useEffect(() => {
    if (!replyMode || !email) return undefined
    const signature = JSON.stringify({
      mode: replyMode,
      target: replyTargetMessage?.email_id || email.email_id,
      to: replyTo, subject: replySubject, body: replyBody,
      attachments: replyAttachments.map((file) => `${file.name}:${file.size}:${file.lastModified || ''}`),
    })
    if (signature === replyAutosaveSignatureRef.current) return undefined
    if (replyAutosaveTimerRef.current) clearTimeout(replyAutosaveTimerRef.current)
    replyAutosaveTimerRef.current = setTimeout(() => {
      persistReplyDraft({ silent: true, closeAfter: false, resetAfter: false, requireRecipient: false, signature })
    }, 1400)
    return () => { if (replyAutosaveTimerRef.current) clearTimeout(replyAutosaveTimerRef.current) }
  }, [replyMode, replyTargetMessage, replyTo, replySubject, replyBody, replyAttachments])

  if (isLoading) return (
    <GmailShell>
      <div style={{ padding: 32, color: 'var(--text-muted)', fontFamily: 'Google Sans' }}>Memuat detail email...</div>
    </GmailShell>
  )

  if (isError || !email) return (
    <GmailShell>
      <div style={{ padding: 32, color: '#EA4335', fontFamily: 'Google Sans' }}>Email tidak ditemukan.</div>
    </GmailShell>
  )

  const role = meData?.user?.role || 'user'
  const showSecurityPanel = true

  const label = (email.label || 'clean').toLowerCase()
  const backPath = fromPath || (label === 'sent' ? '/sent' : '/inbox')
  const makeDetailUrl = (targetEmailId) => {
    const params = new URLSearchParams({ from: backPath })
    if (activeMailboxId) params.set('mailbox_id', activeMailboxId)
    const query = params.toString()
    const path = activeMailboxId
      ? `/mail/${encodeURIComponent(activeMailboxId)}/email/${targetEmailId}`
      : `/email/${targetEmailId}`
    return query ? `${path}?${query}` : path
  }

  const folderBadgeText = label === 'sent'
    ? 'Terkirim'
    : email.status === 'trash'
      ? 'Sampah'
      : label === 'quarantine' || ['spam', 'phishing', 'malware'].includes((email.category || '').toLowerCase())
        ? 'Karantina'
        : 'Kotak Masuk'
  const cfg = BADGE_CFG[label] || BADGE_CFG.clean
  const shap = email.shap_data
  const maxShap = shap?.features?.length
    ? Math.max(...shap.features.map((f) => Math.abs(f.shap)))
    : 1

  const emailBodyHTML = renderEmailBody(email.raw_content, getMockBody(email.subject, email.sender))
  const threadMessages = Array.isArray(email.thread_messages) && email.thread_messages.length > 0
    ? email.thread_messages
    : [email]
  const hasThreadMessages = threadMessages.length > 1
  const visibleThreadMessages = threadMessages.filter((message) =>
    String(message.label || '').toUpperCase() !== 'DRAFT' && message.direction !== 'draft'
  )
  const isDraftDetail = String(email.label || '').toUpperCase() === 'DRAFT' || email.status === 'draft'
  const hasInlineReplyTarget = Boolean(
    replyMode
    && threadMessages.some((message) => message.email_id === replyTargetMessage?.email_id)
  )
  const threadRootMessage = threadMessages[0] || email
  const headerMessage = isDraftDetail && threadRootMessage ? threadRootMessage : email
  const displaySubject = hasThreadMessages
    ? (threadRootMessage.subject || email.subject)
    : email.subject
  const recipients = normalizeRecipients(email.recipient_list)
  const recipientText = recipients.length > 0
    ? recipients.join(', ')
    : meData?.user?.username || 'me'
  const receivedText = headerMessage.received_at
    ? formatAppDateTime(headerMessage.received_at, { dateStyle: 'full', timeStyle: 'medium' })
    : 'N/A'
  const originalMessage = [
    `Message-ID: <${email.email_id}@cognimail.local>`,
    `Date: ${receivedText}`,
    `From: ${email.sender || ''}`,
    `To: ${recipientText}`,
    `Subject: ${email.subject || ''}`,
    `SPF: ${email.spf_result || 'N/A'}`,
    `DKIM: ${email.dkim_result || 'N/A'}`,
    `DMARC: ${email.dmarc_result || 'N/A'}`,
    '',
    email.raw_content || '',
  ].join('\n')
  const mailboxIdentity = activeMailbox || recipients[0] || meData?.user?.email || meData?.user?.username || ''
  const mailboxInitial = (mailboxIdentity || 'U').trim()[0]?.toUpperCase() || 'U'

  // Dynamic Avatar color
  const avatarColors = ['#ea4335', '#1a73e8', '#f29900', '#34a853', '#ab47bc']
  const mailboxColorIndex = mailboxInitial.charCodeAt(0) % avatarColors.length
  const mailboxAvatarBg = avatarColors[mailboxColorIndex]
  const previewEmailId = previewAttachment?.email_id || email.email_id

  const renderAttachmentList = (message) => {
    const attachments = message.attachments || []
    if (attachments.length === 0) return null
    return (
      <div className={styles.attachments}>
        <div className={styles.attachmentsTitle}>
          <Paperclip size={16} />
          <span>{attachments.length} lampiran</span>
        </div>
        <div className={styles.attachmentGrid}>
          {attachments.map((attachment) => {
            const kind = attachmentKind(attachment)
            const url = attachmentUrl(message.email_id, attachment)
            const downloadUrl = attachmentUrl(message.email_id, attachment, true)
            return (
              <div
                key={`${message.email_id}-${attachment.index}`}
                className={`${styles.attachmentItem} ${!attachment.stored ? styles.attachmentDisabled : ''}`}
                title={attachment.stored ? 'Buka preview lampiran' : 'Lampiran terlalu besar untuk disimpan'}
              >
                {kind === 'image' && attachment.stored ? (
                  <img className={styles.attachmentThumb} src={url} alt="" />
                ) : (
                  <Paperclip size={18} />
                )}
                <button
                  type="button"
                  className={styles.attachmentInfo}
                  onClick={() => attachment.stored && setPreviewAttachment({ ...attachment, email_id: message.email_id })}
                  disabled={!attachment.stored}
                >
                  <span className={styles.attachmentName}>{attachment.filename}</span>
                  <span className={styles.attachmentMeta}>{formatBytes(attachment.size)}</span>
                </button>
                {attachment.stored && (
                  <a className={styles.attachmentDownload} href={downloadUrl} title="Download lampiran">
                    <Download size={16} />
                  </a>
                )}
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  const openThreadDraftCompose = async (draftMessage) => {
    try {
      const { data } = await api.get(`/emails/${draftMessage.email_id}`)
      const files = await Promise.all((data.attachments || []).map(async (attachment) => {
        if (!attachment?.stored) return null
        const response = await api.get(`/emails/${data.email_id}/attachments/${attachment.index}`, {
          responseType: 'blob',
        })
        return new File(
          [response.data],
          attachment.filename || `attachment-${attachment.index + 1}`,
          { type: attachment.content_type || response.data.type || 'application/octet-stream' }
        )
      }))
      window.dispatchEvent(new CustomEvent('open-compose', {
        detail: {
          draft_id: data.email_id,
          to: data.recipient_list || '',
          subject: data.subject === '(tanpa subjek)' ? '' : data.subject || '',
          body: stripQuotedThread(data.raw_content || ''),
          attachments: files.filter(Boolean),
        },
      }))
    } catch (err) {
      showToast(err.response?.data?.detail || 'Gagal membuka draf', 'error')
    }
  }

  const renderThreadMessage = (message, index) => {
    const detailId = message.email_id || `${message.subject}-${index}`
    const isSentMessage = String(message.label || '').toUpperCase() === 'SENT' || message.direction === 'sent'
    const isDraftMessage = String(message.label || '').toUpperCase() === 'DRAFT' || message.direction === 'draft'
    const isOwnMessage = isSentMessage || isDraftMessage
    const senderIdentity = parseEmailIdentity(message.sender || '')
    const senderName = isOwnMessage
      ? (senderIdentity.name || message.sender || mailboxIdentity || 'Saya')
      : (senderIdentity.name || 'Pengirim')
    const senderEmail = senderIdentity.email || ''
    const messageRecipients = normalizeRecipients(message.recipient_list).join(', ') || 'saya'
    const messageRecipientLine = isOwnMessage ? `kepada ${messageRecipients}` : 'kepada saya'
    const initial = (isOwnMessage ? mailboxInitial : senderName.trim()[0]?.toUpperCase()) || 'U'
    const bg = isOwnMessage ? mailboxAvatarBg : avatarColors[initial.charCodeAt(0) % avatarColors.length]
    const splitBody = isOwnMessage ? splitQuotedThread(message.raw_content) : null
    const bodySource = isOwnMessage ? splitBody.body : (message.raw_content || getMockBody(message.subject, message.sender))
    const bodyHTML = renderEmailBody(bodySource, '')
    const quoteHTML = splitBody?.quote ? renderEmailBody(splitBody.quote, '') : ''
    const quoteOpen = expandedQuoteIds.has(message.email_id)

    return (
      <div key={message.email_id || `${message.subject}-${index}`} className={styles.threadMessageGroup}>
        <div
          className={`${styles.threadMessage} ${isSentMessage ? styles.threadMessageSent : ''} ${isDraftMessage ? styles.threadMessageDraft : ''}`}
        >
          <div className={styles.threadAvatar} style={{ backgroundColor: bg }} title={senderName}>
            {initial}
          </div>
          <div className={styles.threadCard}>
            <div className={styles.threadHeader}>
              <div className={styles.threadSenderBlock}>
                <div>
                  <strong>{senderName}</strong>
                  {!isOwnMessage && senderEmail && (
                    <span className={styles.senderEmail}>
                      &lt;{senderEmail}&gt;
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  className={styles.threadToMe}
                  onClick={() => {
                    setThreadRecipientDetailId((current) => current === detailId ? null : detailId)
                  }}
                >
                  {messageRecipientLine} ▾
                </button>
                {isDraftMessage && <span className={styles.threadDraftBadge}>Draf</span>}
                {threadRecipientDetailId === detailId && (
                  <div className={styles.recipientDropdown}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-light)', paddingBottom: 8, marginBottom: 8 }}>
                      <strong style={{ fontSize: '0.875rem' }}>Detail Informasi Email</strong>
                      <button
                        style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)' }}
                        onClick={() => setThreadRecipientDetailId(null)}
                      >
                        <X size={16} />
                      </button>
                    </div>
                    <div className={styles.recipientRow}>
                      <span className={styles.recipientLabel}>Dari:</span>
                      <span className={styles.recipientValue}>{message.sender || '-'}</span>
                    </div>
                    <div className={styles.recipientRow}>
                      <span className={styles.recipientLabel}>Kepada:</span>
                      <span className={styles.recipientValue}>{messageRecipients}</span>
                    </div>
                    <div className={styles.recipientRow}>
                      <span className={styles.recipientLabel}>Tanggal:</span>
                      <span className={styles.recipientValue}>
                        {message.received_at ? formatAppDateTime(message.received_at, { dateStyle: 'full', timeStyle: 'medium' }) : 'N/A'}
                      </span>
                    </div>
                    <div className={styles.recipientRow}>
                      <span className={styles.recipientLabel}>Subjek:</span>
                      <span className={styles.recipientValue}>{message.subject || displaySubject}</span>
                    </div>
                    <div className={styles.recipientRow}>
                      <span className={styles.recipientLabel}>Kategori:</span>
                      <span className={styles.recipientValue}>{message.category || message.label || '-'}</span>
                    </div>
                  </div>
                )}
              </div>
              <div className={styles.threadHeaderActions}>
                <time>{message.received_at ? formatAppDateTime(message.received_at, { dateStyle: 'medium', timeStyle: 'short' }) : 'N/A'}</time>
                {isDraftMessage && (
                  <button className={styles.threadTextBtn} onClick={() => openThreadDraftCompose(message)}>
                    Edit draf
                  </button>
                )}
                <button className={styles.threadIconBtn} onClick={handleToggleStar} title="Bintangi">
                  <Star size={16} fill={isStarred ? '#f29900' : 'none'} />
                </button>
                <button className={styles.threadIconBtn} onClick={() => handleOpenReply('reply', message)} title="Balas">
                  <Reply size={16} />
                </button>
                <button className={styles.threadIconBtn} onClick={() => handleOpenReply('forward', message)} title="Teruskan">
                  <CornerUpRight size={16} />
                </button>
                <button className={styles.threadIconBtn} onClick={(event) => handleMoreActions(event, `thread-${message.email_id}`)} title="Lainnya">
                  <MoreVertical size={16} />
                </button>
                {messageMenuAnchor === `thread-${message.email_id}` && (
                  renderMessageMenu('thread', message)
                )}
              </div>
            </div>
            <div className={styles.threadBody} dangerouslySetInnerHTML={{ __html: bodyHTML }} />
            {quoteHTML && (
              <div className={styles.quotedToggleWrap}>
                <button
                  type="button"
                  className={styles.quotedToggle}
                  onClick={() => setExpandedQuoteIds((prev) => {
                    const next = new Set(prev)
                    if (next.has(message.email_id)) next.delete(message.email_id)
                    else next.add(message.email_id)
                    return next
                  })}
                  title={quoteOpen ? 'Sembunyikan pesan sebelumnya' : 'Tampilkan pesan sebelumnya'}
                >
                  ...
                </button>
                {quoteOpen && (
                  <div className={styles.quotedContent} dangerouslySetInnerHTML={{ __html: quoteHTML }} />
                )}
              </div>
            )}
            {renderAttachmentList(message)}
          </div>
        </div>
        {replyMode && replyTargetMessage?.email_id === message.email_id && renderReplyBox(styles.gmailReplyRowInline)}
      </div>
    )
  }
  // Pagination logic
  const emailList = (emailsData?.emails || []).filter((row) => {
    if (!activeMailbox) return false
    const target = activeMailbox.toLowerCase()
    if (listFilter === 'sent') {
      return String(row.sender || row.sender_email || '').toLowerCase() === target
    }
    return String(row.recipient_list || '').toLowerCase().includes(target)
      || String(row.sender || row.sender_email || '').toLowerCase() === target
  })
  const currentIndex = emailList.findIndex((e) => e.email_id === emailId)
  const prevEmail = currentIndex > 0 ? emailList[currentIndex - 1] : null
  const nextEmail = currentIndex >= 0 && currentIndex < emailList.length - 1 ? emailList[currentIndex + 1] : null
  const pagerText = currentIndex !== -1
    ? `${currentIndex + 1} dari ${emailList.length}`
    : '1 dari 1'

  // Star logic
  const isStarred = localStarred !== null ? localStarred : (email.is_starred || false)

  const handleToggleStar = () => {
    const nextVal = !isStarred
    setLocalStarred(nextVal)
    showToast(nextVal ? 'Ditambahkan ke berbintang' : 'Dihapus dari berbintang', 'info')
  }

  // Toolbar handlers
  const handleArchive = () => {
    if (role !== 'superadmin' && role !== 'admin') {
      showToast('Aksi ditolak: Hanya Admin yang dapat mengelola karantina', 'error')
      return
    }
    release(emailId, {
      onSuccess: () => {
        showToast('Email dilepaskan ke inbox', 'success')
        navigate(backPath)
      },
      onError: () => showToast('Gagal melepaskan email', 'error'),
    })
  }

  const handleSpam = () => {
    if (role !== 'superadmin' && role !== 'admin') {
      showToast('Aksi ditolak: Hanya Admin yang dapat mengelola karantina', 'error')
      return
    }
    confirmSpam(emailId, {
      onSuccess: () => {
        showToast('Email dipindahkan ke kategori Spam', 'info')
        navigate(backPath)
      },
      onError: () => showToast('Gagal mengkonfirmasi spam', 'error'),
    })
  }

  const handleDelete = () => {
    setDeleteDialogOpen(true)
  }

  const confirmDelete = () => {
    const alreadyTrash = email.status === 'trash'
    deleteEmail(emailId, {
      onSuccess: () => {
        if (alreadyTrash) showToast('Email berhasil dihapus permanen', 'success')
        setDeleteDialogOpen(false)
        navigate(backPath)
      },
      onError: (err) => showToast(err.response?.data?.detail || 'Gagal menghapus email', 'error'),
    })
  }

  const handleToggleUnread = () => {
    const nextVal = !isUnread
    setIsUnread(nextVal)
    try {
      const readIds = new Set(JSON.parse(localStorage.getItem('cognimail.read') || '[]'))
      if (nextVal) {
        readIds.delete(emailId)
      } else {
        readIds.add(emailId)
      }
      localStorage.setItem('cognimail.read', JSON.stringify(Array.from(readIds)))
    } catch {
      // Ignore localStorage failures; the visual state still updates for this view.
    }
    showToast(nextVal ? 'Ditandai sebagai belum dibaca' : 'Ditandai sebagai sudah dibaca', 'info')
  }

  const handleSnooze = () => {
    showToast('Fitur Tunda disimulasikan', 'info')
  }

  const handleMoveTo = () => {
    showToast('Fitur Pindahkan folder disimulasikan', 'info')
  }

  const handleAddLabel = () => {
    showToast('Fitur Label disimulasikan', 'info')
  }

  const closeMessageMenu = () => setMessageMenuAnchor(null)

  const handleMoreActions = (e, anchor = 'message') => {
    e?.stopPropagation()
    setMessageMenuAnchor((openAnchor) => openAnchor === anchor ? null : anchor)
  }

  const handlePrint = () => {
    const printWindow = window.open('', '_blank', 'width=1120,height=820')
    if (!printWindow) {
      window.print()
      return
    }
    printWindow.document.write(`
      <!doctype html>
      <html>
        <head>
          <title>${escapeHtml(email.subject || 'Cetak email')}</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 0; color: #202124; background: #fff; }
            .page { max-width: 940px; margin: 32px auto; padding: 0 28px; }
            .brand { display: flex; justify-content: space-between; align-items: center; color: #5f6368; margin-bottom: 24px; }
            .brand strong { font-size: 24px; color: #202124; }
            h1 { font-size: 24px; margin: 0 0 14px; border-top: 1px solid #9aa0a6; border-bottom: 1px solid #9aa0a6; padding: 12px 0; }
            .meta { display: flex; justify-content: space-between; gap: 24px; border-bottom: 1px solid #dadce0; padding-bottom: 14px; margin-bottom: 24px; }
            .sender { font-weight: 700; }
            .body { line-height: 1.55; }
            @media print { .page { margin: 18px auto; } }
          </style>
        </head>
        <body>
          <main class="page">
            <div class="brand"><strong>CogniMail</strong><span>${escapeHtml(recipientText)}</span></div>
            <h1>${escapeHtml(email.subject || '(tanpa subjek)')}</h1>
            <div class="meta">
              <div><div class="sender">${escapeHtml(email.sender || 'Pengirim')}</div><div>Kepada: ${escapeHtml(recipientText)}</div></div>
              <div>${escapeHtml(receivedText)}</div>
            </div>
            <div class="body">${emailBodyHTML}</div>
          </main>
          <script>window.onload = () => { window.print(); };</script>
        </body>
      </html>
    `)
    printWindow.document.close()
  }

  const handleOpenNewWindow = () => {
    const params = new URLSearchParams({ from: backPath, original: '1' })
    if (activeMailboxId) params.set('mailbox_id', activeMailboxId)
    const path = activeMailboxId
      ? `/mail/${encodeURIComponent(activeMailboxId)}/email/${emailId}`
      : `/email/${emailId}`
    window.open(`${path}?${params.toString()}`, '_blank', 'width=1180,height=860')
  }

  const handleDownloadMessage = () => {
    const blob = new Blob([originalMessage], { type: 'message/rfc822;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = safeFilename(email.subject)
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleCopyOriginal = async () => {
    try {
      await navigator.clipboard.writeText(originalMessage)
      showToast('Pesan asli disalin ke papan klip', 'success')
    } catch {
      showToast('Gagal menyalin pesan asli', 'error')
    }
  }

  // Reply / Forward Handlers
  const handleOpenReply = (mode, sourceMessage = email) => {
    const source = sourceMessage || email
    const isSourceSent = String(source.label || '').toUpperCase() === 'SENT' || source.direction === 'sent'
    const sourceRecipients = normalizeRecipients(source.recipient_list)
    const sourceRecipientText = sourceRecipients.join(', ')
    closeMessageMenu()
    setReplyActionMenuOpen(false)
    setReplyLinkOpen(false)
    setReplyAttachments([])
    
    // Check if there is an existing draft for this thread & mode
    const existingDraft = findExistingDraft(allDraftsData?.emails || [], {
      mailboxId: activeMailbox,
      threadId: source.thread_id || '',
      parentEmailId: source.email_id || '',
      subject: source.subject || '',
      composeMode: mode
    })

    if (existingDraft) {
      setReplyDraftId(existingDraft.email_id)
      replyDraftIdRef.current = existingDraft.email_id
      setReplyQuoteExpanded(false)
      replyAutosaveSignatureRef.current = ''
      setReplyTargetMessage(source)
      setReplyMode(mode)
      setReplyTo(existingDraft.recipient_list || '')
      setReplySubject(existingDraft.subject || '')
      setReplyBody(existingDraft.raw_content || existingDraft.body_text || '')
      return
    }

    setReplyDraftId('')
    setReplyQuoteExpanded(false)
    replyDraftIdRef.current = ''
    replyAutosaveSignatureRef.current = ''
    setReplyTargetMessage(source)
    setReplyMode(mode)
    if (mode === 'reply') {
      setReplyTo(isSourceSent ? sourceRecipientText : source.sender || '')
      setReplySubject(`Re: ${source.subject || email.subject || ''}`)
      setReplyBody('')
    } else if (mode === 'forward') {
      setReplyTo('')
      setReplySubject(`Fwd: ${source.subject || email.subject || ''}`)
      setReplyBody('')
    }
  }

  const handleApplyReplyLink = () => {
    if (!replyLinkUrl.trim()) return
    const text = replyLinkText.trim() || replyLinkUrl.trim()
    const url = replyLinkUrl.trim()
    const linkText = `${text} (${url})`
    setReplyBody((body) => body ? `${body}\n${linkText}` : linkText)
    setReplyLinkText('')
    setReplyLinkUrl('')
    setReplyLinkOpen(false)
  }

  const parseReplyRecipients = () => {
    const raw = String(replyTo || '')
    const extractedEmails = raw.match(/[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}/gi)
    if (extractedEmails?.length) return extractedEmails.map((item) => item.toLowerCase())
    return raw
      .split(/[,\s;]+/)
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean)
  }

  const validateReplyRecipients = () => {
    const values = parseReplyRecipients()
    if (values.length === 0) return { ok: false, message: 'Silakan tentukan penerima email' }
    const invalid = values.find((value) => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value))
    if (invalid) return { ok: false, message: `Alamat email tidak valid: ${invalid}` }
    return { ok: true, recipients: Array.from(new Set(values)) }
  }

  const quotedOriginalMessage = () => replyTargetMessage || email
  const quotedOriginalMetaLines = () => {
    const source = quotedOriginalMessage()
    return [
      replyMode === 'forward' ? '---------- Forwarded message ---------' : '---------- Original message ---------',
      `Dari: ${source.sender || '-'}`,
      `Tanggal: ${source.received_at ? formatAppDateTime(source.received_at, { dateStyle: 'medium', timeStyle: 'short' }) : '-'}`,
      `Subjek: ${source.subject || '(tanpa subjek)'}`,
      `Kepada: ${normalizeRecipients(source.recipient_list).join(', ') || recipientText || 'saya'}`,
    ]
  }
  const quotedOriginalText = () => {
    const source = quotedOriginalMessage()
    const originalText = plainFromHtmlish(stripRawHeaders(source.raw_content))
      .replace(/\s+/g, ' ')
      .trim()
    return ['', '', ...quotedOriginalMetaLines(), '', originalText].join('\n')
  }
  const quotedOriginalHTML = () => {
    const source = quotedOriginalMessage()
    const metaHtml = quotedOriginalMetaLines()
      .map((line) => escapeHtml(line))
      .join('<br />')
    return `
      <div class="${styles.quotedMeta}">${metaHtml}</div>
      <div class="${styles.quotedRenderedBody}">
        ${renderEmailBody(source.raw_content || '', '')}
      </div>
    `
  }
  const replyQuoteHTML = replyMode
    ? quotedOriginalHTML()
    : ''

  const buildReplyDraftBody = () => {
    return replyBody || ''
  }

  const persistReplyDraft = async ({
    silent = false,
    closeAfter = true,
    resetAfter = true,
    requireRecipient = true,
    signature = null,
  } = {}) => {
    if (savingReplyDraft) return
    const validation = requireRecipient ? validateReplyRecipients() : { ok: true, recipients: parseReplyRecipients() }
    if (!validation.ok) {
      showToast(validation.message, 'error')
      return
    }
    setSavingReplyDraft(true)
    try {
      const finalRecipients = Array.from(new Set(validation.recipients || [])).join(', ')
      const finalBody = buildReplyDraftBody()
      // Thread context: parent_email_id ties this draft to the thread it replies to
      const parentEmailIdForDraft = replyTargetMessage?.email_id || email.email_id
      const composeModeForDraft = replyMode || 'reply'
      let response
      if (replyAttachments.length > 0) {
        const formData = new FormData()
        formData.append('draft_id', replyDraftIdRef.current || replyDraftId)
        formData.append('to', finalRecipients)
        formData.append('from_email', activeMailbox || recipients[0] || email.sender || '')
        formData.append('subject', replySubject)
        formData.append('body', finalBody)
        formData.append('parent_email_id', parentEmailIdForDraft)
        formData.append('compose_mode', composeModeForDraft)
        replyAttachments.forEach((file) => formData.append('attachments', file))
        response = await api.post('/emails/draft', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      } else {
        response = await api.post('/emails/draft', {
          draft_id: replyDraftIdRef.current || replyDraftId,
          to: finalRecipients,
          from_email: activeMailbox || recipients[0] || email.sender || '',
          subject: replySubject,
          body: finalBody,
          parent_email_id: parentEmailIdForDraft,
          compose_mode: composeModeForDraft,
        })
      }
      const nextDraftId = response?.data?.email_id
      if (nextDraftId) {
        replyDraftIdRef.current = nextDraftId
        setReplyDraftId(nextDraftId)
      }
      replyAutosaveSignatureRef.current = signature || JSON.stringify({
        mode: replyMode,
        to: replyTo,
        subject: replySubject,
        body: replyBody,
        attachments: replyAttachments.map((file) => `${file.name}:${file.size}:${file.lastModified || ''}`),
      })
      if (!silent) showToast('Draf balasan berhasil disimpan', 'success')
      queryClient.invalidateQueries({ queryKey: ['emails'] })
      if (resetAfter) {
        setReplyAttachments([])
        setReplyDraftId('')
        setReplyTargetMessage(null)
        replyDraftIdRef.current = ''
        replyAutosaveSignatureRef.current = ''
      }
      if (closeAfter) {
        setReplyMode(null)
        setReplyTargetMessage(null)
      }
    } catch (err) {
      if (!silent) showToast('Gagal menyimpan draf: ' + (err.response?.data?.detail || err.message), 'error')
    } finally {
      setSavingReplyDraft(false)
    }
  }

  const handleSaveReplyDraft = async () => {
    await persistReplyDraft({ silent: false, closeAfter: true, resetAfter: true, requireRecipient: false })
  }

  const clearReplyComposeState = () => {
    setReplyAttachments([])
    setReplyBody('')
    setReplyTo('')
    setReplySubject('')
    setReplyMode(null)
    setReplyTargetMessage(null)
    setReplyDraftId('')
    setReplyQuoteExpanded(false)
    setReplyActionMenuOpen(false)
    setReplyLinkOpen(false)
    setReplyLinkText('')
    setReplyLinkUrl('')
    replyDraftIdRef.current = ''
    replyAutosaveSignatureRef.current = ''
  }

  const handleDiscardReplyDraft = async () => {
    if (replyAutosaveTimerRef.current) clearTimeout(replyAutosaveTimerRef.current)
    const draftId = replyDraftIdRef.current || replyDraftId
    const targetId = replyTargetMessage?.email_id || threadRootMessage?.email_id
    try {
      if (draftId) {
        await api.delete(`/emails/${draftId}`)
      }
      clearReplyComposeState()
      queryClient.invalidateQueries({ queryKey: ['emails'] })
      queryClient.invalidateQueries({ queryKey: ['email', email.email_id] })
      if (targetId && isDraftDetail && targetId !== email.email_id) {
        navigate(makeDetailUrl(targetId), { replace: true })
      }
      showToast('Draf dibuang', 'info')
    } catch (err) {
      showToast(err.response?.data?.detail || 'Gagal membuang draf', 'error')
    }
  }

  const closeReplyBox = () => {
    if (replyAutosaveTimerRef.current) clearTimeout(replyAutosaveTimerRef.current)
    if (replyMode) {
      persistReplyDraft({ silent: true, closeAfter: false, resetAfter: false, requireRecipient: false })
    }
    setReplyMode(null)
    setReplyTargetMessage(null)
  }

  const handleSendReply = async () => {
    const validation = validateReplyRecipients()
    if (!validation.ok) {
      showToast(validation.message, 'error')
      return
    }
    try {
      const finalRecipients = validation.recipients.join(', ')
      const finalBody = buildReplyDraftBody()
      let response
      if (replyAttachments.length > 0) {
        const formData = new FormData()
        formData.append('to', finalRecipients)
        formData.append('from_email', activeMailbox || recipients[0] || email.sender || '')
        formData.append('subject', replySubject)
        formData.append('body', finalBody)
        formData.append('reply_to_id', (replyTargetMessage || email).email_id)
        formData.append('draft_id', replyDraftIdRef.current || replyDraftId)
        formData.append('action', replyMode)
        replyAttachments.forEach((file) => formData.append('attachments', file))
        response = await api.post('/emails/send', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      } else {
        response = await api.post('/emails/send', {
          to: finalRecipients,
          from_email: activeMailbox || recipients[0] || email.sender || '',
          subject: replySubject,
          body: finalBody,
          reply_to_id: (replyTargetMessage || email).email_id,
          draft_id: replyDraftIdRef.current || replyDraftId,
          action: replyMode,
        })
      }
      showToast(
        replyMode === 'reply'
          ? 'Balasan berhasil dikirim'
          : 'Email berhasil diteruskan',
        'success'
      )
      setInlineSentReplies((prev) => hasThreadMessages ? prev : [
        ...prev,
        {
          id: response?.data?.email_id || `inline-${Date.now()}`,
          sender: activeMailbox || recipients[0] || mailboxIdentity || 'Saya',
          recipient: finalRecipients,
          subject: replySubject,
          body: finalBody,
          sentAt: new Date().toISOString(),
          attachments: replyAttachments.map((file) => ({ name: file.name, size: file.size })),
        },
      ])
      queryClient.invalidateQueries({ queryKey: ['email', email.email_id] })
      queryClient.invalidateQueries({ queryKey: ['emails'] })
      setReplyAttachments([])
      setReplyDraftId('')
      replyDraftIdRef.current = ''
      replyAutosaveSignatureRef.current = ''
      setReplyMode(null)
      setReplyTargetMessage(null)
    } catch (err) {
      const detail = err.response?.data?.detail
      const message = typeof detail === 'object'
        ? `${detail.message || 'Email gagal terkirim.'}${detail.reason ? ` ${detail.reason}` : ''}`
        : detail || err.message
      showToast('Gagal mengirim: ' + message, 'error')
    }
  }

  const renderMessageMenu = (placement = 'message', sourceMessage = email) => (
    <div className={`${styles.messageMenu} ${placement === 'toolbar' ? styles.messageMenuToolbar : ''}`}>
      <button onClick={() => handleOpenReply('reply', sourceMessage)}><Reply size={16} />Balas</button>
      <button onClick={() => handleOpenReply('forward', sourceMessage)}><CornerUpRight size={16} />Teruskan</button>
      <div className={styles.menuDivider} />
      <button onClick={() => { closeMessageMenu(); handleDelete() }}><Trash2 size={16} />Hapus</button>
      <button onClick={() => { closeMessageMenu(); handleToggleUnread() }}><Mail size={16} />Tandai belum dibaca</button>
      <div className={styles.menuDivider} />
      <button onClick={() => { closeMessageMenu(); showToast(`Pengirim ${sourceMessage?.sender || email.sender || 'ini'} diblokir`, 'info') }}><Ban size={16} />Blokir pengirim</button>
      <button onClick={() => { closeMessageMenu(); handleSpam() }}><ShieldAlert size={16} />Laporkan spam</button>
      <button onClick={() => { closeMessageMenu(); showToast('Dilaporkan sebagai phishing', 'warning') }}><ShieldAlert size={16} />Laporkan phishing</button>
      <button onClick={() => { closeMessageMenu(); handlePrint() }}><Printer size={16} />Print</button>
      <button onClick={() => { closeMessageMenu(); handleDownloadMessage() }}><Download size={16} />Download pesan</button>
      <button onClick={() => { closeMessageMenu(); handleOpenNewWindow() }}><Code2 size={16} />Tampilkan versi asli</button>
    </div>
  )

  const renderReplyBox = (rowClassName = styles.gmailReplyRow) => (
    <div className={rowClassName}>
      <div className={styles.replyAvatar} style={{ backgroundColor: mailboxAvatarBg }} title={mailboxIdentity || 'Mailbox'}>
        {mailboxInitial}
      </div>
      <div className={styles.replyBox}>
        <div className={styles.replyTopLine}>
          <div className={styles.replyActionWrap}>
            <button
              className={styles.replyActionBtn}
              onClick={() => setReplyActionMenuOpen((open) => !open)}
              title="Pilih aksi"
            >
              {replyMode === 'reply' ? <Reply size={16} /> : <CornerUpRight size={16} />}
              <ChevronDown size={14} />
            </button>
            {replyActionMenuOpen && (
              <div className={styles.replyActionMenu}>
                <button onClick={() => handleOpenReply('reply', replyTargetMessage || email)}><Reply size={16} />Balas</button>
                <button onClick={() => handleOpenReply('forward', replyTargetMessage || email)}><CornerUpRight size={16} />Teruskan</button>
                <div className={styles.menuDivider} />
                <button onClick={() => showToast('Subjek sudah bisa diedit di kolom subjek', 'info')}>Edit subjek</button>
                <button onClick={() => { closeReplyBox(); setReplyActionMenuOpen(false) }}>Lepaskan balasan</button>
              </div>
            )}
          </div>
          <input
            type="text"
            className={styles.replyToInput}
            value={replyTo}
            onChange={(e) => setReplyTo(e.target.value)}
            placeholder="Kepada"
          />
          <button className={styles.replyIconBtn} onClick={closeReplyBox} title="Tutup">
            <X size={16} />
          </button>
        </div>
        <input
          type="text"
          className={styles.replySubjectInput}
          value={replySubject}
          onChange={(e) => setReplySubject(e.target.value)}
          placeholder="Subjek"
        />
        <textarea
          className={styles.replyTextarea}
          value={replyBody}
          onChange={(e) => setReplyBody(e.target.value)}
          placeholder={replyMode === 'reply' ? '' : 'Tulis pesan pengantar di sini'}
        />
        {replyQuoteHTML && (
          <div className={styles.replyQuotedArea}>
            <button
              type="button"
              className={styles.quotedToggle}
              onClick={() => setReplyQuoteExpanded((open) => !open)}
              title={replyQuoteExpanded ? 'Sembunyikan pesan sebelumnya' : 'Tampilkan pesan sebelumnya'}
            >
              ...
            </button>
            {replyQuoteExpanded && (
              <div className={styles.quotedContent} dangerouslySetInnerHTML={{ __html: replyQuoteHTML }} />
            )}
          </div>
        )}
        {replyAttachments.length > 0 && (
          <div className={styles.replyAttachmentList}>
            {replyAttachments.map((file, index) => (
              <div key={`${file.name}-${index}`} className={styles.replyAttachmentChip}>
                <Paperclip size={14} />
                <span>{file.name}</span>
                <button
                  type="button"
                  onClick={() => setReplyAttachments((prev) => prev.filter((_, i) => i !== index))}
                  title="Hapus lampiran"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className={styles.replyBoxFooter}>
          <button className={styles.btnReplySend} onClick={handleSendReply}>
            Kirim
          </button>
          <label className={styles.replyToolBtn} title="Lampirkan file">
            <Paperclip size={17} />
            <input
              type="file"
              multiple
              onChange={(e) => {
                setReplyAttachments((prev) => [...prev, ...Array.from(e.target.files || [])])
                e.target.value = ''
              }}
            />
          </label>
          <div className={styles.replyLinkWrap}>
            <button
              className={`${styles.replyToolBtn} ${replyLinkOpen ? styles.replyToolBtnActive : ''}`}
              title="Sisipkan link"
              onClick={() => setReplyLinkOpen((open) => !open)}
            >
              <Link size={17} />
            </button>
            {replyLinkOpen && (
              <div className={styles.replyLinkPopover}>
                <div className={styles.replyLinkField}>
                  <span className={styles.replyLinkIcon}>≡</span>
                  <input
                    value={replyLinkText}
                    onChange={(e) => setReplyLinkText(e.target.value)}
                    placeholder="Teks"
                    autoFocus
                  />
                </div>
                <div className={styles.replyLinkField}>
                  <Link size={16} />
                  <input
                    value={replyLinkUrl}
                    onChange={(e) => setReplyLinkUrl(e.target.value)}
                    placeholder="Ketik atau tempelkan link"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleApplyReplyLink()
                      if (e.key === 'Escape') setReplyLinkOpen(false)
                    }}
                  />
                  <button
                    className={styles.replyLinkApply}
                    onClick={handleApplyReplyLink}
                    disabled={!replyLinkUrl.trim()}
                  >
                    Terapkan
                  </button>
                </div>
              </div>
            )}
          </div>
          <label className={styles.replyToolBtn} title="Sisipkan gambar">
            <Image size={17} />
            <input
              type="file"
              multiple
              accept="image/*"
              onChange={(e) => {
                setReplyAttachments((prev) => [...prev, ...Array.from(e.target.files || [])])
                e.target.value = ''
              }}
            />
          </label>
          <button className={`${styles.replyToolBtn} ${styles.replyTrashBtn}`} onClick={handleDiscardReplyDraft} title="Buang draft">
            <Trash2 size={17} />
          </button>
        </div>
      </div>
    </div>
  )

  const togglePanel = (panel) => {
    setOpenPanels((prev) => ({ ...prev, [panel]: !prev[panel] }))
  }

  if (originalView) {
    return (
      <div className={styles.originalPage}>
        <header className={styles.originalHeader}>
          <div>
            <h1>Pesan Asli</h1>
            <p>{email.subject || '(tanpa subjek)'}</p>
          </div>
          <div className={styles.originalActions}>
            <button onClick={handleDownloadMessage}>Download Pesan Asli</button>
            <button onClick={handleCopyOriginal}>Salin ke papan klip</button>
          </div>
        </header>

        <section className={styles.originalMeta}>
          <div><span>ID Pesan</span><strong>&lt;{email.email_id}@cognimail.local&gt;</strong></div>
          <div><span>Dibuat pada</span><strong>{receivedText}</strong></div>
          <div><span>Dari</span><strong>{email.sender || '-'}</strong></div>
          <div><span>Kepada</span><strong>{recipientText}</strong></div>
          <div><span>Subjek</span><strong>{email.subject || '(tanpa subjek)'}</strong></div>
          <div><span>SPF</span><strong>{email.spf_result || 'N/A'}</strong></div>
          <div><span>DKIM</span><strong>{email.dkim_result || 'N/A'}</strong></div>
          <div><span>DMARC</span><strong>{email.dmarc_result || 'N/A'}</strong></div>
        </section>

        <pre className={styles.originalRaw}>{originalMessage}</pre>
      </div>
    )
  }

  return (
    <GmailShell>
      <div className={styles.splitLayout}>
        {/* Left Pane: Email Reader */}
        <div className={styles.emailPane}>
          {/* Gmail Toolbar */}
          <div className={styles.toolbar}>
            <div className={styles.toolbarLeft}>
              <button className={styles.toolbarBtn} onClick={() => navigate(backPath)} title="Kembali">
                <ArrowLeft size={18} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleSpam} title="Laporkan Spam">
                <ShieldAlert size={18} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleDelete} title="Hapus">
                <Trash2 size={18} />
              </button>
              <button
                className={`${styles.toolbarBtn} ${isUnread ? styles.unreadActive : ''}`}
                onClick={handleToggleUnread}
                title="Tandai Belum Dibaca"
              >
                <Mail size={18} />
              </button>
              <div className={styles.moreMenuWrap}>
                <button className={styles.toolbarBtn} onClick={(e) => handleMoreActions(e, 'toolbar')} title="Lainnya">
                  <MoreVertical size={18} />
                </button>
                {messageMenuAnchor === 'toolbar' && renderMessageMenu('toolbar')}
              </div>
            </div>
            <div className={styles.toolbarRight}>
              <span className={styles.pagerText}>{pagerText}</span>
              <button
                className={styles.toolbarBtn}
                disabled={!prevEmail}
                onClick={() => prevEmail && navigate(makeDetailUrl(prevEmail.email_id))}
                title="Lebih baru"
              >
                <ChevronLeft size={18} />
              </button>
              <button
                className={styles.toolbarBtn}
                disabled={!nextEmail}
                onClick={() => nextEmail && navigate(makeDetailUrl(nextEmail.email_id))}
                title="Lebih lama"
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>

          {/* Subject Header */}
          <div className={styles.subjectRow}>
            <h1 className={styles.subjectTitle}>
              {displaySubject || '(tanpa subjek)'}
              <span className={styles.badgeInbox}>{folderBadgeText} x</span>
            </h1>
            <div className={styles.subjectActions}>
              <button className={styles.toolbarBtn} onClick={handlePrint} title="Cetak semua">
                <Printer size={18} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleOpenNewWindow} title="Buka di jendela baru">
                <ExternalLink size={18} />
              </button>
            </div>
          </div>


          {/* Email Content Frame */}
          <div className={styles.emailBodyWrapper}>
            {visibleThreadMessages.length > 0 ? (
              <div className={styles.threadStack}>
                {visibleThreadMessages.map(renderThreadMessage)}
              </div>
            ) : (
              <>
                <div className={styles.emailBodyCard} dangerouslySetInnerHTML={{ __html: emailBodyHTML }} />
                {renderAttachmentList(email)}
              </>
            )}
            {previewAttachment && (
              <div className={styles.previewOverlay} onClick={() => setPreviewAttachment(null)}>
                <div className={styles.previewModal} onClick={(event) => event.stopPropagation()}>
                  <div className={styles.previewHeader}>
                    <div className={styles.previewTitle}>
                      <Paperclip size={18} />
                      <span>{previewAttachment.filename}</span>
                    </div>
                    <div className={styles.previewActions}>
                      <a href={attachmentUrl(previewEmailId, previewAttachment, true)} title="Download lampiran">
                        <Download size={18} />
                      </a>
                      <button type="button" onClick={() => setPreviewAttachment(null)} title="Tutup preview">
                        <X size={18} />
                      </button>
                    </div>
                  </div>
                  <div className={styles.previewBody} onClick={() => setPreviewAttachment(null)}>
                    {attachmentKind(previewAttachment) === 'image' && (
                      <img
                        src={attachmentUrl(previewEmailId, previewAttachment)}
                        alt={previewAttachment.filename}
                        onClick={(event) => event.stopPropagation()}
                      />
                    )}
                    {attachmentKind(previewAttachment) === 'pdf' && (
                      <iframe
                        title={previewAttachment.filename}
                        src={attachmentUrl(previewEmailId, previewAttachment)}
                        onClick={(event) => event.stopPropagation()}
                      />
                    )}
                    {attachmentKind(previewAttachment) === 'text' && (
                      <iframe
                        title={previewAttachment.filename}
                        src={attachmentUrl(previewEmailId, previewAttachment)}
                        onClick={(event) => event.stopPropagation()}
                      />
                    )}
                    {attachmentKind(previewAttachment) === 'file' && (
                      <div className={styles.previewFallback} onClick={(event) => event.stopPropagation()}>
                        <Paperclip size={32} />
                        <p>File ini tidak bisa dipreview langsung.</p>
                        <a href={attachmentUrl(previewEmailId, previewAttachment, true)}>Download file</a>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {!hasThreadMessages && inlineSentReplies.map((reply) => (
            <div key={reply.id} className={styles.sentReplyRow}>
              <div className={styles.replyAvatar} style={{ backgroundColor: mailboxAvatarBg }} title={reply.sender}>
                {mailboxInitial}
              </div>
              <div className={styles.sentReplyCard}>
                <div className={styles.sentReplyHeader}>
                  <div>
                    <strong>{reply.sender}</strong>
                    <span> kepada {reply.recipient}</span>
                  </div>
                  <time>{formatAppDateTime(reply.sentAt, { dateStyle: 'medium', timeStyle: 'short' })}</time>
                </div>
                <div className={styles.sentReplyBody}>
                  {reply.body ? reply.body.split('\n').map((line, index) => (
                    <p key={`${reply.id}-${index}`}>{line || '\u00a0'}</p>
                  )) : <p>&nbsp;</p>}
                </div>
                {reply.attachments.length > 0 && (
                  <div className={styles.sentReplyAttachments}>
                    <Paperclip size={15} />
                    <span>{reply.attachments.length} lampiran</span>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Reply / Forward Box Form */}
          {replyMode && !hasInlineReplyTarget && (
            <div className={styles.gmailReplyRow}>
              <div className={styles.replyAvatar} style={{ backgroundColor: mailboxAvatarBg }} title={mailboxIdentity || 'Mailbox'}>
                {mailboxInitial}
              </div>
              <div className={styles.replyBox}>
                <div className={styles.replyTopLine}>
                  <div className={styles.replyActionWrap}>
                    <button
                      className={styles.replyActionBtn}
                      onClick={() => setReplyActionMenuOpen((open) => !open)}
                      title="Pilih aksi"
                    >
                      {replyMode === 'reply' ? <Reply size={16} /> : <CornerUpRight size={16} />}
                      <ChevronDown size={14} />
                    </button>
                    {replyActionMenuOpen && (
                      <div className={styles.replyActionMenu}>
                        <button onClick={() => handleOpenReply('reply', replyTargetMessage || email)}><Reply size={16} />Balas</button>
                        <button onClick={() => handleOpenReply('forward', replyTargetMessage || email)}><CornerUpRight size={16} />Teruskan</button>
                        <div className={styles.menuDivider} />
                        <button onClick={() => showToast('Subjek sudah bisa diedit di kolom subjek', 'info')}>Edit subjek</button>
                        <button onClick={() => { closeReplyBox(); setReplyActionMenuOpen(false) }}>Lepaskan balasan</button>
                      </div>
                    )}
                  </div>
                  <input
                    type="text"
                    className={styles.replyToInput}
                    value={replyTo}
                    onChange={(e) => setReplyTo(e.target.value)}
                    placeholder="Kepada"
                  />
                  <button className={styles.replyIconBtn} onClick={closeReplyBox} title="Tutup">
                    <X size={16} />
                  </button>
                </div>
                <input
                  type="text"
                  className={styles.replySubjectInput}
                  value={replySubject}
                  onChange={(e) => setReplySubject(e.target.value)}
                  placeholder="Subjek"
                />
                <textarea
                  className={styles.replyTextarea}
                  value={replyBody}
                  onChange={(e) => setReplyBody(e.target.value)}
                  placeholder={replyMode === 'reply' ? '' : 'Tulis pesan pengantar di sini'}
                />
                {replyQuoteHTML && (
                  <div className={styles.replyQuotedArea}>
                    <button
                      type="button"
                      className={styles.quotedToggle}
                      onClick={() => setReplyQuoteExpanded((open) => !open)}
                      title={replyQuoteExpanded ? 'Sembunyikan pesan sebelumnya' : 'Tampilkan pesan sebelumnya'}
                    >
                      ...
                    </button>
                    {replyQuoteExpanded && (
                      <div className={styles.quotedContent} dangerouslySetInnerHTML={{ __html: replyQuoteHTML }} />
                    )}
                  </div>
                )}
                {replyAttachments.length > 0 && (
                  <div className={styles.replyAttachmentList}>
                    {replyAttachments.map((file, index) => (
                      <div key={`${file.name}-${index}`} className={styles.replyAttachmentChip}>
                        <Paperclip size={14} />
                        <span>{file.name}</span>
                        <button
                          type="button"
                          onClick={() => setReplyAttachments((prev) => prev.filter((_, i) => i !== index))}
                          title="Hapus lampiran"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div className={styles.replyBoxFooter}>
                  <button className={styles.btnReplySend} onClick={handleSendReply}>
                    Kirim
                  </button>
                  <label className={styles.replyToolBtn} title="Lampirkan file">
                    <Paperclip size={17} />
                    <input
                      type="file"
                      multiple
                      onChange={(e) => {
                        setReplyAttachments((prev) => [...prev, ...Array.from(e.target.files || [])])
                        e.target.value = ''
                      }}
                    />
                  </label>
                  <div className={styles.replyLinkWrap}>
                    <button
                      className={`${styles.replyToolBtn} ${replyLinkOpen ? styles.replyToolBtnActive : ''}`}
                      title="Sisipkan link"
                      onClick={() => setReplyLinkOpen((open) => !open)}
                    >
                      <Link size={17} />
                    </button>
                    {replyLinkOpen && (
                      <div className={styles.replyLinkPopover}>
                        <div className={styles.replyLinkField}>
                          <span className={styles.replyLinkIcon}>≡</span>
                          <input
                            value={replyLinkText}
                            onChange={(e) => setReplyLinkText(e.target.value)}
                            placeholder="Teks"
                            autoFocus
                          />
                        </div>
                        <div className={styles.replyLinkField}>
                          <Link size={16} />
                          <input
                            value={replyLinkUrl}
                            onChange={(e) => setReplyLinkUrl(e.target.value)}
                            placeholder="Ketik atau tempelkan link"
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleApplyReplyLink()
                              if (e.key === 'Escape') setReplyLinkOpen(false)
                            }}
                          />
                          <button
                            className={styles.replyLinkApply}
                            onClick={handleApplyReplyLink}
                            disabled={!replyLinkUrl.trim()}
                          >
                            Terapkan
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                  <label className={styles.replyToolBtn} title="Sisipkan gambar">
                    <Image size={17} />
                    <input
                      type="file"
                      multiple
                      accept="image/*"
                      onChange={(e) => {
                        setReplyAttachments((prev) => [...prev, ...Array.from(e.target.files || [])])
                        e.target.value = ''
                      }}
                    />
                  </label>
                  <button className={`${styles.replyToolBtn} ${styles.replyTrashBtn}`} onClick={handleDiscardReplyDraft} title="Buang draft">
                    <Trash2 size={17} />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Bottom Action Row */}
          {!replyMode && (
            <div className={styles.bottomActionRow}>
              <button className={styles.bottomBtn} onClick={() => handleOpenReply('reply')}>
                <Reply size={16} className={styles.bottomBtnIcon} />
                <span>Balas</span>
              </button>
              <button className={styles.bottomBtn} onClick={() => handleOpenReply('forward')}>
                <CornerUpRight size={16} className={styles.bottomBtnIcon} />
                <span>Teruskan</span>
              </button>
            </div>
          )}
        </div>

        {/* Right Pane: Admin security tools (Hidden for standard 'user') */}
        {showSecurityPanel && (
          <>
            <button
              className={`${styles.securityDrawerToggle} ${securityPanelOpen ? styles.securityDrawerToggleOpen : ''}`}
              onClick={() => setSecurityPanelOpen((open) => !open)}
              title={securityPanelOpen ? 'Tutup Panel Deteksi Keamanan' : 'Buka Panel Deteksi Keamanan'}
            >
              {securityPanelOpen ? <ChevronRight size={20} /> : <ShieldAlert size={20} />}
            </button>
            <div className={`${styles.securityPane} ${securityPanelOpen ? styles.securityPaneOpen : ''}`}>
              <SecurityPanelWrapper onClose={() => setSecurityPanelOpen(false)}>
                {/* Actions Panel */}
                <SecuritySection id="actions" title="Tindakan Karantina" isOpen={openPanels.actions} onToggle={togglePanel}>
                  <div className={styles.actionHeader}>
                    <span className={`${styles.badge} ${cfg.cls}`}>{cfg.text}</span>
                    {email.anomaly_score > 0
                      ? <span className={`${styles.badge} ${styles.badgeDual}`}>Dual Detection</span>
                      : <span className={`${styles.badge} ${styles.badgeML}`}>ML Only</span>}
                  </div>
                  <div style={{ height: 16 }} />
                  <div className={styles.actionButtons}>
                    <button
                      className={`${styles.btn} ${styles.btnGreen}`}
                      onClick={() => release(emailId, {
                        onSuccess: () => { showToast('Email dilepaskan ke inbox', 'success'); navigate(backPath) },
                        onError: () => showToast('Gagal melepaskan', 'error'),
                      })}
                      disabled={releasing}
                    >
                      {releasing ? 'Memproses...' : 'Lepaskan ke Inbox'}
                    </button>
                    <button
                      className={`${styles.btn} ${styles.btnRed}`}
                      onClick={() => confirmSpam(emailId, {
                        onSuccess: () => { showToast('Dikonfirmasi sebagai spam', 'info'); navigate(backPath) },
                        onError: () => showToast('Gagal mengkonfirmasi', 'error'),
                      })}
                      disabled={spamming}
                    >
                      {spamming ? 'Memproses...' : 'Konfirmasi Spam'}
                    </button>
                    <div className={styles.fpSection}>
                      <input
                        className={styles.fpInput}
                        type="text"
                        placeholder="Catatan false positive (opsional)"
                        value={fpNotes}
                        onChange={(e) => setFpNotes(e.target.value)}
                      />
                      <button
                        className={`${styles.btn} ${styles.btnYellow}`}
                        onClick={() => reportFP({ emailId, notes: fpNotes }, {
                          onSuccess: () => { showToast('False positive dilaporkan', 'warning'); navigate(backPath) },
                          onError: () => showToast('Gagal melaporkan', 'error'),
                        })}
                        disabled={reporting}
                      >
                        {reporting ? 'Memproses...' : 'Laporkan FP'}
                      </button>
                    </div>
                  </div>
                </SecuritySection>

                {/* Score Grid Panel */}
                <SecuritySection id="scores" title="Skor Deteksi" isOpen={openPanels.scores} onToggle={togglePanel}>
                  <div className={styles.scoreGrid}>
                    <div className={styles.scoreCard}>
                      <div className={styles.scoreValue}>{email.fused_score?.toFixed(3)}</div>
                      <div className={styles.scoreLabel}>Skor Akhir</div>
                    </div>
                    <div className={styles.scoreCard}>
                      <div className={styles.scoreValue}>{email.ml_probability?.toFixed(4)}</div>
                      <div className={styles.scoreLabel}>Probabilitas ML</div>
                    </div>
                    <div className={styles.scoreCard}>
                      <div className={styles.scoreValue}>{email.sa_score?.toFixed(2) || '0.00'}</div>
                      <div className={styles.scoreLabel}>SpamAssassin</div>
                    </div>
                    <div className={styles.scoreCard}>
                      <div className={styles.scoreValue}>{(email.anomaly_score || 0).toFixed(4)}</div>
                      <div className={styles.scoreLabel}>Skor Anomali</div>
                    </div>
                  </div>
                </SecuritySection>

                {/* XAI Panel */}
                {email.human_reasons?.length > 0 && (
                  <SecuritySection id="xai" title="Penjelasan AI (XAI)" isOpen={openPanels.xai} onToggle={togglePanel}>
                    <div className={styles.xaiList}>
                      {email.human_reasons.map((r, i) => (
                        <div key={i} className={styles.xaiItem}>• {r}</div>
                      ))}
                    </div>
                  </SecuritySection>
                )}

                {/* Metadata Detail Table */}
                <SecuritySection id="metadata" title="Metadata Deteksi" isOpen={openPanels.metadata} onToggle={togglePanel}>
                  <div className={styles.meta}>
                    <div className={styles.metaRow}>
                      <span className={styles.metaLabel}>Kategori</span>
                      <span className={styles.metaValue}>{email.category || email.label || '-'}</span>
                    </div>
                    <div className={styles.metaRow}>
                      <span className={styles.metaLabel}>Status</span>
                      <span className={styles.metaValue} style={{ fontWeight: 500, color: 'var(--text)' }}>
                        {email.status === 'released' ? 'Dirilis' : email.status === 'confirmed_spam' ? 'Spam' : email.status}
                      </span>
                    </div>
                    <div className={styles.metaRow}>
                      <span className={styles.metaLabel}>Model Versi</span>
                      <span className={styles.metaValue}>{email.model_version || 'N/A'}</span>
                    </div>
                    <div className={styles.metaRow}>
                      <span className={styles.metaLabel}>Alasan Routing</span>
                      <span className={styles.metaValue}>{email.routing_reason || 'N/A'}</span>
                    </div>
                  </div>
                </SecuritySection>
              </SecurityPanelWrapper>
            </div>
          </>
        )}
      </div>
      <ConfirmDialog
        open={deleteDialogOpen}
        title="Konfirmasi penghapusan pesan"
        message={
          email.status === 'trash'
            ? 'Tindakan ini akan menghapus permanen percakapan ini. Apakah Anda yakin ingin melanjutkan?'
            : 'Tindakan ini akan memindahkan percakapan ini ke Sampah. Apakah Anda yakin ingin melanjutkan?'
        }
        onCancel={() => setDeleteDialogOpen(false)}
        onConfirm={confirmDelete}
        busy={deleting}
      />
    </GmailShell>
  )
}
