import { useEffect, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'

export function useAdminWebSocket(enabled = true) {
  const qc = useQueryClient()
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  const connect = useCallback(() => {
    if (!enabled) return
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${proto}//${window.location.host}/ws`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        qc.invalidateQueries({ queryKey: ['emails'] })
        qc.invalidateQueries({ queryKey: ['stats'] })

        qc.invalidateQueries({ queryKey: ['admin-stats'] })
        qc.invalidateQueries({ queryKey: ['admin-logs'] })
        qc.invalidateQueries({ queryKey: ['admin-reports'] })
        qc.invalidateQueries({ queryKey: ['admin-mailboxes'] })
        qc.invalidateQueries({ queryKey: ['admin-detections'] })
      } catch {}
    }

    ws.onclose = () => {
      reconnectRef.current = setTimeout(connect, 5000)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [enabled, qc])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
      clearTimeout(reconnectRef.current)
    }
  }, [connect])
}
