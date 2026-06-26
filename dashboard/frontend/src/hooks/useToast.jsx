import { createContext, useContext, useEffect, useRef, useCallback } from 'react'

const ToastCtx = createContext(null)

export function ToastProvider({ children }) {
  const toastsRef = useRef([])
  const containerRef = useRef(null)

  const showToast = useCallback((message, type = 'info') => {
    const container = containerRef.current
    if (!container) return
    const el = document.createElement('div')
    el.className = `toast toast-${type}`
    el.textContent = message
    container.appendChild(el)
    setTimeout(() => el.remove(), 4200)
  }, [])

  return (
    <ToastCtx.Provider value={{ showToast }}>
      {children}
      <div
        ref={containerRef}
        style={{
          position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
          zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center',
        }}
      />
    </ToastCtx.Provider>
  )
}

export const useToast = () => useContext(ToastCtx)
