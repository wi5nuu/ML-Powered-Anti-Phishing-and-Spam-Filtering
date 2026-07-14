import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './client'

export const useProfile = (mailboxId = '') =>
  useQuery({
    queryKey: ['profile', mailboxId],
    queryFn: async () => {
      const { data } = await api.get('/auth/profile', {
        params: mailboxId ? { mailbox_id: mailboxId } : {},
      })
      return data
    },
    retry: false,
    staleTime: 60000,
  })

export const useChangePassword = () =>
  useMutation({
    mutationFn: ({ current_password, new_password }) =>
      api.post('/auth/change-password', { current_password, new_password }),
  })

export const useUpdateProfile = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ username, current_password, new_password }) =>
      api.put('/auth/profile', { username, current_password, new_password }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile'] })
      qc.invalidateQueries({ queryKey: ['me'] })
    },
  })
}

export const useUploadProfileAvatar = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input) => {
      const file = input?.file || input
      const mailboxId = input?.mailboxId || ''
      const formData = new FormData()
      formData.append('avatar', file)
      return api.post('/auth/profile/avatar', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        params: mailboxId ? { mailbox_id: mailboxId } : {},
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile'] })
      qc.invalidateQueries({ queryKey: ['me'] })
    },
  })
}

export const useApiKeys = () =>
  useQuery({
    queryKey: ['api-keys'],
    queryFn: async () => {
      const { data } = await api.get('/auth/api-keys')
      return data
    },
    staleTime: 30000,
  })

export const useCreateApiKey = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, rate_limit }) =>
      api.post('/auth/api-keys', { name, rate_limit }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-keys'] }),
  })
}

export const useDeleteApiKey = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (keyId) => api.delete(`/auth/api-keys/${keyId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-keys'] }),
  })
}

export const useActivity = () =>
  useQuery({
    queryKey: ['activity'],
    queryFn: async () => {
      const { data } = await api.get('/auth/activity')
      return data
    },
    staleTime: 30000,
  })
