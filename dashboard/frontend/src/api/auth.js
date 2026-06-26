import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './client'

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
    onSuccess: async () => {
      await qc.refetchQueries({ queryKey: ['me'] })
    },
  })
}

export const useLogout = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post('/auth/logout'),
    onSuccess: () => {
      qc.clear()
      window.location.href = '/login'
    },
  })
}
