import { useEffect, useRef } from 'react'
import { useToast } from './useToast'
import { useQueryClient } from '@tanstack/react-query'

export function useWebSocket() {
  const { showToast } = useToast()
  const qc = useQueryClient()
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  useEffect(() => {
    function connect() {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const url = `${proto}//${window.location.host}/ws`
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          const label = (data.label || 'info').toLowerCase()
          const type = label === 'quarantine' ? 'error' : label === 'warn' ? 'warning' : 'success'
          showToast('Ada Email Baru', type, {
            id: 'new-email',
            compact: true,
            duration: 2200,
          })
          qc.invalidateQueries({ queryKey: ['emails'] })
          qc.invalidateQueries({ queryKey: ['stats'] })
        } catch (_) {}
      }

      ws.onclose = () => {
        reconnectRef.current = setTimeout(connect, 5000)
      }
    }

    connect()

    return () => {
      wsRef.current?.close()
      clearTimeout(reconnectRef.current)
    }
  }, [showToast, qc])
}
