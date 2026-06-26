import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import styles from './SearchFilterPanel.module.css'

const SEARCH_IN_OPTIONS = [
  { value: 'all', label: 'Semua email' },
  { value: 'quarantine', label: 'Karantina' },
  { value: 'warn', label: 'Peringatan' },
  { value: 'clean', label: 'Bersih' },
]

const SIZE_OPERATOR_OPTIONS = [
  { value: 'gt', label: 'Lebih besar dari' },
  { value: 'lt', label: 'Lebih kecil dari' },
]

const SIZE_UNIT_OPTIONS = [
  { value: 'MB', label: 'MB' },
  { value: 'KB', label: 'KB' },
  { value: 'B', label: 'Byte' },
]

export default function SearchFilterPanel({ open, onClose, onSearch }) {
  const navigate = useNavigate()

  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [subject, setSubject] = useState('')
  const [hasWords, setHasWords] = useState('')
  const [noWords, setNoWords] = useState('')
  const [sizeOp, setSizeOp] = useState('gt')
  const [sizeVal, setSizeVal] = useState('')
  const [sizeUnit, setSizeUnit] = useState('MB')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [searchIn, setSearchIn] = useState('all')
  const [hasAttachment, setHasAttachment] = useState(false)
  const [excludeChat, setExcludeChat] = useState(true)

  const handleReset = () => {
    setFrom(''); setTo(''); setSubject(''); setHasWords(''); setNoWords('')
    setSizeOp('gt'); setSizeVal(''); setSizeUnit('MB')
    setDateFrom(''); setDateTo(''); setSearchIn('all')
    setHasAttachment(false); setExcludeChat(true)
  }

  const handleSearch = () => {
    // Build query string
    const params = new URLSearchParams()
    if (from)      params.set('from', from)
    if (to)        params.set('to', to)
    if (subject)   params.set('subject', subject)
    if (hasWords)  params.set('q', hasWords)
    if (noWords)   params.set('nq', noWords)
    if (sizeVal)   params.set('size', `${sizeOp}:${sizeVal}${sizeUnit}`)
    if (dateFrom)  params.set('after', dateFrom)
    if (dateTo)    params.set('before', dateTo)
    if (searchIn !== 'all') params.set('filter', searchIn)
    if (hasAttachment) params.set('has', 'attachment')
    if (excludeChat) params.set('excludeChat', '1')

    onClose()
    navigate(`/inbox?${params.toString()}`)
    if (onSearch) onSearch(params.toString())
  }

  if (!open) return null

  return (
    <>
      <div className={styles.overlay} onClick={onClose} />
      <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
        <div className={styles.content}>

          {/* Dari */}
          <div className={styles.row}>
            <span className={styles.label}>Dari</span>
            <div className={styles.inputWrap}>
              <input
                className={styles.input}
                type="text"
                placeholder="pengirim@contoh.com"
                value={from}
                onChange={(e) => setFrom(e.target.value)}
                id="filter-from"
                autoComplete="off"
              />
            </div>
          </div>

          {/* Kepada */}
          <div className={styles.row}>
            <span className={styles.label}>Kepada</span>
            <div className={styles.inputWrap}>
              <input
                className={styles.input}
                type="text"
                placeholder="penerima@contoh.com"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                id="filter-to"
                autoComplete="off"
              />
            </div>
          </div>

          {/* Subjek */}
          <div className={styles.row}>
            <span className={styles.label}>Subjek</span>
            <div className={styles.inputWrap}>
              <input
                className={styles.input}
                type="text"
                placeholder="Subjek email"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                id="filter-subject"
                autoComplete="off"
              />
            </div>
          </div>

          {/* Mengandung kata-kata */}
          <div className={styles.row}>
            <span className={styles.label}>Mengandung kata-kata</span>
            <div className={styles.inputWrap}>
              <input
                className={styles.input}
                type="text"
                placeholder="kata kunci tertentu"
                value={hasWords}
                onChange={(e) => setHasWords(e.target.value)}
                id="filter-has-words"
                autoComplete="off"
              />
            </div>
          </div>

          {/* Tidak mengandung */}
          <div className={styles.row}>
            <span className={styles.label}>Tidak mengandung</span>
            <div className={styles.inputWrap}>
              <input
                className={styles.input}
                type="text"
                placeholder="kata yang dikecualikan"
                value={noWords}
                onChange={(e) => setNoWords(e.target.value)}
                id="filter-no-words"
                autoComplete="off"
              />
            </div>
          </div>

          {/* Ukuran */}
          <div className={styles.row}>
            <span className={styles.label}>Ukuran</span>
            <div className={styles.inputWrap}>
              <div className={styles.sizeRow}>
                <select
                  className={styles.select}
                  value={sizeOp}
                  onChange={(e) => setSizeOp(e.target.value)}
                  id="filter-size-op"
                >
                  {SIZE_OPERATOR_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
                <input
                  className={styles.sizeInput}
                  type="number"
                  placeholder="0"
                  min="0"
                  value={sizeVal}
                  onChange={(e) => setSizeVal(e.target.value)}
                  id="filter-size-val"
                />
                <select
                  className={styles.select}
                  value={sizeUnit}
                  onChange={(e) => setSizeUnit(e.target.value)}
                  id="filter-size-unit"
                  style={{ width: 70 }}
                >
                  {SIZE_UNIT_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Cakupan tanggal */}
          <div className={styles.row}>
            <span className={styles.label}>Cakupan tanggal</span>
            <div className={styles.inputWrap}>
              <div className={styles.dateRange}>
                <input
                  className={styles.input}
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  id="filter-date-from"
                />
                <span className={styles.dateRangeSep}>–</span>
                <input
                  className={styles.input}
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  id="filter-date-to"
                />
              </div>
            </div>
          </div>

          {/* Telusuri dalam */}
          <div className={styles.row}>
            <span className={styles.label}>Telusuri</span>
            <div className={styles.inputWrap}>
              <select
                className={styles.select}
                value={searchIn}
                onChange={(e) => setSearchIn(e.target.value)}
                id="filter-search-in"
                style={{ width: '100%' }}
              >
                {SEARCH_IN_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Checkbox options */}
          <div className={styles.row} style={{ borderBottom: 'none' }}>
            <span className={styles.label}></span>
            <div className={styles.inputWrap}>
              <div className={styles.checkRow}>
                <label className={styles.checkItem} id="filter-has-attachment-label">
                  <input
                    type="checkbox"
                    checked={hasAttachment}
                    onChange={(e) => setHasAttachment(e.target.checked)}
                    id="filter-has-attachment"
                  />
                  Memiliki lampiran
                </label>
                <label className={styles.checkItem} id="filter-exclude-chat-label">
                  <input
                    type="checkbox"
                    checked={excludeChat}
                    onChange={(e) => setExcludeChat(e.target.checked)}
                    id="filter-exclude-chat"
                  />
                  Jangan sertakan chat
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <button className={styles.btnCancel} onClick={handleReset} id="filter-reset-btn">
            Hapus Filter
          </button>
          <button className={styles.btnCancel} onClick={onClose} id="filter-cancel-btn">
            Batal
          </button>
          <button className={styles.btnSearch} onClick={handleSearch} id="filter-search-btn">
            <Search size={15} />
            Telusuri
          </button>
        </div>
      </div>
    </>
  )
}
