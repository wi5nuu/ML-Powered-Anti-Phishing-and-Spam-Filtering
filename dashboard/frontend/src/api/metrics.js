import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './client'

// ── Quick stats (header ribbon, sidebar counts)
export const useStats = () =>
  useQuery({
    queryKey: ['stats'],
    queryFn: async () => {
      const { data } = await api.get('/stats')
      return data
    },
    refetchInterval: 10000,
    staleTime: 3000,
  })

// ── Full metrics panel (charts, top senders, daily stats)
export const useMetrics = () =>
  useQuery({
    queryKey: ['metrics'],
    queryFn: async () => {
      const { data } = await api.get('/metrics')
      return data
    },
    refetchInterval: 30000,
    staleTime: 10000,
  })

// ── Audit log (paginated)
export const useAuditLog = ({ page = 1, pageSize = 50, eventType, username } = {}) =>
  useQuery({
    queryKey: ['audit-log', page, pageSize, eventType, username],
    queryFn: async () => {
      const params = { page, page_size: pageSize }
      if (eventType) params.event_type = eventType
      if (username) params.username = username
      const { data } = await api.get('/audit-log', { params })
      return data
    },
    refetchInterval: 30000,
    staleTime: 10000,
  })

// ── System settings
export const useSettings = () =>
  useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      const { data } = await api.get('/settings')
      return data
    },
    staleTime: 60000,
  })

export const useUpdateSettings = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (settings) => api.post('/settings', settings),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  })
}

// ── Test IMAP connection
export const useTestImap = () =>
  useMutation({
    mutationFn: () => api.post('/settings/test-imap'),
  })

// ── CSV export (returns download URL)
export const downloadEmailsCsv = async (label) => {
  const params = label && label !== 'all' ? { label } : {}
  const response = await api.get('/emails/export-csv', {
    params,
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  const date = new Date().toISOString().slice(0, 10)
  link.setAttribute('download', `lti_emails_${date}.csv`)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
