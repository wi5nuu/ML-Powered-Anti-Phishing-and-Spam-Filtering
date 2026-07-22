import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Database, Download, Trash2, CheckCircle, XCircle, 
  AlertTriangle, RefreshCw, PlayCircle, FileText, Info 
} from 'lucide-react'
import api from '../api/client'
import AdminShell from '../components/layout/AdminShell'
import styles from './SuperadminTrainingPage.module.css'

export default function SuperadminTrainingPage() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('samples')
  const [filterStatus, setFilterStatus] = useState('all')
  const [selectedSample, setSelectedSample] = useState(null)
  const [retrainLoading, setRetrainLoading] = useState(false)

  // Fetch training stats
  const { data: stats } = useQuery({
    queryKey: ['training-stats'],
    queryFn: async () => {
      const { data } = await api.get('/admin/training/stats')
      return data
    },
    staleTime: 30000,
  })

  // Fetch training samples
  const { data: samplesData, isLoading } = useQuery({
    queryKey: ['training-samples', filterStatus],
    queryFn: async () => {
      const params = filterStatus !== 'all' ? { status: filterStatus } : {}
      const { data } = await api.get('/admin/training-samples', { params })
      return data
    },
    staleTime: 10000,
  })

  // Update sample mutation
  const updateSampleMutation = useMutation({
    mutationFn: async ({ id, updates }) => {
      const { data } = await api.put(`/admin/training-samples/${id}`, updates)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['training-samples'])
      queryClient.invalidateQueries(['training-stats'])
      setSelectedSample(null)
    },
  })

  // Delete sample mutation
  const deleteSampleMutation = useMutation({
    mutationFn: async (id) => {
      await api.delete(`/admin/training-samples/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['training-samples'])
      queryClient.invalidateQueries(['training-stats'])
      setSelectedSample(null)
    },
  })

  // Export dataset
  const handleExport = async (status) => {
    try {
      const response = await api.post(`/admin/training/export-dataset?status=${status}`, {}, {
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `training_samples_${status}_${new Date().toISOString().split('T')[0]}.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (error) {
      alert('Export failed: ' + (error.response?.data?.detail || error.message))
    }
  }

  // Trigger retrain
  const handleRetrain = async () => {
    if (!confirm(`Trigger retraining with ${stats?.by_status?.approved || 0} approved samples?`)) return
    
    setRetrainLoading(true)
    try {
      const { data } = await api.post('/admin/training/retrain')
      alert(data.message || 'Retraining triggered successfully')
      queryClient.invalidateQueries(['training-samples'])
      queryClient.invalidateQueries(['training-stats'])
    } catch (error) {
      alert('Retrain failed: ' + (error.response?.data?.detail || error.message))
    } finally {
      setRetrainLoading(false)
    }
  }

  const samples = samplesData?.samples || []

  return (
    <AdminShell>
      <div className={styles.wrap}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <Database size={24} />
            <div>
              <h1 className={styles.title}>ML Training & Dataset</h1>
              <p className={styles.subtitle}>Manage false negative reports and retrain models</p>
            </div>
          </div>
          <div className={styles.headerActions}>
            <button
              className={styles.btnSecondary}
              onClick={() => handleExport('approved')}
              disabled={!stats?.by_status?.approved}
            >
              <Download size={16} />
              Export Approved
            </button>
            <button
              className={styles.btnPrimary}
              onClick={handleRetrain}
              disabled={retrainLoading || !stats?.by_status?.approved}
            >
              <PlayCircle size={16} />
              {retrainLoading ? 'Triggering...' : 'Trigger Retrain'}
            </button>
          </div>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className={styles.statsGrid}>
            <div className={styles.statCard}>
              <div className={styles.statIcon} style={{ backgroundColor: '#e8f5e9' }}>
                <CheckCircle size={20} color="#4caf50" />
              </div>
              <div className={styles.statContent}>
                <div className={styles.statValue}>{stats.by_status.approved}</div>
                <div className={styles.statLabel}>Approved</div>
              </div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statIcon} style={{ backgroundColor: '#fff3e0' }}>
                <AlertTriangle size={20} color="#ff9800" />
              </div>
              <div className={styles.statContent}>
                <div className={styles.statValue}>{stats.by_status.pending}</div>
                <div className={styles.statLabel}>Pending Review</div>
              </div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statIcon} style={{ backgroundColor: '#fce4ec' }}>
                <XCircle size={20} color="#e91e63" />
              </div>
              <div className={styles.statContent}>
                <div className={styles.statValue}>{stats.by_status.rejected}</div>
                <div className={styles.statLabel}>Rejected</div>
              </div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statIcon} style={{ backgroundColor: '#e3f2fd' }}>
                <Database size={20} color="#2196f3" />
              </div>
              <div className={styles.statContent}>
                <div className={styles.statValue}>{stats.by_status.used_in_training}</div>
                <div className={styles.statLabel}>Used in Training</div>
              </div>
            </div>
          </div>
        )}

        {/* Filter Tabs */}
        <div className={styles.filterTabs}>
          {['all', 'pending', 'approved', 'rejected', 'used_in_training'].map(status => (
            <button
              key={status}
              className={`${styles.filterTab} ${filterStatus === status ? styles.filterTabActive : ''}`}
              onClick={() => setFilterStatus(status)}
            >
              {status.replace('_', ' ')}
            </button>
          ))}
        </div>

        {/* Samples Table */}
        <div className={styles.tableWrap}>
          {isLoading ? (
            <div className={styles.loading}>Loading samples...</div>
          ) : samples.length === 0 ? (
            <div className={styles.empty}>
              <Info size={48} color="#9e9e9e" />
              <p>No training samples found</p>
            </div>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Email ID</th>
                  <th>Subject</th>
                  <th>Sender</th>
                  <th>Original Label</th>
                  <th>Corrected Label</th>
                  <th>Reported By</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {samples.map(sample => (
                  <tr key={sample.id}>
                    <td><code>{sample.email_id.substring(0, 12)}...</code></td>
                    <td className={styles.subject}>{sample.subject || '(no subject)'}</td>
                    <td>{sample.sender}</td>
                    <td>
                      <span className={`${styles.badge} ${styles['badge' + sample.original_label]}`}>
                        {sample.original_label}
                      </span>
                    </td>
                    <td>
                      <span className={`${styles.badge} ${styles.badgeDanger}`}>
                        {sample.corrected_label}
                      </span>
                    </td>
                    <td>{sample.reported_by}</td>
                    <td>
                      <span className={`${styles.badge} ${styles['badgeStatus' + sample.status]}`}>
                        {sample.status}
                      </span>
                    </td>
                    <td>{new Date(sample.created_at).toLocaleDateString()}</td>
                    <td>
                      <div className={styles.actions}>
                        <button
                          className={styles.btnIcon}
                          onClick={() => setSelectedSample(sample)}
                          title="View Details"
                        >
                          <FileText size={16} />
                        </button>
                        {sample.status === 'pending' && (
                          <>
                            <button
                              className={styles.btnIcon}
                              onClick={() => updateSampleMutation.mutate({ 
                                id: sample.id, 
                                updates: { status: 'approved' } 
                              })}
                              title="Approve"
                            >
                              <CheckCircle size={16} color="#4caf50" />
                            </button>
                            <button
                              className={styles.btnIcon}
                              onClick={() => updateSampleMutation.mutate({ 
                                id: sample.id, 
                                updates: { status: 'rejected' } 
                              })}
                              title="Reject"
                            >
                              <XCircle size={16} color="#f44336" />
                            </button>
                          </>
                        )}
                        <button
                          className={styles.btnIcon}
                          onClick={() => {
                            if (confirm('Delete this training sample?')) {
                              deleteSampleMutation.mutate(sample.id)
                            }
                          }}
                          title="Delete"
                        >
                          <Trash2 size={16} color="#f44336" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Sample Detail Modal */}
        {selectedSample && (
          <div className={styles.modal} onClick={() => setSelectedSample(null)}>
            <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <h2>Training Sample Details</h2>
                <button onClick={() => setSelectedSample(null)}>&times;</button>
              </div>
              <div className={styles.modalBody}>
                <div className={styles.detailRow}>
                  <strong>Email ID:</strong> <code>{selectedSample.email_id}</code>
                </div>
                <div className={styles.detailRow}>
                  <strong>Subject:</strong> {selectedSample.subject}
                </div>
                <div className={styles.detailRow}>
                  <strong>Sender:</strong> {selectedSample.sender}
                </div>
                <div className={styles.detailRow}>
                  <strong>Original Label:</strong>
                  <span className={`${styles.badge} ${styles['badge' + selectedSample.original_label]}`}>
                    {selectedSample.original_label}
                  </span>
                </div>
                <div className={styles.detailRow}>
                  <strong>Corrected Label:</strong>
                  <span className={`${styles.badge} ${styles.badgeDanger}`}>
                    {selectedSample.corrected_label}
                  </span>
                </div>
                <div className={styles.detailRow}>
                  <strong>Original Scores:</strong>
                  <pre>{JSON.stringify(selectedSample.original_scores, null, 2)}</pre>
                </div>
                <div className={styles.detailRow}>
                  <strong>Notes:</strong> {selectedSample.notes || '(none)'}
                </div>
                <div className={styles.detailRow}>
                  <strong>Reported By:</strong> {selectedSample.reported_by}
                </div>
                <div className={styles.detailRow}>
                  <strong>Reviewed By:</strong> {selectedSample.reviewed_by || '(not reviewed)'}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </AdminShell>
  )
}
