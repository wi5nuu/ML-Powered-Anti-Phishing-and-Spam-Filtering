import { useEmails } from '../api/emails'
import GmailShell from '../components/layout/GmailShell'
import { useTranslation } from '../i18n/context'
import EmailRow from '../components/inbox/EmailRow'
import { Star } from 'lucide-react'
import { useState, useEffect } from 'react'

// Starred state is kept in localStorage since the backend has no is_starred field
const STARRED_KEY = 'cognimail_starred_ids'

function getStarredIds() {
  try { return new Set(JSON.parse(localStorage.getItem(STARRED_KEY) || '[]')) }
  catch { return new Set() }
}

export function toggleStarred(emailId) {
  const ids = getStarredIds()
  ids.has(emailId) ? ids.delete(emailId) : ids.add(emailId)
  localStorage.setItem(STARRED_KEY, JSON.stringify([...ids]))
  window.dispatchEvent(new Event('cognimail_starred_changed'))
}

export function isStarred(emailId) {
  return getStarredIds().has(emailId)
}

export default function StarredPage() {
  const { t } = useTranslation()
  const { data, isLoading, isError } = useEmails('all')
  const [selected, setSelected] = useState(new Set())
  const [starredIds, setStarredIds] = useState(getStarredIds)

  useEffect(() => {
    const handler = () => setStarredIds(getStarredIds())
    window.addEventListener('cognimail_starred_changed', handler)
    return () => window.removeEventListener('cognimail_starred_changed', handler)
  }, [])

  const emails = data?.emails || []
  const starredEmails = emails.filter((e) => starredIds.has(e.email_id))

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <GmailShell>
      <div style={{ padding: '24px', fontFamily: 'Google Sans, Roboto, sans-serif' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
          <Star size={24} fill="#f29900" stroke="#f29900" />
          <h1 style={{ fontSize: '1.5rem', fontWeight: 500, margin: 0 }}>{t('gmail.starred')}</h1>
        </div>

        {isLoading && (
          <div style={{ color: 'var(--text-muted)', padding: '20px' }}>{t('gmail.loading')}</div>
        )}

        {!isLoading && !isError && starredEmails.length === 0 && (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '80px 20px',
            color: 'var(--text-muted)',
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <Star size={48} stroke="currentColor" opacity={0.25} style={{ marginBottom: '16px' }} />
            <h3 style={{ margin: '0 0 8px 0', fontWeight: 500, color: 'var(--text)' }}>{t('gmail.noMails')}</h3>
            <p style={{ margin: 0, fontSize: '0.875rem', maxWidth: '360px' }}>
              Bintangi email penting untuk menemukannya dengan mudah di sini nanti.
            </p>
          </div>
        )}

        {!isLoading && !isError && starredEmails.length > 0 && (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
            {starredEmails.map((email) => (
              <EmailRow
                key={email.email_id}
                email={email}
                isSelected={selected.has(email.email_id)}
                onToggleSelect={() => toggleSelect(email.email_id)}
              />
            ))}
          </div>
        )}
      </div>
    </GmailShell>
  )
}
