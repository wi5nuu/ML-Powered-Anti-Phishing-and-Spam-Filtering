import { useMutation } from '@tanstack/react-query'
import api from './client'

/**
 * Analyze a raw email string via POST /api/analyze.
 * Returns full dual-detection result with XAI reasons, URL analysis, etc.
 */
export const useAnalyzeEmail = () =>
  useMutation({
    mutationFn: async (rawEmail) => {
      const { data } = await api.post('/analyze', { raw_email: rawEmail })
      return data
    },
  })
