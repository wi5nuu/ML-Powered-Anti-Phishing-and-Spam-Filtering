import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Minus, Maximize2, Minimize2, X, Trash2, Paperclip } from 'lucide-react'
import { useToast } from '../../hooks/useToast'
import api from '../../api/client'
import styles from './ComposeModal.module.css'

export default function ComposeModal({ open, onClose, fromMailbox = '', initialDraft = null }) {
  const { showToast } = useToast()
  const queryClient = useQueryClient()
  const [recipients, setRecipients] = useState([])
  const [recipientInput, setRecipientInput] = useState('')
  const [recipientError, setRecipientError] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [attachments, setAttachments] = useState([])
  const [minimized, setMinimized] = useState(false)
  const [maximized, setMaximized] = useState(false)
  const [savePromptOpen, setSavePromptOpen] = useState(false)
  const [savingDraft, setSavingDraft] = useState(false)
  const [draftId, setDraftId] = useState('')

  useEffect(() => {
    if (!open) return
    if (initialDraft) {
      setDraftId(initialDraft.draft_id || initialDraft.email_id || '')
      const parsedRecipients = parseRecipientText(initialDraft.to || '')
      setRecipients(parsedRecipients.valid)
      setRecipientInput(parsedRecipients.invalid.join(', '))
      setRecipientError(parsedRecipients.invalid.length ? 'Ada alamat email yang belum valid.' : '')
      setSubject(initialDraft.subject || '')
      setBody(initialDraft.body || '')
      setAttachments(initialDraft.attachments || [])
      setMinimized(false)
      setMaximized(false)
      setSavePromptOpen(false)
    }
  }, [open, initialDraft])

  if (!open) return null

  const hasDraftContent = Boolean(
    recipients.length > 0 || recipientInput.trim() || subject.trim() || body.trim() || attachments.length > 0
  )

  const isValidEmail = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || '').trim())

  function parseRecipientText(value) {
    const parts = String(value || '')
      .split(/[;,\s]+/)
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean)
    const valid = []
    const invalid = []
    parts.forEach((item) => {
      if (isValidEmail(item)) {
        if (!valid.includes(item)) valid.push(item)
      } else {
        invalid.push(item)
      }
    })
    return { valid, invalid }
  }

  const recipientsToString = (includeInput = false) => {
    const values = [...recipients]
    const pending = recipientInput.trim()
    if (includeInput && pending) values.push(pending)
    return values.join(', ')
  }

  const commitRecipientInput = ({ allowEmpty = true } = {}) => {
    const raw = recipientInput.trim()
    if (!raw) {
      if (allowEmpty) setRecipientError('')
      return true
    }
    const parsed = parseRecipientText(raw)
    if (parsed.invalid.length > 0 || parsed.valid.length === 0) {
      setRecipientError(`Alamat email tidak valid: ${parsed.invalid[0] || raw}`)
      return false
    }
    setRecipients((prev) => {
      const next = [...prev]
      parsed.valid.forEach((email) => {
        if (!next.includes(email)) next.push(email)
      })
      return next
    })
    setRecipientInput('')
    setRecipientError('')
    return true
  }

  const removeRecipient = (email) => {
    setRecipients((prev) => prev.filter((item) => item !== email))
  }

  const handleRecipientKeyDown = (e) => {
    if (['Enter', ',', ';', 'Tab', ' '].includes(e.key)) {
      e.preventDefault()
      commitRecipientInput()
      return
    }
    if (e.key === 'Backspace' && !recipientInput && recipients.length > 0) {
      setRecipients((prev) => prev.slice(0, -1))
    }
  }

  const handleRecipientPaste = (e) => {
    const text = e.clipboardData.getData('text')
    if (!/[;,\s]/.test(text)) return
    e.preventDefault()
    const parsed = parseRecipientText(text)
    if (parsed.invalid.length > 0) {
      setRecipientInput(parsed.invalid.join(', '))
      setRecipientError(`Alamat email tidak valid: ${parsed.invalid[0]}`)
      return
    }
    setRecipients((prev) => {
      const next = [...prev]
      parsed.valid.forEach((email) => {
        if (!next.includes(email)) next.push(email)
      })
      return next
    })
    setRecipientInput('')
    setRecipientError('')
  }

  const resetCompose = () => {
    setRecipients([])
    setRecipientInput('')
    setRecipientError('')
    setSubject('')
    setBody('')
    setAttachments([])
    setMinimized(false)
    setMaximized(false)
    setSavePromptOpen(false)
    setDraftId('')
  }

  const handleSend = async (e) => {
    e.preventDefault()
    const pending = recipientInput.trim()
    const parsedPending = parseRecipientText(pending)
    if (pending && (parsedPending.invalid.length > 0 || parsedPending.valid.length === 0)) {
      setRecipientError(`Alamat email tidak valid: ${parsedPending.invalid[0] || pending}`)
      return
    }
    const finalRecipientList = [...recipients]
    parsedPending.valid.forEach((email) => {
      if (!finalRecipientList.includes(email)) finalRecipientList.push(email)
    })
    const finalRecipients = finalRecipientList.join(', ')
    if (!finalRecipients) {
      showToast('Silakan tentukan penerima email', 'error')
      return
    }
    setRecipients(finalRecipientList)
    setRecipientInput('')
    setRecipientError('')
    
    try {
      if (attachments.length > 0) {
        const formData = new FormData()
        formData.append('to', finalRecipients)
        formData.append('from_email', fromMailbox)
        formData.append('subject', subject)
        formData.append('body', body)
        formData.append('action', 'send')
        formData.append('draft_id', draftId)
        attachments.forEach((file) => formData.append('attachments', file))
        await api.post('/emails/send', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      } else {
        await api.post('/emails/send', { to: finalRecipients, from_email: fromMailbox, subject, body, action: 'send', draft_id: draftId })
      }
      showToast(`Email berhasil dikirim ke ${finalRecipients}`, 'success')
      resetCompose()
      onClose()
      queryClient.invalidateQueries({ queryKey: ['emails'] })
    } catch (err) {
      showToast('Gagal mengirim email: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const saveDraft = async () => {
    if (!hasDraftContent || savingDraft) return
    setSavingDraft(true)
    try {
      if (attachments.length > 0) {
        const formData = new FormData()
        formData.append('to', recipientsToString(true))
        formData.append('from_email', fromMailbox)
        formData.append('subject', subject)
        formData.append('body', body)
        formData.append('draft_id', draftId)
        attachments.forEach((file) => formData.append('attachments', file))
        await api.post('/emails/draft', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      } else {
        await api.post('/emails/draft', { draft_id: draftId, to: recipientsToString(true), from_email: fromMailbox, subject, body })
      }
      showToast('Draf berhasil disimpan', 'success')
      resetCompose()
      onClose()
      queryClient.invalidateQueries({ queryKey: ['emails'] })
    } catch (err) {
      showToast('Gagal menyimpan draf: ' + (err.response?.data?.detail || err.message), 'error')
    } finally {
      setSavingDraft(false)
    }
  }

  const requestClose = () => {
    if (hasDraftContent) {
      setSavePromptOpen(true)
      return
    }
    resetCompose()
    onClose()
  }

  const handleDiscard = () => {
    resetCompose()
    onClose()
  }

  return (
    <>
    <div className={`${styles.composeOverlay} ${minimized ? styles.minimized : ''} ${maximized ? styles.maximized : ''}`}>
      {/* Header bar */}
      <div className={styles.header} onClick={() => setMinimized(!minimized)}>
        <span className={styles.title}>{subject || 'Pesan Baru'}</span>
        <div className={styles.actions} onClick={(e) => e.stopPropagation()}>
          <button 
            className={styles.actionBtn} 
            onClick={() => setMinimized(!minimized)} 
            title="Minimalkan"
          >
            <Minus size={16} />
          </button>
          <button 
            className={styles.actionBtn} 
            onClick={() => setMaximized(!maximized)} 
            title={maximized ? 'Pulihkan ukuran' : 'Maksimalkan'}
          >
            {maximized ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
          <button 
            className={styles.actionBtn} 
            onClick={requestClose}
            title="Simpan & Tutup"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Main content body */}
      {!minimized && (
        <form onSubmit={handleSend} className={styles.body}>
          <div className={styles.field}>
            <span className={styles.label}>Dari:</span>
            <input
              type="text"
              className={styles.input}
              value={fromMailbox || 'akun login'}
              readOnly
            />
          </div>
          <div className={styles.field}>
            <span className={styles.label}>Penerima:</span>
            <div className={`${styles.recipientBox} ${recipientError ? styles.recipientBoxError : ''}`}>
              {recipients.map((email) => (
                <span key={email} className={styles.recipientChip}>
                  <span className={styles.recipientAvatar}>{email[0].toUpperCase()}</span>
                  <span className={styles.recipientText}>{email}</span>
                  <button type="button" onClick={() => removeRecipient(email)} title="Hapus penerima">
                    <X size={14} />
                  </button>
                </span>
              ))}
              <input
                type="text"
                className={styles.recipientInput}
                value={recipientInput}
                onChange={(e) => { setRecipientInput(e.target.value); setRecipientError('') }}
                onKeyDown={handleRecipientKeyDown}
                onPaste={handleRecipientPaste}
                onBlur={() => commitRecipientInput()}
                placeholder={recipients.length ? '' : 'nama@contoh.com'}
                aria-invalid={Boolean(recipientError)}
              />
            </div>
          </div>
          {recipientError && <div className={styles.recipientError}>{recipientError}</div>}
          <div className={styles.field}>
            <span className={styles.label}>Subjek:</span>
            <input 
              type="text" 
              className={styles.input} 
              value={subject} 
              onChange={(e) => setSubject(e.target.value)} 
              placeholder="Subjek email"
            />
          </div>
          <textarea 
            className={styles.textarea} 
            value={body} 
            onChange={(e) => setBody(e.target.value)} 
            placeholder="Tulis pesan Anda di sini..."
          />
          {attachments.length > 0 && (
            <div className={styles.attachmentList}>
              {attachments.map((file, index) => (
                <div key={`${file.name}-${index}`} className={styles.attachmentChip}>
                  <Paperclip size={14} />
                  <span>{file.name}</span>
                  <button
                    type="button"
                    onClick={() => setAttachments((prev) => prev.filter((_, i) => i !== index))}
                    title="Hapus lampiran"
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
          
          {/* Footer controls */}
          <div className={styles.footer}>
            <button type="submit" className={styles.sendBtn}>Kirim</button>
            <div className={styles.footerActions}>
              <button
                type="button"
                className={styles.saveDraftBtn}
                onClick={saveDraft}
                disabled={!hasDraftContent || savingDraft}
              >
                {savingDraft ? 'Menyimpan...' : 'Save draft'}
              </button>
              <label className={styles.iconBtn} title="Lampirkan file">
                <Paperclip size={18} />
                <input
                  type="file"
                  multiple
                  onChange={(e) => setAttachments((prev) => [...prev, ...Array.from(e.target.files || [])])}
                />
              </label>
              <button
                type="button"
                className={styles.trashBtn}
                onClick={handleDiscard}
                title="Buang draf"
              >
                <Trash2 size={18} />
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
    {savePromptOpen && (
      <div className={styles.draftDialogOverlay} onClick={() => setSavePromptOpen(false)}>
        <div className={styles.draftDialog} onClick={(e) => e.stopPropagation()}>
          <h2>Save as draft?</h2>
          <p>
            Pesan belum dikirim dan memiliki perubahan yang belum disimpan.
            Anda ingin membuang perubahan atau menyimpannya sebagai draf?
          </p>
          <div className={styles.draftDialogActions}>
            <button type="button" className={styles.discardBtn} onClick={handleDiscard}>
              Discard
            </button>
            <button type="button" className={styles.primaryDraftBtn} onClick={saveDraft} disabled={savingDraft}>
              {savingDraft ? 'Saving...' : 'Save draft'}
            </button>
          </div>
        </div>
      </div>
    )}
    </>
  )
}
