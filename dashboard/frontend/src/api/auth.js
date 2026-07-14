import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './client'
import { MAILBOX_SESSION_PREFIX } from '../utils/mailbox'

export const useMe = () =>
  useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const { data } = await api.get('/auth/me')
      return data
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
    refetchInterval: 60 * 1000,
    refetchOnWindowFocus: false,
  })

export const useLogin = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ username, password }) => {
      const params = new URLSearchParams()
      params.append('username', username)
      params.append('password', password)
      params.append('grant_type', 'password')
      return api.post('/auth/login', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
    },
    onSuccess: async (res) => {
      if (res?.data?.role && res.data.role !== 'mailbox') {
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
