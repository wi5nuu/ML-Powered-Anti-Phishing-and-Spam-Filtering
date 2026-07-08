import { useQuery } from '@tanstack/react-query'
import api from './client'
import { useMe } from './auth'

export function useUserMailbox() {
  const { data: auth } = useMe()
  const role = auth?.user?.role
  return useQuery({
    queryKey: ['userMailbox'],
    queryFn: async () => {
      const { data } = await api.get('/api/user/mailbox')
      return data.mailbox || null
    },
    enabled: role === 'user',
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
}
