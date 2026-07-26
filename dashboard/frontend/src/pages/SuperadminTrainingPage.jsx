import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Database, Download, Trash2, CheckCircle, XCircle, 
  AlertTriangle, RefreshCw, PlayCircle, FileText, Info, ArrowRight
} from 'lucide-react'
import api from '../api/client'
import AdminShell from '../components/layout/AdminShell'
import ConfirmDialog from '../components/common/ConfirmDialog'
import { useToast } from '../hooks/useToast'
import styles from './SuperadminTrainingPage.module.css'

export default function SuperadminTrainingPage() {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [filterStatus, setFilterStatus] = useState('all')
  const [page, setPage] = useState(1)
  const [selectedSample, setSelectedSample] = useState(null)
  const [retrainLoading, setRetrainLoading] = useState(false)
  const [confirmation, setConfirmation] = useState(null)

  // Fetch training stats
  const { data: stats, isError: statsError } = useQuery({
    queryKey: ['training-stats'],
    queryFn: async () => {
      const { data } = await api.get('/admin/training/stats')
      return data
    },
    staleTime: 30000,
  })

  // Fetch training samples
  const { data: samplesData, isLoading, isError: samplesError } = useQuery({
    queryKey: ['training-samples', filterStatus, page],
    queryFn: async () => {
      const params = { page, page_size: 25 }
      if (filterStatus !== 'all') params.status = filterStatus
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
      queryClient.invalidateQueries({ queryKey: ['training-samples'] })
      queryClient.invalidateQueries({ queryKey: ['training-stats'] })
      setSelectedSample(null)
      showToast('Status sampel pelatihan berhasil diperbarui', 'success')
    },
    onError: (error) => showToast(error.response?.data?.detail || 'Gagal memperbarui sampel pelatihan', 'error'),
  })

  // Delete sample mutation
  const deleteSampleMutation = useMutation({
    mutationFn: async (id) => {
      await api.delete(`/admin/training-samples/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['training-samples'] })
      queryClient.invalidateQueries({ queryKey: ['training-stats'] })
      setSelectedSample(null)
      showToast('Sampel pelatihan berhasil dihapus', 'success')
    },
    onError: (error) => showToast(error.response?.data?.detail || 'Gagal menghapus sampel pelatihan', 'error'),
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
      window.URL.revokeObjectURL(url)
      showToast(`Dataset ${status} berhasil diekspor`, 'success')
    } catch (error) {
      showToast(error.response?.data?.detail || 'Tidak ada sampel approved yang dapat diekspor', 'error')
    }
  }

  // Trigger retrain
  const handleRetrain = async () => {
    setRetrainLoading(true)
    try {
      const { data } = await api.post('/admin/training/retrain')
      showToast(data.message || 'Retraining berhasil dimulai', 'success')
      queryClient.invalidateQueries({ queryKey: ['training-samples'] })
      queryClient.invalidateQueries({ queryKey: ['training-stats'] })
    } catch (error) {
      showToast(error.response?.data?.detail || 'Retraining gagal dijalankan', 'error')
    } finally {
      setRetrainLoading(false)
    }
  }

  const confirmRetrain = () => setConfirmation({
    title: 'Mulai pelatihan ulang model',
    message: `Pelatihan akan menggunakan ${stats?.by_status?.approved || 0} sampel yang telah disetujui. Lanjutkan?`,
    confirmLabel: 'Mulai Pelatihan',
    onConfirm: () => { setConfirmation(null); handleRetrain() },
  })

  const confirmDelete = (sample) => setConfirmation({
    title: 'Hapus sampel pelatihan',
    message: `Sampel ${sample.email_id} akan dihapus permanen dari dataset.`,
    confirmLabel: 'Hapus',
    cancelLabel: 'Batal',
    danger: true,
    onConfirm: () => { setConfirmation(null); deleteSampleMutation.mutate(sample.id) },
  })

  const confirmReview = (sample, status) => setConfirmation({
    title: status === 'approved' ? 'Setujui koreksi dataset' : 'Tolak koreksi dataset',
    message: status === 'approved'
      ? `Koreksi ${sample.feedback_type === 'false_positive' ? 'False Positive' : 'False Negative'} ini akan tersedia untuk dataset pelatihan.`
      : 'Sampel ini akan ditandai ditolak dan tidak digunakan untuk pelatihan model.',
    detail: `${sample.subject || '(tanpa subjek)'} → ${sample.corrected_label}`,
    confirmLabel: status === 'approved' ? 'Setujui' : 'Tolak',
    danger: status === 'rejected',
    onConfirm: () => {
      setConfirmation(null)
      updateSampleMutation.mutate({ id: sample.id, updates: { status } })
    },
  })

  const refreshTrainingData = () => {
    queryClient.invalidateQueries({ queryKey: ['training-samples'] })
    queryClient.invalidateQueries({ queryKey: ['training-stats'] })
    showToast('Data pelatihan diperbarui dari database', 'info')
  }

  const samples = samplesData?.samples || []
  const totalPages = Math.max(1, Math.ceil((samplesData?.total || 0) / 25))
  const loadError = statsError || samplesError
  const retrainingConfigured = Boolean(stats?.retraining?.configured)
  const filterLabels = {
    all: 'Semua',
    pending: 'Menunggu Review',
    approved: 'Disetujui',
    rejected: 'Ditolak',
    used_in_training: 'Sudah Dilatih',
  }

  return (
    <AdminShell>
      <div className={styles.wrap}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <Database size={24} />
            <div>
              <h1 className={styles.title}>Pelatihan ML & Dataset</h1>
              <p className={styles.subtitle}>Tinjau koreksi False Positive dan False Negative sebelum menjadi dataset model.</p>
            </div>
          </div>
          <div className={styles.headerActions}>
            <button className={styles.btnSecondary} onClick={refreshTrainingData}>
              <RefreshCw size={16} />
              Refresh
            </button>
            <button
              className={styles.btnSecondary}
              onClick={() => handleExport('approved')}
              disabled={!stats?.by_status?.approved}
            >
              <Download size={16} />
              Ekspor yang Disetujui
            </button>
          </div>
        </div>

        {loadError && (
          <div style={{ marginBottom: 16, padding: '10px 14px', borderRadius: 8, color: '#b42318', background: '#fef3f2', border: '1px solid #fecdca' }}>
            Data pelatihan gagal dimuat dari database. Tekan Refresh untuk mencoba kembali.
          </div>
        )}

        <div className={styles.flowNotice}>
          <Info size={18} />
          <span>
            Koreksi dari Panel Deteksi masuk sebagai <strong>Pending Review</strong>.
            False Positive mengoreksi email menjadi aman; False Negative mengoreksi email menjadi ancaman.
            Sampel tidak digunakan model sebelum disetujui dan proses training nyata dijalankan.
          </span>
        </div>

        <section className={styles.trainingControl} aria-labelledby="training-control-title">
          <div className={styles.trainingControlInfo}>
            <div className={styles.trainingControlHeading}>
              <span className={styles.trainingControlIcon}><PlayCircle size={20} /></span>
              <div>
                <h2 id="training-control-title">Pelatihan Model</h2>
                <span className={`${styles.capabilityBadge} ${retrainingConfigured ? styles.capabilityReady : styles.capabilityUnavailable}`}>
                  {retrainingConfigured ? 'Siap' : 'Belum dikonfigurasi'}
                </span>
              </div>
            </div>
            <p>
              Pelatihan hanya menggunakan sampel yang sudah disetujui.
              Saat ini tersedia <strong>{stats?.by_status?.approved || 0} sampel approved</strong> dari database.
            </p>
            {!retrainingConfigured && (
              <span className={styles.trainingReason}>
                <AlertTriangle size={15} />
                {stats?.retraining?.message || 'Training worker belum dikonfigurasi.'}
              </span>
            )}
          </div>
          <button
            className={styles.startTrainingBtn}
            onClick={confirmRetrain}
            disabled={retrainLoading || !stats?.by_status?.approved || !retrainingConfigured}
            title={
              !retrainingConfigured
                ? stats?.retraining?.message
                : !stats?.by_status?.approved
                  ? 'Setujui minimal satu sampel sebelum memulai training'
                  : 'Mulai pelatihan model'
            }
          >
            <PlayCircle size={18} />
            {retrainLoading ? 'Memulai Training...' : 'Mulai Training'}
          </button>
        </section>

        {/* Stats Cards */}
        {stats && (
          <div className={styles.statsGrid}>
            <div className={styles.statCard}>
              <div className={styles.statIcon} style={{ backgroundColor: '#e8f5e9' }}>
                <CheckCircle size={20} color="#4caf50" />
              </div>
              <div className={styles.statContent}>
                <div className={styles.statValue}>{stats.by_status.approved}</div>
                <div className={styles.statLabel}>Disetujui</div>
              </div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statIcon} style={{ backgroundColor: '#fff3e0' }}>
                <AlertTriangle size={20} color="#ff9800" />
              </div>
              <div className={styles.statContent}>
                <div className={styles.statValue}>{stats.by_status.pending}</div>
                <div className={styles.statLabel}>Menunggu Review</div>
              </div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statIcon} style={{ backgroundColor: '#fce4ec' }}>
                <XCircle size={20} color="#e91e63" />
              </div>
              <div className={styles.statContent}>
                <div className={styles.statValue}>{stats.by_status.rejected}</div>
                <div className={styles.statLabel}>Ditolak</div>
              </div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statIcon} style={{ backgroundColor: '#e3f2fd' }}>
                <Database size={20} color="#2196f3" />
              </div>
              <div className={styles.statContent}>
                <div className={styles.statValue}>{stats.by_status.used_in_training}</div>
                <div className={styles.statLabel}>Sudah Digunakan Training</div>
              </div>
            </div>
          </div>
        )}

        {stats && (
          <div className={styles.feedbackSummary}>
            <span><strong>{stats.by_feedback_type.false_positive}</strong> False Positive (koreksi menjadi aman)</span>
            <span><strong>{stats.by_feedback_type.false_negative}</strong> False Negative (koreksi menjadi ancaman)</span>
          </div>
        )}

        {/* Filter Tabs */}
        <div className={styles.filterTabs}>
          {['all', 'pending', 'approved', 'rejected', 'used_in_training'].map(status => (
            <button
              key={status}
              className={`${styles.filterTab} ${filterStatus === status ? styles.filterTabActive : ''}`}
              onClick={() => { setFilterStatus(status); setPage(1) }}
            >
              {filterLabels[status]}
            </button>
          ))}
        </div>

        <div className={styles.actionLegend} aria-label="Keterangan ikon tindakan">
          <span className={styles.actionLegendTitle}>Keterangan tindakan:</span>
          <span><FileText size={15} aria-hidden="true" /> Lihat detail</span>
          <span><CheckCircle size={15} aria-hidden="true" /> Setujui koreksi</span>
          <span><XCircle size={15} aria-hidden="true" /> Tolak koreksi</span>
          <span><Trash2 size={15} aria-hidden="true" /> Hapus sampel</span>
        </div>

        {/* Samples Table */}
        <div className={styles.tableWrap}>
          {isLoading ? (
            <div className={styles.loading}>Memuat sampel dari database...</div>
          ) : samples.length === 0 ? (
            <div className={styles.empty}>
              <Info size={48} color="#9e9e9e" />
              <p>Belum ada sampel pada filter ini</p>
              <span>
                Sampel hanya dibuat dari koreksi nyata melalui Panel Deteksi Keamanan.
                Gunakan False Positive jika email sebenarnya aman atau False Negative jika email sebenarnya berbahaya.
              </span>
            </div>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Perubahan Klasifikasi</th>
                  <th>Jenis Koreksi</th>
                  <th>Dilaporkan Oleh</th>
                  <th>Status</th>
                  <th>Dibuat</th>
                  <th className={styles.stickyAction}>Tindakan</th>
                </tr>
              </thead>
              <tbody>
                {samples.map(sample => (
                  <tr key={sample.id}>
                    <td className={styles.emailCell}>
                      <strong title={sample.subject}>{sample.subject || '(tanpa subjek)'}</strong>
                      <span title={sample.sender}>{sample.sender || '-'}</span>
                      <code title={sample.email_id}>{sample.email_id.substring(0, 18)}...</code>
                    </td>
                    <td>
                      <div className={styles.classificationChange}>
                        <span className={`${styles.badge} ${styles['badge' + sample.original_label]}`}>
                          {sample.original_label}
                        </span>
                        <ArrowRight size={15} aria-hidden="true" />
                        <span className={`${styles.badge} ${sample.corrected_label === 'clean' ? styles.badgeSafe : styles.badgeDanger}`}>
                          {sample.corrected_label}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className={`${styles.badge} ${sample.feedback_type === 'false_positive' ? styles.badgeSafe : styles.badgeDanger}`}>
                        {sample.feedback_type === 'false_positive' ? 'False Positive' : 'False Negative'}
                      </span>
                    </td>
                    <td>{sample.reported_by}</td>
                    <td>
                      <span className={`${styles.badge} ${styles['badgeStatus' + sample.status]}`}>
                        {filterLabels[sample.status] || sample.status}
                      </span>
                    </td>
                    <td>{new Date(sample.created_at).toLocaleString('id-ID')}</td>
                    <td className={styles.stickyAction}>
                      <div className={styles.actions}>
                        <button
                          className={styles.btnIcon}
                          onClick={() => setSelectedSample(sample)}
                          title="Lihat detail"
                          aria-label={`Lihat detail sampel ${sample.email_id}`}
                        >
                          <FileText size={16} />
                        </button>
                        {sample.status === 'pending' && (
                          <>
                            <button
                              className={styles.btnIcon}
                              onClick={() => confirmReview(sample, 'approved')}
                              title="Setujui koreksi"
                              aria-label={`Setujui koreksi sampel ${sample.email_id}`}
                            >
                              <CheckCircle size={16} color="#4caf50" />
                            </button>
                            <button
                              className={styles.btnIcon}
                              onClick={() => confirmReview(sample, 'rejected')}
                              title="Tolak koreksi"
                              aria-label={`Tolak koreksi sampel ${sample.email_id}`}
                            >
                              <XCircle size={16} color="#f44336" />
                            </button>
                          </>
                        )}
                        <button
                          className={styles.btnIcon}
                          onClick={() => {
                            confirmDelete(sample)
                          }}
                          title="Hapus sampel"
                          aria-label={`Hapus sampel ${sample.email_id}`}
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

        {(samplesData?.total || 0) > 0 && (
          <div className={styles.pagination}>
            <span>Menampilkan {samples.length} dari {samplesData.total} sampel</span>
            <div>
              <button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Sebelumnya</button>
              <span>Halaman {page} dari {totalPages}</span>
              <button disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>Berikutnya</button>
            </div>
          </div>
        )}

        {/* Sample Detail Modal */}
        {selectedSample && (
          <div className={styles.modal} onClick={() => setSelectedSample(null)}>
            <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <h2>Detail Sampel Pelatihan</h2>
                <button onClick={() => setSelectedSample(null)}>&times;</button>
              </div>
              <div className={styles.modalBody}>
                <div className={styles.detailRow}>
                  <strong>Email ID:</strong> <code>{selectedSample.email_id}</code>
                </div>
                <div className={styles.detailRow}>
                  <strong>Subjek:</strong> {selectedSample.subject}
                </div>
                <div className={styles.detailRow}>
                  <strong>Pengirim:</strong> {selectedSample.sender}
                </div>
                <div className={styles.detailRow}>
                  <strong>Label Awal:</strong>
                  <span className={`${styles.badge} ${styles['badge' + selectedSample.original_label]}`}>
                    {selectedSample.original_label}
                  </span>
                </div>
                <div className={styles.detailRow}>
                  <strong>Label Koreksi:</strong>
                  <span className={`${styles.badge} ${selectedSample.corrected_label === 'clean' ? styles.badgeSafe : styles.badgeDanger}`}>
                    {selectedSample.corrected_label}
                  </span>
                </div>
                <div className={styles.detailRow}>
                  <strong>Jenis Koreksi:</strong> {selectedSample.feedback_type === 'false_positive' ? 'False Positive (seharusnya aman)' : 'False Negative (seharusnya berbahaya)'}
                </div>
                <div className={styles.detailRow}>
                  <strong>Skor Deteksi Awal:</strong>
                  <pre>{JSON.stringify(selectedSample.original_scores, null, 2)}</pre>
                </div>
                <div className={styles.detailRow}>
                  <strong>Catatan:</strong> {selectedSample.notes || '(tidak ada)'}
                </div>
                <div className={styles.detailRow}>
                  <strong>Dilaporkan Oleh:</strong> {selectedSample.reported_by}
                </div>
                <div className={styles.detailRow}>
                  <strong>Ditinjau Oleh:</strong> {selectedSample.reviewed_by || '(belum ditinjau)'}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
      <ConfirmDialog
        open={Boolean(confirmation)}
        title={confirmation?.title}
        message={confirmation?.message}
        detail={confirmation?.detail}
        confirmLabel={confirmation?.confirmLabel}
        cancelLabel={confirmation?.cancelLabel}
        danger={confirmation?.danger}
        busy={updateSampleMutation.isPending || deleteSampleMutation.isPending || retrainLoading}
        onConfirm={confirmation?.onConfirm}
        onCancel={() => setConfirmation(null)}
      />
    </AdminShell>
  )
}
