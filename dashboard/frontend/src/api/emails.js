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
    enabled: options.enabled !== false,
    queryFn: async () => {
      const CATEGORIES = ['transaction','customer_service','internal_document','b2b','spam','phishing','malware']
      const FOLDERS = ['allmail', 'draft', 'trash', 'starred', 'snoozed']
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
    // Each request is paginated, so polling keeps the mailbox current without
    // loading the entire table or inventing client-side counts.
    refetchInterval: options.refetchInterval ?? 5000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    staleTime: 3000,
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
    retry: false,
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
      if (ctx?.prev) {
        ctx.prev.forEach(([queryKey, data]) => {
          qc.setQueryData(queryKey, data)
        })
      }
    },
    onSettled: (_data, _err, emailId) => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['email', emailId] })
    },
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
      if (ctx?.prev) {
        ctx.prev.forEach(([queryKey, data]) => {
          qc.setQueryData(queryKey, data)
        })
      }
    },
    onSettled: (_data, _err, emailId) => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['email', emailId] })
    },
  })
}

// ── Report false positive
export const useReportFalsePositive = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ emailId, notes }) =>
      api.post(`/emails/${emailId}/report-false-positive`, { notes }),
    onSettled: (_data, _err, { emailId }) => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['email', emailId] })
    },
  })
}

// ── Report false negative (dangerous email that was marked safe)
export const useReportFalseNegative = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ emailId, correctedLabel, notes }) =>
      api.post(`/emails/${emailId}/report-false-negative`, { corrected_label: correctedLabel, notes }),
    onSettled: (_data, _err, { emailId }) => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['email', emailId] })
    },
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
      if (ctx?.prev) {
        ctx.prev.forEach(([queryKey, data]) => {
          qc.setQueryData(queryKey, data)
        })
      }
    },
    onSettled: (_data, _err, emailId) => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['email', emailId] })
    },
  })
}

export const useRestoreEmail = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (emailId) => api.post(`/emails/${emailId}/restore`),
    onSettled: () => qc.invalidateQueries({ queryKey: ['emails'] }),
  })
}

// ── Toggle email read status
export const useToggleReadEmail = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ emailId, isRead }) => api.put(`/emails/${emailId}/read`, { is_read: isRead }),
    onMutate: async ({ emailId, isRead }) => {
      // Optimistically update the list cache
      await qc.cancelQueries({ queryKey: ['emails'] })
      await qc.cancelQueries({ queryKey: ['email', emailId] })
      const prev = qc.getQueriesData({ queryKey: ['emails'] })
      const prevDetail = qc.getQueryData(['email', emailId])
      qc.setQueriesData({ queryKey: ['emails'] }, (old) => {
        if (!old) return old
        return {
          ...old,
          emails: old.emails.map((e) => (e.email_id === emailId ? { ...e, is_read: isRead } : e)),
        }
      })
      // Optimistically update the single email cache if it exists
      qc.setQueryData(['email', emailId], (old) => {
        if (!old) return old
        return {
          ...old,
          is_read: isRead,
          thread_is_read: isRead,
          thread_has_unread: !isRead,
          thread_messages: Array.isArray(old.thread_messages)
            ? old.thread_messages.map((message) => {
                const label = String(message.label || '').toUpperCase()
                const status = String(message.status || '').toLowerCase()
                return label === 'SENT' || label === 'DRAFT' || status === 'sent' || status === 'draft'
                  ? message
                  : { ...message, is_read: isRead }
              })
            : old.thread_messages,
        }
      })
      return { prev, prevDetail }
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        ctx.prev.forEach(([queryKey, data]) => qc.setQueryData(queryKey, data))
      }
      if (ctx?.prevDetail) qc.setQueryData(['email', _vars.emailId], ctx.prevDetail)
    },
    onSettled: (_data, _err, vars) => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['email', vars.emailId] })
    },
  })
}

// ── Toggle starred
export const useToggleStarred = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ emailId, isStarred }) => api.put(`/emails/${emailId}/starred`, { is_starred: isStarred }),
    onMutate: async ({ emailId, isStarred }) => {
      await qc.cancelQueries({ queryKey: ['emails'] })
      const prev = qc.getQueriesData({ queryKey: ['emails'] })
      qc.setQueriesData({ queryKey: ['emails'] }, (old) => {
        if (!old) return old
        return {
          ...old,
          emails: old.emails.map((e) => (e.email_id === emailId ? { ...e, is_starred: isStarred } : e)),
        }
      })
      qc.setQueryData(['email', emailId], (old) => {
        if (!old) return old
        return { ...old, is_starred: isStarred }
      })
      return { prev }
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueriesData({ queryKey: ['emails'] }, ctx.prev)
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['stats'] })
    },
  })
}

// ── Toggle snooze
export const useSnoozeEmail = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ emailId, snoozedUntil }) => api.put(`/emails/${emailId}/snooze`, { snoozed_until: snoozedUntil }),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['emails'] })
    },
  })
}
