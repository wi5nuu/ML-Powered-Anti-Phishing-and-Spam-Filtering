import { useEmails } from '../api/emails'
import GmailShell from '../components/layout/GmailShell'
import EmailRow from '../components/inbox/EmailRow'
import { FileText } from 'lucide-react'
import { useState } from 'react'

export default function DraftPage() {
  const { data, isLoading, isError } = useEmails('draft')
  const [selected, setSelected] = useState(new Set())

  const emails = data?.emails || []
  const draftEmails = emails.filter((e) => e.label === 'DRAFT' || e.status === 'draft')

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
          <FileText size={24} stroke="var(--text-muted)" />
          <h1 style={{ fontSize: '1.5rem', fontWeight: 500, margin: 0 }}>Draf</h1>
        </div>

        {isLoading && (
          <div style={{ color: 'var(--text-muted)', padding: '20px' }}>Memuat draf...</div>
        )}

        {!isLoading && !isError && draftEmails.length === 0 && (
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
            <FileText size={48} stroke="currentColor" opacity={0.25} style={{ marginBottom: '16px' }} />
            <h3 style={{ margin: '0 0 8px 0', fontWeight: 500, color: 'var(--text)' }}>Tidak ada draf</h3>
            <p style={{ margin: 0, fontSize: '0.875rem', maxWidth: '360px' }}>
              Draf email yang belum terkirim akan muncul di sini.
            </p>
          </div>
        )}

        {!isLoading && !isError && draftEmails.length > 0 && (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
            {draftEmails.map((email) => (
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
