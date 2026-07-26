import { useQuery } from '@tanstack/react-query'
import api from './client'

/**
 * Fetch the current user's mailbox info (for mailbox-role users).
 * Returns mailbox details including email, id, and avatar_url.
 */
export const useUserMailbox = ({ mailboxId } = {}) =>
  useQuery({
    queryKey: ['user-mailbox', mailboxId || ''],
    queryFn: async () => {
      const params = {}
      if (mailboxId) params.mailbox_id = mailboxId
      const { data } = await api.get('/user/mailboxes', { params })
      const rows = Array.isArray(data) ? data : []
      if (mailboxId) {
        return rows.find((m) => String(m.id) === String(mailboxId) || m.email === mailboxId) || rows[0] || null
      }
      return rows[0] || null
    },
    staleTime: 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
    retry: false,
  })
