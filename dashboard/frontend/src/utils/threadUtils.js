/**
 * threadUtils.js — CogniMail Thread & Draft Deduplication Utilities
 *
 * Provides helper functions to:
 *  1. Normalize email subjects (strip Re:/Fwd: prefixes)
 *  2. Compute stable thread keys for grouping conversations
 *  3. Compute draft keys for preventing duplicate drafts
 *  4. Deduplicate drafts (keep newest per thread+mode)
 *  5. Group emails into conversation threads
 */

// ─────────────────────────────────────────────────────────────────────────────
// 1. normalizeSubject
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Strip repeated Re:/Fwd: prefixes and return a lowercase base subject.
 * Used for comparison only — do NOT display this value directly.
 *
 * Examples:
 *   "Re: Re: Konfirmasi pembayaran" → "konfirmasi pembayaran"
 *   "FWD: Fwd: Hello World"        → "hello world"
 *   "Konfirmasi pembayaran"         → "konfirmasi pembayaran"
 *
 * @param {string} subject
 * @returns {string} normalized base subject (lowercase, trimmed)
 */
export function normalizeSubject(subject) {
  let value = String(subject || '').trim()
  // Strip repeated prefixes: Re:, RE:, Fwd:, FW:, Fw:, and combinations
  while (/^(re|fw|fwd)\s*:\s*/i.test(value)) {
    value = value.replace(/^(re|fw|fwd)\s*:\s*/i, '').trim()
  }
  return value.toLowerCase()
}

/**
 * Return a display-friendly version of a subject (strips prefixes but preserves case).
 * @param {string} subject
 * @returns {string}
 */
export function displaySubject(subject) {
  let value = String(subject || '').trim()
  while (/^(re|fw|fwd)\s*:\s*/i.test(value)) {
    value = value.replace(/^(re|fw|fwd)\s*:\s*/i, '').trim()
  }
  return value || subject || '(tanpa subjek)'
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. getThreadKey
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Compute a stable thread grouping key for an email/draft.
 *
 * Priority:
 *  1. thread_id  (explicit thread identifier from server)
 *  2. parent_email_id / original_email_id  (reply chain)
 *  3. Fallback: normalizedSubject + sorted participants
 *
 * @param {object} email   - email or draft object from the API
 * @param {string} mailboxId - current mailbox identifier
 * @returns {string}
 */
export function getThreadKey(email, mailboxId = '') {
  if (!email) return ''

  const mbx = String(mailboxId || '').toLowerCase()

  // Priority 1: explicit thread_id
  if (email.thread_id) {
    return `${mbx}::thread::${String(email.thread_id)}`
  }

  // Priority 2: parent chain identifiers
  const parentId = email.parent_email_id || email.original_email_id || ''
  if (parentId) {
    return `${mbx}::parent::${String(parentId)}`
  }

  // Priority 3: subject + participants fallback
  const normalSubject = normalizeSubject(email.subject || '')

  // Collect all participants and sort for stable key
  const rawParticipants = [
    email.sender || email.sender_email || '',
    ...(Array.isArray(email.recipient_list)
      ? email.recipient_list
      : String(email.recipient_list || '').split(',').map((s) => s.trim())),
  ]
    .map((s) => s.toLowerCase().trim())
    .filter(Boolean)
    .sort()

  const participantKey = rawParticipants.join('|')
  return `${mbx}::subject::${normalSubject}::${participantKey}`
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. getDraftKey
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Compute a uniqueness key for a draft to prevent duplicates.
 *
 * Key format: mailboxId + threadKey + compose_mode
 *
 * @param {object} draft
 * @param {string} mailboxId
 * @returns {string}
 */
export function getDraftKey(draft, mailboxId = '') {
  if (!draft) return ''
  const mbx = String(mailboxId || '').toLowerCase()
  const mode = String(draft.compose_mode || draft.composeMode || 'new').toLowerCase()
  const threadKey = getThreadKey(draft, mbx)
  return `${threadKey}::mode::${mode}`
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. dedupeDrafts
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Deduplicate a list of drafts so that only the newest draft per
 * (mailbox + thread + compose_mode) combination is kept.
 *
 * @param {object[]} drafts   - array of draft objects
 * @param {string}   mailboxId
 * @returns {object[]} deduplicated drafts, sorted newest first
 */
export function dedupeDrafts(drafts = [], mailboxId = '') {
  if (!drafts.length) return []

  // Sort newest first (by updated_at → received_at → timestamp)
  const sorted = [...drafts].sort((a, b) => {
    const aTime = new Date(a.updated_at || a.received_at || a.timestamp || 0).getTime()
    const bTime = new Date(b.updated_at || b.received_at || b.timestamp || 0).getTime()
    return (isNaN(bTime) ? 0 : bTime) - (isNaN(aTime) ? 0 : aTime)
  })

  // Keep only the first (newest) per draft key
  const seen = new Map()
  for (const draft of sorted) {
    const key = getDraftKey(draft, mailboxId)
    if (!seen.has(key)) {
      seen.set(key, {
        ...draft,
        // Attach convenience metadata
        _threadKey: getThreadKey(draft, mailboxId),
        _draftKey: key,
        _isReplyDraft: Boolean(
          draft.parent_email_id ||
          draft.original_email_id ||
          draft.thread_id ||
          String(draft.compose_mode || '').toLowerCase() === 'reply' ||
          /^re\s*:/i.test(String(draft.subject || ''))
        ),
      })
    }
  }

  return Array.from(seen.values())
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. groupEmailsIntoThreads
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Group a flat list of emails into conversation threads, Gmail-style.
 *
 * Each group contains:
 *  - All messages in the thread sorted oldest → newest
 *  - A `threadKey` for identification
 *  - `messageCount` (number of messages in thread)
 *  - `latestMessage` (most recent message object)
 *  - `senders` (de-duped list of unique senders)
 *  - `hasDraft` flag if any message is a draft
 *  - `activeDraft` (the newest draft in this thread, if any)
 *
 * The returned array contains one entry per thread, sorted by the latest
 * message timestamp (newest thread first).
 *
 * @param {object[]} emails     - flat list of email/draft objects
 * @param {string}   mailboxId
 * @returns {object[]} array of thread group objects
 */
export function groupEmailsIntoThreads(emails = [], mailboxId = '') {
  if (!emails.length) return []

  const threadMap = new Map()

  for (const email of emails) {
    const key = getThreadKey(email, mailboxId)
    if (!threadMap.has(key)) {
      threadMap.set(key, [])
    }
    threadMap.get(key).push(email)
  }

  const threads = []

  for (const [key, messages] of threadMap.entries()) {
    // Sort messages oldest first within a thread
    const sorted = [...messages].sort((a, b) => {
      const aTime = new Date(a.received_at || a.timestamp || 0).getTime()
      const bTime = new Date(b.received_at || b.timestamp || 0).getTime()
      return (isNaN(aTime) ? 0 : aTime) - (isNaN(bTime) ? 0 : bTime)
    })

    const drafts = sorted.filter(
      (m) => (m.label || '').toUpperCase() === 'DRAFT' || m.status === 'draft'
    )
    const nonDrafts = sorted.filter(
      (m) => (m.label || '').toUpperCase() !== 'DRAFT' && m.status !== 'draft'
    )

    // Latest non-draft message, or latest draft if thread is all-drafts
    const latestMessage = nonDrafts[nonDrafts.length - 1] || sorted[sorted.length - 1]

    // For the activeDraft: pick newest draft in thread
    const activeDraft = drafts.length
      ? drafts.sort((a, b) => {
          const aTime = new Date(a.updated_at || a.received_at || a.timestamp || 0).getTime()
          const bTime = new Date(b.updated_at || b.received_at || b.timestamp || 0).getTime()
          return (isNaN(bTime) ? 0 : bTime) - (isNaN(aTime) ? 0 : aTime)
        })[0]
      : null

    // Unique senders (display order: order they appeared)
    const senders = []
    const seenSenders = new Set()
    for (const msg of sorted) {
      const s = (msg.sender || msg.sender_email || '').toLowerCase()
      if (s && !seenSenders.has(s)) {
        seenSenders.add(s)
        senders.push(msg.sender || msg.sender_email || '')
      }
    }

    threads.push({
      threadKey: key,
      messages: sorted,
      messageCount: sorted.length,
      nonDraftCount: nonDrafts.length,
      latestMessage,
      senders,
      hasDraft: drafts.length > 0,
      activeDraft,
      // Convenience fields pulled from latestMessage for EmailRow compatibility
      email_id: latestMessage.email_id,
      subject: latestMessage.subject,
      sender: senders[senders.length - 1] || latestMessage.sender || '',
      received_at: latestMessage.received_at || latestMessage.timestamp,
      timestamp: latestMessage.received_at || latestMessage.timestamp,
      body_preview: latestMessage.body_preview || latestMessage.body_text?.slice(0, 120) || '',
      label: latestMessage.label,
      status: latestMessage.status,
      category: latestMessage.category,
      is_read: sorted.every((m) => m.is_read),
      has_attachments: sorted.some((m) => m.has_attachments),
      // Used by EmailRow for batch-delete
      thread_email_ids: sorted.map((m) => m.email_id),
      _isThread: true,
    })
  }

  // Sort threads by latest message, newest first
  threads.sort((a, b) => {
    const aTime = new Date(a.received_at || 0).getTime()
    const bTime = new Date(b.received_at || 0).getTime()
    return (isNaN(bTime) ? 0 : bTime) - (isNaN(aTime) ? 0 : aTime)
  })

  return threads
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. findExistingDraft  (helper for ComposeModal / EmailDetailPage)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Given a list of all drafts, find the one that matches the given key.
 *
 * @param {object[]} allDrafts
 * @param {object}   params    - { mailboxId, threadId, parentEmailId, subject, composeMode }
 * @returns {object|null}
 */
export function findExistingDraft(allDrafts = [], params = {}) {
  const { mailboxId = '', threadId, parentEmailId, subject, composeMode = 'new' } = params

  // Build a synthetic draft object to get the key
  const syntheticDraft = {
    thread_id: threadId || '',
    parent_email_id: parentEmailId || '',
    subject: subject || '',
    compose_mode: composeMode,
  }
  const targetKey = getDraftKey(syntheticDraft, mailboxId)

  // Sort newest first and find first match
  const sorted = [...allDrafts].sort((a, b) => {
    const aTime = new Date(a.updated_at || a.received_at || 0).getTime()
    const bTime = new Date(b.updated_at || b.received_at || 0).getTime()
    return (isNaN(bTime) ? 0 : bTime) - (isNaN(aTime) ? 0 : aTime)
  })

  return sorted.find((draft) => getDraftKey(draft, mailboxId) === targetKey) || null
}
