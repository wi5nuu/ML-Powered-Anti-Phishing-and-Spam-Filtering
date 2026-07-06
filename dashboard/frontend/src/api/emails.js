import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './client'

// ── Fetch all emails (supports filter=label or category=name)
export const useEmails = (filter = 'all', searchQuery = '', options = {}) =>
  useQuery({
    queryKey: [
      'emails',
      filter,
      searchQuery,
      options.mailbox || '',
      options.mailboxId || '',
      options.page || 1,
      options.pageSize || 50,
    ],
    queryFn: async () => {
      const CATEGORIES = ['transaction','customer_service','internal_document','b2b','spam','phishing','malware']
      const FOLDERS = ['allmail', 'draft', 'trash']
      const params = {}
      if (filter !== 'all') {
        if (CATEGORIES.includes(filter)) {
          params.category = filter
        } else if (FOLDERS.includes(filter)) {
          params.folder = filter === 'allmail' ? 'all' : filter
        } else {
          params.label = filter.toUpperCase()
        }
      }
      if (searchQuery?.trim()) params.q = searchQuery.trim()
      if (options.mailbox) params.mailbox = options.mailbox
      if (options.mailboxId) params.mailbox_id = options.mailboxId
      params.page = options.page || 1
      params.page_size = options.pageSize || 50
      const { data } = await api.get('/emails', { params })
      return data
    },
    refetchInterval: 30000,
    staleTime: 10000,
  })

// ── Fetch single email
export const useEmail = (emailId) =>
  useQuery({
    queryKey: ['email', emailId],
    queryFn: async () => {
      const { data } = await api.get(`/emails/${emailId}`)
      return data
    },
    enabled: !!emailId,
  })

// ── Release email (optimistic)
export const useReleaseEmail = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (emailId) => api.post(`/emails/${emailId}/release`),
    onMutate: async (emailId) => {
      await qc.cancelQueries({ queryKey: ['emails'] })
      const prev = qc.getQueriesData({ queryKey: ['emails'] })
      qc.setQueriesData({ queryKey: ['emails'] }, (old) =>
        old ? { ...old, emails: old.emails.filter((e) => e.email_id !== emailId) } : old
      )
      return { prev }
    },
    onError: (_err, _id, ctx) => {
      qc.setQueriesData({ queryKey: ['emails'] }, ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['emails'] }),
  })
}

// ── Confirm spam (optimistic)
export const useConfirmSpam = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (emailId) => api.post(`/emails/${emailId}/confirm-spam`),
    onMutate: async (emailId) => {
      await qc.cancelQueries({ queryKey: ['emails'] })
      const prev = qc.getQueriesData({ queryKey: ['emails'] })
      qc.setQueriesData({ queryKey: ['emails'] }, (old) =>
        old ? { ...old, emails: old.emails.filter((e) => e.email_id !== emailId) } : old
      )
      return { prev }
    },
    onError: (_err, _id, ctx) => {
      qc.setQueriesData({ queryKey: ['emails'] }, ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['emails'] }),
  })
}

// ── Report false positive
export const useReportFalsePositive = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ emailId, notes }) =>
      api.post(`/emails/${emailId}/report-false-positive`, { notes }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['emails'] }),
  })
}

// ── Delete email
export const useDeleteEmail = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (emailId) => api.delete(`/emails/${emailId}`),
    onMutate: async (emailId) => {
      await qc.cancelQueries({ queryKey: ['emails'] })
      const prev = qc.getQueriesData({ queryKey: ['emails'] })
      qc.setQueriesData({ queryKey: ['emails'] }, (old) =>
        old ? { ...old, emails: old.emails.filter((e) => e.email_id !== emailId) } : old
      )
      return { prev }
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueriesData({ queryKey: ['emails'] }, ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['emails'] }),
  })
}

export const useRestoreEmail = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (emailId) => api.post(`/emails/${emailId}/restore`),
    onSettled: () => qc.invalidateQueries({ queryKey: ['emails'] }),
  })
}
