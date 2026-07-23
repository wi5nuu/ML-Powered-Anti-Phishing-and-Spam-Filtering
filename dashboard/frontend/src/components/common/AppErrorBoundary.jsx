import React from 'react'

export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Unhandled dashboard render error', error, info)
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <main style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: 24,
        background: 'var(--bg, #f8fafc)',
        color: 'var(--text, #172033)',
        fontFamily: 'Google Sans, Roboto, sans-serif',
      }}>
        <section style={{
          width: 'min(520px, 100%)',
          padding: 24,
          border: '1px solid var(--border, #dbe2ea)',
          borderRadius: 12,
          background: 'var(--surface, #fff)',
          boxShadow: '0 12px 32px rgba(15, 23, 42, 0.08)',
        }}>
          <h1 style={{ margin: '0 0 8px', fontSize: 20 }}>Halaman mengalami kendala</h1>
          <p style={{ margin: '0 0 18px', color: 'var(--text-muted, #64748b)', lineHeight: 1.5 }}>
            Data Anda tetap aman. Muat ulang halaman untuk memulihkan tampilan.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              border: 0,
              borderRadius: 8,
              padding: '10px 16px',
              background: '#2563eb',
              color: '#fff',
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            Muat ulang
          </button>
        </section>
      </main>
    )
  }
}
