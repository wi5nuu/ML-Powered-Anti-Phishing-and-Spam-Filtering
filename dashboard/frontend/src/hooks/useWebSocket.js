import { useEffect, useRef } from 'react'
import { useToast } from './useToast'
import { useQueryClient } from '@tanstack/react-query'

const MAX_RETRIES = 10
const BASE_DELAY_MS = 1000
const MAX_DELAY_MS = 30000

export function useWebSocket() {
  const { showToast } = useToast()
  const qc = useQueryClient()
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)
  const retriesRef = useRef(0)
  const intentionalCloseRef = useRef(false)

  useEffect(() => {
    function connect() {
      // Close any existing socket before creating a new one to prevent duplicates
      if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
        wsRef.current.close()
      }

      // The access_token is an HttpOnly cookie — the browser sends it automatically.
      // No need to pass it manually in the URL.
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const url = `${proto}//${window.location.host}/ws`

      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        // Reset retry counter on successful connection
        retriesRef.current = 0
      }

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

      ws.onclose = (event) => {
        // Do not reconnect on intentional close or auth error (4001)
        if (intentionalCloseRef.current) return
        if (event.code === 4001) {
          console.warn('WebSocket closed: unauthorized. Not reconnecting.')
          return
        }

        if (retriesRef.current >= MAX_RETRIES) {
          console.warn('WebSocket max retries reached. Giving up.')
          return
        }

        // Exponential backoff: 1s, 2s, 4s, 8s … capped at 30s
        const delay = Math.min(BASE_DELAY_MS * Math.pow(2, retriesRef.current), MAX_DELAY_MS)
        retriesRef.current += 1
        reconnectRef.current = setTimeout(connect, delay)
      }

      ws.onerror = () => {
        // onclose will fire after onerror and handle reconnect
        ws.close()
      }
    }

    intentionalCloseRef.current = false
    connect()

    return () => {
      intentionalCloseRef.current = true
      clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [showToast, qc])
}
