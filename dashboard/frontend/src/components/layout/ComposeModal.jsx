import { useState } from 'react'
import { Minus, Maximize2, Minimize2, X, Trash2 } from 'lucide-react'
import { useToast } from '../../hooks/useToast'
import styles from './ComposeModal.module.css'

export default function ComposeModal({ open, onClose }) {
  const { showToast } = useToast()
  const [to, setTo] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [minimized, setMinimized] = useState(false)
  const [maximized, setMaximized] = useState(false)

  if (!open) return null

  const handleSend = (e) => {
    e.preventDefault()
    if (!to) {
      showToast('Silakan tentukan penerima email', 'error')
      return
    }
    
    // Simulate sending email
    showToast(`Email berhasil dikirim ke ${to} (Simulasi)`, 'success')
    setTo('')
    setSubject('')
    setBody('')
    onClose()
  }

  const handleDiscard = () => {
    if (window.confirm('Buang draf email ini?')) {
      setTo('')
      setSubject('')
      setBody('')
      onClose()
    }
  }

  return (
    <div className={`${styles.composeOverlay} ${minimized ? styles.minimized : ''} ${maximized ? styles.maximized : ''}`}>
      {/* Header bar */}
      <div className={styles.header} onClick={() => setMinimized(!minimized)}>
        <span className={styles.title}>{subject || 'Pesan Baru'}</span>
        <div className={styles.actions} onClick={(e) => e.stopPropagation()}>
          <button 
            className={styles.actionBtn} 
            onClick={() => setMinimized(!minimized)} 
            title="Minimalkan"
          >
            <Minus size={16} />
          </button>
          <button 
            className={styles.actionBtn} 
            onClick={() => setMaximized(!maximized)} 
            title={maximized ? 'Pulihkan ukuran' : 'Maksimalkan'}
          >
            {maximized ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
          <button 
            className={styles.actionBtn} 
            onClick={onClose} 
            title="Simpan & Tutup"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Main content body */}
      {!minimized && (
        <form onSubmit={handleSend} className={styles.body}>
          <div className={styles.field}>
            <span className={styles.label}>Penerima:</span>
            <input 
              type="text" 
              className={styles.input} 
              value={to} 
              onChange={(e) => setTo(e.target.value)} 
              placeholder="nama@contoh.com"
              required
            />
          </div>
          <div className={styles.field}>
            <span className={styles.label}>Subjek:</span>
            <input 
              type="text" 
              className={styles.input} 
              value={subject} 
              onChange={(e) => setSubject(e.target.value)} 
              placeholder="Subjek email"
            />
          </div>
          <textarea 
            className={styles.textarea} 
            value={body} 
            onChange={(e) => setBody(e.target.value)} 
            placeholder="Tulis pesan Anda di sini..."
          />
          
          {/* Footer controls */}
          <div className={styles.footer}>
            <button type="submit" className={styles.sendBtn}>Kirim</button>
            <button 
              type="button" 
              className={styles.trashBtn} 
              onClick={handleDiscard}
              title="Buang draf"
            >
              <Trash2 size={18} />
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
