import { useEmails } from '../api/emails'
import GmailShell from '../components/layout/GmailShell'
import EmailRow from '../components/inbox/EmailRow'
import { ShoppingBag } from 'lucide-react'
import { useState } from 'react'

export default function PembelianPage() {
  const { data, isLoading, isError } = useEmails('all')
  const [selected, setSelected] = useState(new Set())

  const emails = data?.emails || []
  const pembelianEmails = emails.filter((e) => e.label === 'pembelian' || e.category === 'pembelian')

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
          <ShoppingBag size={24} stroke="var(--text-muted)" />
          <h1 style={{ fontSize: '1.5rem', fontWeight: 500, margin: 0 }}>Pembelian</h1>
        </div>

        {isLoading && (
          <div style={{ color: 'var(--text-muted)', padding: '20px' }}>Memuat email pembelian...</div>
        )}

        {!isLoading && !isError && pembelianEmails.length === 0 && (
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
            <ShoppingBag size={48} stroke="currentColor" opacity={0.25} style={{ marginBottom: '16px' }} />
            <h3 style={{ margin: '0 0 8px 0', fontWeight: 500, color: 'var(--text)' }}>Tidak ada email pembelian</h3>
            <p style={{ margin: 0, fontSize: '0.875rem', maxWidth: '360px' }}>
              Struk dan notifikasi pembelian akan muncul di sini.
            </p>
          </div>
        )}

        {!isLoading && !isError && pembelianEmails.length > 0 && (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
            {pembelianEmails.map((email) => (
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