import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './client'
import { MAILBOX_SESSION_PREFIX } from '../utils/mailbox'

// PERFORMANCE: Reduced auth polling from 60s to 5 minutes, with longer staleTime
export const useMe = () =>
  useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const { data } = await api.get('/auth/me')
      return data
    },
    retry: false,
    staleTime: 10 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
    refetchOnWindowFocus: true,
  })

export const useLogin = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ username, password }) => {
      return api.post('/auth/login', { username, password })
    },
    onSuccess: async (res) => {
      if (res?.data?.role) {
        qc.setQueryData(['me'], {
          authenticated: true,
          user: { username: res.data.username, role: res.data.role },
        })
      }
      await qc.invalidateQueries({ queryKey: ['me'] })
    },
  })
}

function clearAllMailboxSessions() {
  // Dashboard logout clears ALL mailbox localStorage sessions too.
  try {
    Object.keys(localStorage)
      .filter((key) => key.startsWith(MAILBOX_SESSION_PREFIX))
      .forEach((key) => localStorage.removeItem(key))
  } catch {
    // Ignore localStorage failures.
  }
}

export const useLogout = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post('/auth/logout'),
    onSuccess: () => {
      // Clear dashboard React Query cache + all mailbox sessions in localStorage.
      clearAllMailboxSessions()
      qc.clear()
      window.location.href = '/login'
    },
  })
}

