import GmailShell from '../components/layout/GmailShell'
import { Send } from 'lucide-react'

export default function SentPage() {
  return (
    <GmailShell>
      <div style={{ padding: '24px', fontFamily: 'Google Sans, Roboto, sans-serif' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
          <Send size={24} color="#1a73e8" />
          <h1 style={{ fontSize: '1.5rem', fontWeight: 500, margin: 0 }}>Email Terkirim</h1>
        </div>

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
          <Send size={48} stroke="currentColor" opacity={0.25} style={{ marginBottom: '16px' }} />
          <h3 style={{ margin: '0 0 8px 0', fontWeight: 500, color: 'var(--text)' }}>Tidak ada email terkirim</h3>
          <p style={{ margin: 0, fontSize: '0.875rem', maxWidth: '360px' }}>
            Kirim email simulasi menggunakan tombol <strong>Tulis</strong> di sidebar untuk melihat email Anda di sini.
          </p>
        </div>
      </div>
    </GmailShell>
  )
}
