import { useState, useEffect } from 'react'
import api from '../../../api/client'
import SectionCard from '../../../components/ui/SectionCard'
import DataTable from '../../../components/ui/DataTable'
import { Activity } from 'lucide-react'

export default function ActivityLog() {
  const [logs, setLogs] = useState([])

  useEffect(() => {
    api.get('/admin/audit-logs').then((r) => setLogs(r.data)).catch(() => {})
  }, [])

  const columns = [
    { key: 'user', label: 'User' },
    {
      key: 'action', label: 'Aksi',
      render: (row) => <code style={{ padding: '2px 6px', background: 'var(--border-light)', borderRadius: 3, fontSize: '0.75rem', fontFamily: 'monospace' }}>{row.action}</code>
    },
    { key: 'email_id', label: 'Email ID', render: (row) => <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--text-muted)' }}>{row.email_id || '-'}</span> },
    { key: 'details', label: 'Detail', render: (row) => <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>{row.details || '-'}</span> },
    { key: 'created_at', label: 'Waktu', render: (row) => <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--text-muted)' }}>{row.created_at?.split('.')[0]}</span> },
  ]

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1400, width: '100%', margin: '0 auto', boxSizing: 'border-box' }}>
      <SectionCard icon={<Activity size={16} />} title="Activity Log">
        <DataTable columns={columns} rows={logs} emptyMessage="No activity logs." />
      </SectionCard>
    </div>
  )
}
