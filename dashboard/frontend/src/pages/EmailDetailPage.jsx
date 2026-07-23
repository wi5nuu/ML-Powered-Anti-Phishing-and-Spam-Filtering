import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Reply, MoreVertical, Trash2, Mail,
  Printer, ExternalLink, Star, ShieldAlert, Smile,
  ChevronLeft, ChevronRight, CornerUpRight, ChevronDown, ChevronRight as ChevronRightIcon, X, Paperclip, Download,
  Code2, Link, Image
} from 'lucide-react'
import { useTranslation } from '../i18n/context'
import api from '../api/client'
import GmailShell from '../components/layout/GmailShell'
import ConfirmDialog from '../components/common/ConfirmDialog'
import {
  useEmail,
  useEmails,
  useReleaseEmail,
  useConfirmSpam,
  useReportFalsePositive,
  useReportFalseNegative,
  useDeleteEmail,
  useToggleReadEmail,
  useToggleStarred,
} from '../api/emails'
import { useMe } from '../api/auth'
import { useToast } from '../hooks/useToast'
import { useEffect, useRef, useState } from 'react'
import { getActiveMailbox, getActiveMailboxId } from '../utils/mailbox'
import { formatAppDateTime } from '../utils/time'
import { findExistingDraft } from '../utils/threadUtils'
import styles from './EmailDetailPage.module.css'

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
  // Decode stored HTML entities once before escaping for display. Outbound
  // thread quotes are stored with safe entities (for example &lt;address&gt;);
  // escaping the encoded source again would expose "&lt;" to the user.
  return escapeHtml(decoded).replace(/\n/g, '<br />')
}

function plainFromHtmlish(value = '') {
  return String(value || '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
}

function stripQuotedThread(value = '') {
  const { body: visibleBody } = splitQuotedThread(value)
  const plain = plainFromHtmlish(visibleBody)
  const metadataQuoteIndex = plain.search(/\n?\s*(?:Dari:\s*.+\n)?Tanggal:\s*.+\nSubjek:\s*.+\nKepada:\s*/i)
  if (metadataQuoteIndex >= 0) return plain.slice(0, metadataQuoteIndex).trim()
  const [body] = plain.split(/\n\s*-{5,}\s*(?:Original|Forwarded) message\s*-{5,}\s*/i)
  return (body || plain).trim()
}

function splitQuotedThread(value = '') {
  const source = stripRawHeaders(value)

  // Replies generated by CogniMail and Gmail use this wrapper. Preserve the
  // HTML so links and formatting remain intact when the user expands it.
  const gmailQuote = source.match(/<div\b[^>]*class=["'][^"']*\bgmail_quote\b[^"']*["'][^>]*>/i)
  if (gmailQuote?.index >= 0) {
    return {
      body: source.slice(0, gmailQuote.index).replace(/(?:<br\s*\/?>\s*)+$/i, '').trim(),
      quote: source.slice(gmailQuote.index).trim(),
    }
  }

  // Some Gmail clients omit the outer gmail_quote div but retain a
  // blockquote. Include its attribution line in the collapsed section.
  const blockquote = source.match(/<blockquote\b[^>]*>/i)
  if (blockquote?.index >= 0) {
    const before = source.slice(0, blockquote.index)
    const attrMatches = [...before.matchAll(/<div\b[^>]*class=["'][^"']*\bgmail_attr\b[^"']*["'][^>]*>/gi)]
    const lastAttr = attrMatches[attrMatches.length - 1]
    const quoteStart = lastAttr?.index ?? blockquote.index
    return {
      body: source.slice(0, quoteStart).replace(/(?:<br\s*\/?>\s*)+$/i, '').trim(),
      quote: source.slice(quoteStart).trim(),
    }
  }

  const plain = plainFromHtmlish(source)
  const match = plain.match(/\n\s*(-{5,}\s*(?:Original|Forwarded) message\s*-{5,}\s*[\s\S]*)/i)
  if (match) return { body: plain.slice(0, match.index).trim(), quote: match[1].trim() }

  // Localized Gmail plaintext attribution (for example "Pada ... menulis:")
  // is also quoted history, even when the MIME-to-HTML conversion removed its
  // original blockquote tag.
  const localizedQuote = plain.match(/\n\s*((?:On\s.+?\swrote:|Pada\s.+?\smenulis:)\s*[\s\S]*)/i)
  if (localizedQuote) {
    return {
      body: plain.slice(0, localizedQuote.index).trim(),
      quote: localizedQuote[1].trim(),
    }
  }
  return { body: plain.trim(), quote: '' }
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

function SecurityPanelWrapper({ onClose, children, t }) {
  return (
    <div className={styles.securityWrapper}>
      <div className={styles.securityWrapperHeader}>
        <span>{t('email.securityPanel')}</span>
        <button className={styles.securityCloseBtn} onClick={onClose} title={t('email.closePanel')}>
          <X size={18} />
        </button>
      </div>
      <div className={styles.securityWrapperBody}>
        {children}
      </div>
    </div>
  )
}

export default function EmailDetailPage({ overrideEmailId = null }) {
  const { t } = useTranslation()
  const { emailId: paramEmailId } = useParams()
  const emailId = overrideEmailId || paramEmailId || ''
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()

  const { showToast } = useToast()
  const fromPath = searchParams.get('from') || ''
  const originalView = searchParams.get('original') === '1'
  const fromParams = new URLSearchParams(fromPath.split('?')[1] || '')
  const activeMailboxId = getActiveMailboxId(searchParams) || getActiveMailboxId(fromParams)
  const activeMailbox = getActiveMailbox(searchParams) || getActiveMailbox(fromParams)

  const badgeCfg = {
    quarantine: { text: t('label.quarantine'), cls: styles.badgeQ },
    warn: { text: t('label.warn'), cls: styles.badgeW },
    clean: { text: t('label.clean'), cls: styles.badgeC },
  }

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

  const { mutateAsync: deleteEmail, isPending: deleting } = useDeleteEmail()
  const { mutateAsync: releaseEmail, isPending: releasing } = useReleaseEmail()
  const { mutateAsync: confirmSpam, isPending: spamming } = useConfirmSpam()
  const { mutateAsync: reportFP, isPending: reporting } = useReportFalsePositive()
  const { mutateAsync: reportFN, isPending: reportingFN } = useReportFalseNegative()
  const { mutateAsync: toggleRead } = useToggleReadEmail()
  const { mutate: toggleStarredMutate } = useToggleStarred()

  const [fpNotes, setFpNotes] = useState('')
  const [fnNotes, setFnNotes] = useState('')
  const [fnLabel, setFnLabel] = useState('phishing')
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
  const [isUnread, setIsUnread] = useState(false)

  useEffect(() => {
    if (email) {
      const currentlyRead = email.thread_is_read
        ?? (email.thread_has_unread != null ? !email.thread_has_unread : email.is_read)
      setIsUnread(!currentlyRead)
      const isDraftEmail = String(email.label || '').toUpperCase() === 'DRAFT' || email.status === 'draft'
      if (!currentlyRead && !isDraftEmail) {
        toggleRead({ emailId: email.email_id, isRead: true }).catch(() => {})
        setIsUnread(false)
      }
    }
  }, [email])

  useEffect(() => {
    setInlineSentReplies([])
    setHydratedDraftId('')
    setExpandedQuoteIds(new Set())
    setReplyQuoteExpanded(false)
    setThreadRecipientDetailId(null)
  }, [emailId])

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
      <div style={{ padding: 32, color: 'var(--text-muted)', fontFamily: 'Google Sans' }}>{t('common.loading')}</div>
    </GmailShell>
  )

  if (isError || !email) return (
    <GmailShell>
      <div style={{ padding: 32, color: '#EA4335', fontFamily: 'Google Sans' }}>{t('email.notFound')}</div>
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
    ? t('gmail.sent')
    : email.status === 'trash'
      ? t('gmail.trash')
      : label === 'quarantine' || ['spam', 'phishing', 'malware'].includes((email.category || '').toLowerCase())
        ? t('gmail.quarantine')
        : t('gmail.inbox')
  const cfg = badgeCfg[label] || badgeCfg.clean
  const shap = email.shap_data
  const maxShap = shap?.features?.length
    ? Math.max(...shap.features.map((f) => Math.abs(f.shap)))
    : 1

  const emailBodyHTML = renderEmailBody(email.raw_content, t('email.noContent'))
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
          <span>{t('attachment.count', { count: attachments.length })}</span>
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
                title={attachment.stored ? t('email.attachmentPreview') : t('email.attachmentTooLarge')}
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
                  <a className={styles.attachmentDownload} href={downloadUrl} title={t('email.downloadAttachment')}>
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
      showToast(err.response?.data?.detail || t('email.failOpenDraft'), 'error')
    }
  }

  const renderThreadMessage = (message, index) => {
    const detailId = message.email_id || `${message.subject}-${index}`
    const isSentMessage = String(message.label || '').toUpperCase() === 'SENT' || message.direction === 'sent'
    const isDraftMessage = String(message.label || '').toUpperCase() === 'DRAFT' || message.direction === 'draft'
    const isOwnMessage = isSentMessage || isDraftMessage
    const senderIdentity = parseEmailIdentity(message.sender || '')
    const senderName = isOwnMessage
      ? (senderIdentity.name || message.sender || mailboxIdentity || t('email.me'))
      : (senderIdentity.name || t('email.sender'))
    const senderEmail = senderIdentity.email || ''
    const messageRecipients = normalizeRecipients(message.recipient_list).join(', ') || t('email.me').toLowerCase()
    const messageRecipientLine = isOwnMessage ? `${t('email.to')} ${messageRecipients}` : t('email.toMe')
    const initial = (isOwnMessage ? mailboxInitial : senderName.trim()[0]?.toUpperCase()) || 'U'
    const bg = isOwnMessage ? mailboxAvatarBg : avatarColors[initial.charCodeAt(0) % avatarColors.length]
    const splitBody = splitQuotedThread(message.raw_content)
    const bodySource = splitBody.body
    const bodyHTML = renderEmailBody(bodySource, t('email.noContent'))
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
                {isDraftMessage && <span className={styles.threadDraftBadge}>{t('email.draft')}</span>}
                {threadRecipientDetailId === detailId && (
                  <div className={styles.recipientDropdown}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-light)', paddingBottom: 8, marginBottom: 8 }}>
                      <strong style={{ fontSize: '0.875rem' }}>{t('email.detailInfo')}</strong>
                      <button
                        style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)' }}
                        onClick={() => setThreadRecipientDetailId(null)}
                      >
                        <X size={16} />
                      </button>
                    </div>
                    <div className={styles.recipientRow}>
                      <span className={styles.recipientLabel}>{t('email.from')}</span>
                      <span className={styles.recipientValue}>{message.sender || '-'}</span>
                    </div>
                    <div className={styles.recipientRow}>
                      <span className={styles.recipientLabel}>{t('email.toLabel')}</span>
                      <span className={styles.recipientValue}>{messageRecipients}</span>
                    </div>
                    <div className={styles.recipientRow}>
                      <span className={styles.recipientLabel}>{t('email.date')}</span>
                      <span className={styles.recipientValue}>
                        {message.received_at ? formatAppDateTime(message.received_at, { dateStyle: 'full', timeStyle: 'medium' }) : 'N/A'}
                      </span>
                    </div>
                    <div className={styles.recipientRow}>
                      <span className={styles.recipientLabel}>{t('common.subject')}</span>
                      <span className={styles.recipientValue}>{message.subject || displaySubject}</span>
                    </div>
                    <div className={styles.recipientRow}>
                      <span className={styles.recipientLabel}>{t('common.category')}</span>
                      <span className={styles.recipientValue}>{message.category || message.label || '-'}</span>
                    </div>
                  </div>
                )}
              </div>
              <div className={styles.threadHeaderActions}>
                <time>{message.received_at ? formatAppDateTime(message.received_at, { dateStyle: 'medium', timeStyle: 'short' }) : 'N/A'}</time>
                {isDraftMessage && (
                  <button className={styles.threadTextBtn} onClick={() => openThreadDraftCompose(message)}>
                    {t('email.editDraft')}
                  </button>
                )}
                <button className={styles.threadIconBtn} onClick={handleToggleStar} title={t('email.star')}>
                  <Star size={16} fill={isStarred ? '#f29900' : 'none'} />
                </button>
                <button className={styles.threadIconBtn} onClick={() => handleOpenReply('reply', message)} title={t('action.reply')}>
                  <Reply size={16} />
                </button>
                <button className={styles.threadIconBtn} onClick={() => handleOpenReply('forward', message)} title={t('action.forward')}>
                  <CornerUpRight size={16} />
                </button>
                <button className={styles.threadIconBtn} onClick={(event) => handleMoreActions(event, `thread-${message.email_id}`)} title={t('email.more')}>
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
                  title={quoteOpen ? t('email.hideQuote') : t('email.showQuote')}
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
    ? `${currentIndex + 1} ${t('email.of')} ${emailList.length}`
    : `1 ${t('email.of')} 1`

  const isStarred = email?.is_starred ?? false

  const handleToggleStar = () => {
    const nextVal = !isStarred
    toggleStarredMutate({ emailId: email.email_id, isStarred: nextVal })
    showToast(nextVal ? t('email.addedToStarred') : t('email.removedFromStarred'), 'info')
  }

  const handleArchive = () => {
    if (role !== 'superadmin' && role !== 'admin') {
      showToast(t('msg.actionDenied'), 'error')
      return
    }
    releaseEmail(emailId, {
      onSuccess: () => {
        showToast(t('email.releasedToInbox'), 'success')
        navigate(backPath)
      },
      onError: () => showToast(t('email.failRelease'), 'error'),
    })
  }

  const handleSpam = () => {
    if (role !== 'superadmin' && role !== 'admin') {
      showToast(t('msg.actionDenied'), 'error')
      return
    }
    confirmSpam(emailId, {
      onSuccess: () => {
        showToast(t('email.movedToSpam'), 'info')
        navigate(backPath)
      },
      onError: () => showToast(t('email.failConfirmSpam'), 'error'),
    })
  }

  const handleDelete = () => {
    setDeleteDialogOpen(true)
  }

  const confirmDelete = () => {
    const alreadyTrash = String(email.label || '').toUpperCase() === 'TRASH' || email.status === 'trash'
    deleteEmail(emailId, {
      onSuccess: () => {
        if (alreadyTrash) showToast(t('email.deletedPermanently'), 'success')
        setDeleteDialogOpen(false)
        navigate(backPath)
      },
      onError: (err) => showToast(err.response?.data?.detail || t('email.failDelete'), 'error'),
    })
  }

  const handleToggleUnread = async () => {
    const nextVal = !isUnread
    setIsUnread(nextVal)
    try {
      await toggleRead({ emailId: emailId, isRead: !nextVal })
      showToast(nextVal ? t('email.markedUnread') : t('email.markedRead'), 'info')
    } catch (err) {
      setIsUnread(!nextVal)
      showToast(err.response?.data?.detail || t('common.error'), 'error')
    }
  }

  const handleMoveTo = () => {
    // Move to trash is the only supported action for users
    deleteEmail(email.email_id, {
      onSuccess: () => {
        showToast(t('email.movedToTrash') || 'Email dipindahkan ke Sampah', 'success')
        navigate(backPath)
      },
      onError: () => showToast(t('email.failDelete'), 'error'),
    })
  }

  const handleAddLabel = () => {
    // Toggle starred as the primary label action available
    const nextVal = !isStarred
    toggleStarredMutate({ emailId: email.email_id, isStarred: nextVal })
    showToast(nextVal ? (t('email.addedToStarred') || 'Ditambahkan ke Berbintang') : (t('email.removedFromStarred') || 'Dihapus dari Berbintang'), 'info')
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
          <title>${escapeHtml(email.subject || t('email.print'))}</title>
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
            <h1>${escapeHtml(email.subject || t('common.noSubject'))}</h1>
            <div class="meta">
              <div><div class="sender">${escapeHtml(email.sender || t('email.unknownSender'))}</div><div>${t('print.to')} ${escapeHtml(recipientText)}</div></div>
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
      showToast(t('email.originalCopied'), 'success')
    } catch {
      showToast(t('email.failCopy'), 'error')
    }
  }

  const handleOpenReply = (mode, sourceMessage = email) => {
    const source = sourceMessage || email
    const isSourceSent = String(source.label || '').toUpperCase() === 'SENT' || source.direction === 'sent'
    const sourceRecipients = normalizeRecipients(source.recipient_list)
    const sourceRecipientText = sourceRecipients.join(', ')
    closeMessageMenu()
    setReplyActionMenuOpen(false)
    setReplyLinkOpen(false)
    setReplyAttachments([])

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
    } else if (mode === 'reply_all') {
      const allAddresses = [
        isSourceSent ? '' : source.sender || '',
        ...sourceRecipients,
      ].filter((addr) => {
        if (!addr) return false
        const lower = addr.toLowerCase()
        return lower !== (activeMailbox || '').toLowerCase() &&
               lower !== (meData?.user?.email || '').toLowerCase() &&
               lower !== (meData?.user?.username || '').toLowerCase()
      })
      const uniqueAddresses = [...new Set(allAddresses)]
      setReplyTo(uniqueAddresses.join(', '))
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
    if (values.length === 0) return { ok: false, message: t('msg.recipientRequired') }
    const invalid = values.find((value) => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value))
    if (invalid) return { ok: false, message: t('msg.invalidEmail').replace('{email}', invalid) }
    return { ok: true, recipients: Array.from(new Set(values)) }
  }

  const quotedOriginalMessage = () => replyTargetMessage || email
  const quotedOriginalMetaLines = () => {
    const source = quotedOriginalMessage()
    const metaPrefix = replyMode === 'forward' ? t('email.forwardTitle') : t('email.originalTitle')
    return [
      `---------- ${metaPrefix} ---------`,
      `${t('email.from')} ${source.sender || '-'}`,
      `${t('email.date')} ${source.received_at ? formatAppDateTime(source.received_at, { dateStyle: 'medium', timeStyle: 'short' }) : '-'}`,
      `${t('common.subject')}: ${source.subject || t('common.noSubject')}`,
      `${t('email.toLabel')} ${normalizeRecipients(source.recipient_list).join(', ') || recipientText || t('email.me').toLowerCase()}`,
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
      const parentEmailIdForDraft = replyTargetMessage?.email_id || email.email_id
      const composeModeForDraft = replyMode || 'reply'
      let response
      if (replyAttachments.length > 0) {
        const formData = new FormData()
        formData.append('draft_id', replyDraftIdRef.current || replyDraftId)
        formData.append('to', finalRecipients)
        formData.append('from_email', activeMailbox || recipients[0] || meData?.user?.email || meData?.user?.username || '')
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
          from_email: activeMailbox || recipients[0] || meData?.user?.email || meData?.user?.username || '',
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
      if (!silent) showToast(t('email.draftSaved'), 'success')
      queryClient.invalidateQueries({ queryKey: ['emails'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
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
      if (!silent) showToast(t('email.failSaveDraft') + (err.response?.data?.detail ? ': ' + err.response.data.detail : ''), 'error')
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
      queryClient.invalidateQueries({ queryKey: ['stats'] })
      queryClient.invalidateQueries({ queryKey: ['email', email.email_id] })
      if (targetId && isDraftDetail && targetId !== email.email_id) {
        navigate(makeDetailUrl(targetId), { replace: true })
      }
      showToast(t('email.draftDiscarded'), 'info')
    } catch (err) {
      showToast(err.response?.data?.detail || t('email.failDiscardDraft'), 'error')
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
        formData.append('from_email', activeMailbox || recipients[0] || meData?.user?.email || meData?.user?.username || '')
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
          from_email: activeMailbox || recipients[0] || meData?.user?.email || meData?.user?.username || '',
          subject: replySubject,
          body: finalBody,
          reply_to_id: (replyTargetMessage || email).email_id,
          draft_id: replyDraftIdRef.current || replyDraftId,
          action: replyMode,
        })
      }
      showToast(
        replyMode === 'reply'
          ? t('email.replySent')
          : t('email.forwarded'),
        'success'
      )
      setInlineSentReplies((prev) => hasThreadMessages ? prev : [
        ...prev,
        {
          id: response?.data?.email_id || `inline-${Date.now()}`,
          sender: activeMailbox || recipients[0] || mailboxIdentity || t('email.me'),
          recipient: finalRecipients,
          subject: replySubject,
          body: finalBody,
          sentAt: new Date().toISOString(),
          attachments: replyAttachments.map((file) => ({ name: file.name, size: file.size })),
        },
      ])
      queryClient.invalidateQueries({ queryKey: ['email', email.email_id] })
      queryClient.invalidateQueries({ queryKey: ['emails'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
      setReplyAttachments([])
      setReplyDraftId('')
      replyDraftIdRef.current = ''
      replyAutosaveSignatureRef.current = ''
      setReplyMode(null)
      setReplyTargetMessage(null)
    } catch (err) {
      const detail = err.response?.data?.detail
      const message = typeof detail === 'object'
        ? `${detail.message || t('email.failSendReasonNoReason')}${detail.reason ? ` ${detail.reason}` : ''}`
        : detail || err.message
      showToast(t('email.failSend') + message, 'error')
    }
  }

  const renderMessageMenu = (placement = 'message', sourceMessage = email) => (
    <div className={`${styles.messageMenu} ${placement === 'toolbar' ? styles.messageMenuToolbar : ''}`}>
      <button onClick={() => handleOpenReply('reply', sourceMessage)}><Reply size={16} />{t('action.reply')}</button>
      <button onClick={() => handleOpenReply('forward', sourceMessage)}><CornerUpRight size={16} />{t('action.forward')}</button>
      <div className={styles.menuDivider} />
      <button onClick={() => { closeMessageMenu(); handleDelete() }}><Trash2 size={16} />{t('action.delete')}</button>
      <button onClick={() => { closeMessageMenu(); handleToggleUnread() }}><Mail size={16} />{t('action.markUnread')}</button>
      <div className={styles.menuDivider} />
      <button onClick={() => { closeMessageMenu(); handleSpam() }}><ShieldAlert size={16} />{t('action.reportSpam')}</button>
      <button onClick={() => { closeMessageMenu(); reportFP(sourceMessage.email_id || emailId, { onSuccess: () => showToast(t('email.reportedAsPhishing'), 'warning'), onError: () => showToast(t('email.failReportPhishing'), 'error') }) }}><ShieldAlert size={16} />{t('action.reportPhishing')}</button>
      <button onClick={() => { closeMessageMenu(); handlePrint() }}><Printer size={16} />{t('action.print')}</button>
      <button onClick={() => { closeMessageMenu(); handleDownloadMessage() }}><Download size={16} />{t('action.downloadMessage')}</button>
      <button onClick={() => { closeMessageMenu(); handleOpenNewWindow() }}><Code2 size={16} />{t('action.showOriginal')}</button>
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
              title={t('action.selectAction')}
            >
              {replyMode === 'reply' ? <Reply size={16} /> : <CornerUpRight size={16} />}
              <ChevronDown size={14} />
            </button>
            {replyActionMenuOpen && (
              <div className={styles.replyActionMenu}>
                <button onClick={() => handleOpenReply('reply', replyTargetMessage || email)}><Reply size={16} />{t('action.reply')}</button>
                <button onClick={() => handleOpenReply('forward', replyTargetMessage || email)}><CornerUpRight size={16} />{t('action.forward')}</button>
                <div className={styles.menuDivider} />
                <button onClick={() => showToast(t('email.subjectEditable'), 'info')}>{t('action.editSubject')}</button>
                <button onClick={() => { closeReplyBox(); setReplyActionMenuOpen(false) }}>{t('action.discard')}</button>
              </div>
            )}
          </div>
          <input
            type="text"
            className={styles.replyToInput}
            value={replyTo}
            onChange={(e) => setReplyTo(e.target.value)}
            placeholder={t('placeholder.to')}
          />
          <button className={styles.replyIconBtn} onClick={closeReplyBox} title={t('btn.close')}>
            <X size={16} />
          </button>
        </div>
        <input
          type="text"
          className={styles.replySubjectInput}
          value={replySubject}
          onChange={(e) => setReplySubject(e.target.value)}
          placeholder={t('placeholder.subject')}
        />
        <textarea
          className={styles.replyTextarea}
          value={replyBody}
          onChange={(e) => setReplyBody(e.target.value)}
          placeholder={replyMode === 'reply' ? '' : t('placeholder.writeMessage')}
        />
        {replyQuoteHTML && (
          <div className={styles.replyQuotedArea}>
            <button
              type="button"
              className={styles.quotedToggle}
              onClick={() => setReplyQuoteExpanded((open) => !open)}
              title={replyQuoteExpanded ? t('email.hideQuote') : t('email.showQuote')}
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
                  title={t('action.removeAttachment')}
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className={styles.replyBoxFooter}>
          <button className={styles.btnReplySend} onClick={handleSendReply}>
            {t('action.send')}
          </button>
          <label className={styles.replyToolBtn} title={t('action.attachFile')}>
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
              title={t('action.insertLink')}
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
                    placeholder={t('placeholder.text')}
                    autoFocus
                  />
                </div>
                <div className={styles.replyLinkField}>
                  <Link size={16} />
                  <input
                    value={replyLinkUrl}
                    onChange={(e) => setReplyLinkUrl(e.target.value)}
                    placeholder={t('placeholder.link')}
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
                    {t('action.apply')}
                  </button>
                </div>
              </div>
            )}
          </div>
          <label className={styles.replyToolBtn} title={t('action.insertImage')}>
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
          <button className={`${styles.replyToolBtn} ${styles.replyTrashBtn}`} onClick={handleDiscardReplyDraft} title={t('action.discardDraft')}>
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
            <h1>{t('original.pageTitle')}</h1>
            <p>{email.subject || t('common.noSubject')}</p>
          </div>
          <div className={styles.originalActions}>
            <button onClick={handleDownloadMessage}>{t('original.download')}</button>
            <button onClick={handleCopyOriginal}>{t('original.copyClipboard')}</button>
          </div>
        </header>

        <section className={styles.originalMeta}>
          <div><span>{t('original.messageId')}</span><strong>&lt;{email.email_id}@cognimail.local&gt;</strong></div>
          <div><span>{t('email.created')}</span><strong>{receivedText}</strong></div>
          <div><span>{t('email.from').replace(':', '')}</span><strong>{email.sender || '-'}</strong></div>
          <div><span>{t('email.toLabel').replace(':', '')}</span><strong>{recipientText}</strong></div>
          <div><span>{t('common.subject')}</span><strong>{email.subject || t('common.noSubject')}</strong></div>
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
        <div className={styles.emailPane}>
          <div className={styles.toolbar}>
            <div className={styles.toolbarLeft}>
              <button className={styles.toolbarBtn} onClick={() => navigate(backPath)} title={t('toolbar.back')}>
                <ArrowLeft size={18} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleSpam} title={t('toolbar.reportSpam')}>
                <ShieldAlert size={18} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleDelete} title={t('toolbar.delete')}>
                <Trash2 size={18} />
              </button>
              <button
                className={`${styles.toolbarBtn} ${isUnread ? styles.unreadActive : ''}`}
                onClick={handleToggleUnread}
                title={t('toolbar.markUnread')}
              >
                <Mail size={18} />
              </button>
              <div className={styles.moreMenuWrap}>
                <button className={styles.toolbarBtn} onClick={(e) => handleMoreActions(e, 'toolbar')} title={t('toolbar.more')}>
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
                title={t('toolbar.newer')}
              >
                <ChevronLeft size={18} />
              </button>
              <button
                className={styles.toolbarBtn}
                disabled={!nextEmail}
                onClick={() => nextEmail && navigate(makeDetailUrl(nextEmail.email_id))}
                title={t('toolbar.older')}
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>

          <div className={styles.subjectRow}>
            <h1 className={styles.subjectTitle}>
              {displaySubject || t('common.noSubject')}
              <span className={styles.badgeInbox}>{folderBadgeText} x</span>
            </h1>
            <div className={styles.subjectActions}>
              <button className={styles.toolbarBtn} onClick={handlePrint} title={t('toolbar.printAll')}>
                <Printer size={18} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleOpenNewWindow} title={t('toolbar.openNewWindow')}>
                <ExternalLink size={18} />
              </button>
            </div>
          </div>

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
                      <a href={attachmentUrl(previewEmailId, previewAttachment, true)} title={t('email.downloadAttachment')}>
                        <Download size={18} />
                      </a>
                      <button type="button" onClick={() => setPreviewAttachment(null)} title={t('preview.closePreview')}>
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
                        <p>{t('preview.cannotPreview')}</p>
                        <a href={attachmentUrl(previewEmailId, previewAttachment, true)}>{t('preview.downloadFile')}</a>
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
                    <span> {t('email.to')} {reply.recipient}</span>
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
                    <span>{t('attachment.count', { count: reply.attachments.length })}</span>
                  </div>
                )}
              </div>
            </div>
          ))}

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
                      title={t('action.selectAction')}
                    >
                      {replyMode === 'reply' ? <Reply size={16} /> : <CornerUpRight size={16} />}
                      <ChevronDown size={14} />
                    </button>
                    {replyActionMenuOpen && (
                      <div className={styles.replyActionMenu}>
                        <button onClick={() => handleOpenReply('reply', replyTargetMessage || email)}><Reply size={16} />{t('action.reply')}</button>
                        <button onClick={() => handleOpenReply('forward', replyTargetMessage || email)}><CornerUpRight size={16} />{t('action.forward')}</button>
                        <div className={styles.menuDivider} />
                        <button onClick={() => showToast(t('email.subjectEditable'), 'info')}>{t('action.editSubject')}</button>
                        <button onClick={() => { closeReplyBox(); setReplyActionMenuOpen(false) }}>{t('action.discard')}</button>
                      </div>
                    )}
                  </div>
                  <input
                    type="text"
                    className={styles.replyToInput}
                    value={replyTo}
                    onChange={(e) => setReplyTo(e.target.value)}
                    placeholder={t('placeholder.to')}
                  />
                  <button className={styles.replyIconBtn} onClick={closeReplyBox} title={t('btn.close')}>
                    <X size={16} />
                  </button>
                </div>
                <input
                  type="text"
                  className={styles.replySubjectInput}
                  value={replySubject}
                  onChange={(e) => setReplySubject(e.target.value)}
                  placeholder={t('placeholder.subject')}
                />
                <textarea
                  className={styles.replyTextarea}
                  value={replyBody}
                  onChange={(e) => setReplyBody(e.target.value)}
                  placeholder={replyMode === 'reply' ? '' : t('placeholder.writeMessage')}
                />
                {replyQuoteHTML && (
                  <div className={styles.replyQuotedArea}>
                    <button
                      type="button"
                      className={styles.quotedToggle}
                      onClick={() => setReplyQuoteExpanded((open) => !open)}
                      title={replyQuoteExpanded ? t('email.hideQuote') : t('email.showQuote')}
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
                          title={t('action.removeAttachment')}
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div className={styles.replyBoxFooter}>
                  <button className={styles.btnReplySend} onClick={handleSendReply}>
                    {t('action.send')}
                  </button>
                  <label className={styles.replyToolBtn} title={t('action.attachFile')}>
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
                      title={t('action.insertLink')}
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
                            placeholder={t('placeholder.text')}
                            autoFocus
                          />
                        </div>
                        <div className={styles.replyLinkField}>
                          <Link size={16} />
                          <input
                            value={replyLinkUrl}
                            onChange={(e) => setReplyLinkUrl(e.target.value)}
                            placeholder={t('placeholder.link')}
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
                            {t('action.apply')}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                  <label className={styles.replyToolBtn} title={t('action.insertImage')}>
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
                  <button className={`${styles.replyToolBtn} ${styles.replyTrashBtn}`} onClick={handleDiscardReplyDraft} title={t('action.discardDraft')}>
                    <Trash2 size={17} />
                  </button>
                </div>
              </div>
            </div>
          )}

          {!replyMode && (
            <div className={styles.bottomActionRow}>
              <button className={styles.bottomBtn} onClick={() => handleOpenReply('reply')}>
                <Reply size={16} className={styles.bottomBtnIcon} />
                <span>{t('action.reply')}</span>
              </button>
              <button className={styles.bottomBtn} onClick={() => handleOpenReply('forward')}>
                <CornerUpRight size={16} className={styles.bottomBtnIcon} />
                <span>{t('action.forward')}</span>
              </button>
            </div>
          )}
        </div>

        {showSecurityPanel && (
          <>
            <button
              className={`${styles.securityDrawerToggle} ${securityPanelOpen ? styles.securityDrawerToggleOpen : ''}`}
              onClick={() => setSecurityPanelOpen((open) => !open)}
              title={securityPanelOpen ? t('toolbar.closeSecurityPanel') : t('toolbar.openSecurityPanel')}
            >
              {securityPanelOpen ? <ChevronRight size={20} /> : <ShieldAlert size={20} />}
            </button>
            <div className={`${styles.securityPane} ${securityPanelOpen ? styles.securityPaneOpen : ''}`}>
              <SecurityPanelWrapper onClose={() => setSecurityPanelOpen(false)} t={t}>
                <SecuritySection id="actions" title={t('panel.actions')} isOpen={openPanels.actions} onToggle={togglePanel}>
                  <div className={styles.actionHeader}>
                    <span className={`${styles.badge} ${cfg.cls}`}>{cfg.text}</span>
                    {email.anomaly_score > 0
                      ? <span className={`${styles.badge} ${styles.badgeDual}`}>{t('score.dual')}</span>
                      : <span className={`${styles.badge} ${styles.badgeML}`}>{t('score.mlOnly')}</span>}
                  </div>
                  <div style={{ height: 16 }} />
                  <div className={styles.actionButtons}>
                    <button
                      className={`${styles.btn} ${styles.btnGreen}`}
                      onClick={() => releaseEmail(emailId, {
                        onSuccess: () => { showToast(t('email.releasedToInbox'), 'success'); navigate(backPath) },
                        onError: () => showToast(t('email.failRelease'), 'error'),
                      })}
                      disabled={releasing}
                    >
                      {releasing ? t('action.processing') : t('action.releaseToInbox')}
                    </button>
                    <button
                      className={`${styles.btn} ${styles.btnRed}`}
                      onClick={() => confirmSpam(emailId, {
                        onSuccess: () => { showToast(t('email.confirmedAsSpam'), 'info'); navigate(backPath) },
                        onError: () => showToast(t('email.failConfirmSpam'), 'error'),
                      })}
                      disabled={spamming}
                    >
                      {spamming ? t('action.processing') : t('action.confirmSpam')}
                    </button>
                    <div className={styles.fpSection}>
                      <input
                        className={styles.fpInput}
                        type="text"
                        placeholder={t('placeholder.fpNotes')}
                        value={fpNotes}
                        onChange={(e) => setFpNotes(e.target.value)}
                      />
                      <button
                        className={`${styles.btn} ${styles.btnYellow}`}
                        onClick={() => reportFP({ emailId, notes: fpNotes }, {
                          onSuccess: () => { showToast(t('email.falsePositiveReported'), 'warning'); navigate(backPath) },
                          onError: () => showToast(t('email.failReportFalsePositive'), 'error'),
                        })}
                        disabled={reporting}
                      >
                        {reporting ? t('action.processing') : t('action.reportFP')}
                      </button>
                    </div>
                    {(email.label === 'CLEAN' || email.label === 'WARN') && (
                      <div className={styles.fpSection}>
                        <select
                          className={styles.fpInput}
                          value={fnLabel}
                          onChange={(e) => setFnLabel(e.target.value)}
                          style={{ marginRight: '8px' }}
                        >
                          <option value="phishing">Phishing</option>
                          <option value="spam">Spam</option>
                          <option value="malware">Malware</option>
                          <option value="suspicious">Suspicious</option>
                        </select>
                        <input
                          className={styles.fpInput}
                          type="text"
                          placeholder="Notes (why is this dangerous?)"
                          value={fnNotes}
                          onChange={(e) => setFnNotes(e.target.value)}
                        />
                        <button
                          className={`${styles.btn} ${styles.btnRed}`}
                          onClick={() => reportFN({ emailId, correctedLabel: fnLabel, notes: fnNotes }, {
                            onSuccess: () => { showToast('Email reported as false negative for training', 'warning'); navigate(backPath) },
                            onError: (err) => showToast(err.response?.data?.detail || 'Failed to report false negative', 'error'),
                          })}
                          disabled={reportingFN}
                        >
                          {reportingFN ? 'Processing...' : 'Report False Negative'}
                        </button>
                      </div>
                    )}
                  </div>
                </SecuritySection>

                <SecuritySection id="scores" title={t('panel.scores')} isOpen={openPanels.scores} onToggle={togglePanel}>
                  <div className={styles.scoreGrid}>
                    <div className={styles.scoreCard}>
                      <div className={styles.scoreValue}>{email.fused_score?.toFixed(3)}</div>
                      <div className={styles.scoreLabel}>{t('score.final')}</div>
                    </div>
                    <div className={styles.scoreCard}>
                      <div className={styles.scoreValue}>{email.ml_probability?.toFixed(4)}</div>
                      <div className={styles.scoreLabel}>{t('score.ml')}</div>
                    </div>
                    <div className={styles.scoreCard}>
                      <div className={styles.scoreValue}>{email.sa_score?.toFixed(2) || '0.00'}</div>
                      <div className={styles.scoreLabel}>{t('score.spamAssassin')}</div>
                    </div>
                    <div className={styles.scoreCard}>
                      <div className={styles.scoreValue}>{(email.anomaly_score || 0).toFixed(4)}</div>
                      <div className={styles.scoreLabel}>{t('score.anomaly')}</div>
                    </div>
                  </div>
                </SecuritySection>

                {email.human_reasons?.length > 0 && (
                  <SecuritySection id="xai" title={t('panel.xai')} isOpen={openPanels.xai} onToggle={togglePanel}>
                    <div className={styles.xaiList}>
                      {email.human_reasons.map((r, i) => (
                        <div key={i} className={styles.xaiItem}>• {r}</div>
                      ))}
                    </div>
                  </SecuritySection>
                )}

                <SecuritySection id="metadata" title={t('panel.metadata')} isOpen={openPanels.metadata} onToggle={togglePanel}>
                  <div className={styles.meta}>
                    <div className={styles.metaRow}>
                      <span className={styles.metaLabel}>{t('meta.category')}</span>
                      <span className={styles.metaValue}>{email.category || email.label || '-'}</span>
                    </div>
                    <div className={styles.metaRow}>
                      <span className={styles.metaLabel}>{t('meta.status')}</span>
                      <span className={styles.metaValue} style={{ fontWeight: 500, color: 'var(--text)' }}>
                        {email.status === 'released' ? t('email.statusReleased') : email.status === 'confirmed_spam' ? t('email.statusSpam') : email.status}
                      </span>
                    </div>
                    <div className={styles.metaRow}>
                      <span className={styles.metaLabel}>{t('meta.modelVersion')}</span>
                      <span className={styles.metaValue}>{email.model_version || 'N/A'}</span>
                    </div>
                    <div className={styles.metaRow}>
                      <span className={styles.metaLabel}>{t('meta.routingReason')}</span>
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
        title={t('dialog.deleteTitle')}
        message={
          email.status === 'trash'
            ? t('dialog.deletePermanent')
            : t('dialog.deleteTrash')
        }
        onCancel={() => setDeleteDialogOpen(false)}
        onConfirm={confirmDelete}
        busy={deleting}
      />
    </GmailShell>
  )
}
