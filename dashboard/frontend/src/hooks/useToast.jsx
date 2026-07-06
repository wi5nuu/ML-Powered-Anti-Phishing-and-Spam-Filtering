import { createContext, useContext, useRef, useCallback } from 'react'

const ToastCtx = createContext(null)

export function ToastProvider({ children }) {
  const containerRef = useRef(null)
  const keyedToastsRef = useRef(new Map())

  const showToast = useCallback((message, type = 'info', options = {}) => {
    const container = containerRef.current
    if (!container) return
    const toastKey = options.id || null
    const duration = options.duration ?? 4200

    if (toastKey && keyedToastsRef.current.has(toastKey)) {
      const existing = keyedToastsRef.current.get(toastKey)
      clearTimeout(existing.timer)
      existing.el.className = `toast toast-${type} ${options.compact ? 'toast-compact' : ''}`.trim()
      existing.el.textContent = message
      existing.timer = setTimeout(() => {
        existing.el.remove()
        keyedToastsRef.current.delete(toastKey)
      }, duration)
      return
    }

    const el = document.createElement('div')
    el.className = `toast toast-${type} ${options.compact ? 'toast-compact' : ''}`.trim()
    el.textContent = message
    container.appendChild(el)
    const timer = setTimeout(() => {
      el.remove()
      if (toastKey) keyedToastsRef.current.delete(toastKey)
    }, duration)
    if (toastKey) keyedToastsRef.current.set(toastKey, { el, timer })
  }, [])

  return (
    <ToastCtx.Provider value={{ showToast }}>
      {children}
      <div
        ref={containerRef}
        style={{
          position: 'fixed',
          bottom: 16,
          left: 16,
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          alignItems: 'flex-start',
          pointerEvents: 'none',
        }}
      />
    </ToastCtx.Provider>
  )
}

export const useToast = () => useContext(ToastCtx)
