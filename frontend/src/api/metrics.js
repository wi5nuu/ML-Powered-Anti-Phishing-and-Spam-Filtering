import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './client'
import { APP_TIME_ZONE } from '../utils/time'

// ── Quick stats (header ribbon, sidebar counts)
// PERFORMANCE: Reduced refetch interval from 10s to 30s
export const useStats = () =>
  useQuery({
    queryKey: ['stats'],
    queryFn: async () => {
      const { data } = await api.get('/stats')
      return data
    },
    refetchInterval: 30000,
    staleTime: 15000,
  })

// ── Full metrics panel (charts, top senders, daily stats)
// PERFORMANCE: Increased staleTime to reduce unnecessary requests
export const useMetrics = ({ mailbox, mailboxId } = {}) =>
  useQuery({
    queryKey: ['metrics', mailbox || '', mailboxId || ''],
    queryFn: async () => {
      const params = {}
      if (mailbox) params.mailbox = mailbox
      if (mailboxId) params.mailbox_id = mailboxId
      const { data } = await api.get('/metrics', { params })
      return data
    },
    refetchInterval: 60000,
    staleTime: 30000,
  })

// ── Audit log (paginated)
// PERFORMANCE: Increased intervals, audit logs don't change frequently
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
    refetchInterval: 60000,
    staleTime: 30000,
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
  const date = new Date().toLocaleDateString('en-CA', { timeZone: APP_TIME_ZONE })
  link.setAttribute('download', `cognimail_emails_${date}.csv`)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
