import { useTranslation } from '../i18n/context'
import GmailShell from '../components/layout/GmailShell'
import { Clock } from 'lucide-react'

export default function SnoozedPage() {
  const { t } = useTranslation()
  return (
    <GmailShell>
      <div style={{ padding: '24px', fontFamily: 'Google Sans, Roboto, sans-serif' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
          <Clock size={24} color="#f29900" />
          <h1 style={{ fontSize: '1.5rem', fontWeight: 500, margin: 0 }}>{t('snoozed.title')}</h1>
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
          <Clock size={48} stroke="currentColor" opacity={0.25} style={{ marginBottom: '16px' }} />
          <h3 style={{ margin: '0 0 8px 0', fontWeight: 500, color: 'var(--text)' }}>{t('snoozed.empty')}</h3>
          <p style={{ margin: 0, fontSize: '0.875rem', maxWidth: '360px' }}>
            {t('snoozed.hint')}
          </p>
        </div>
      </div>
    </GmailShell>
  )
}
