import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import { useTranslation } from '../../i18n/context'
import styles from './SearchFilterPanel.module.css'

export default function SearchFilterPanel({ open, onClose, onSearch }) {
  const { t } = useTranslation()
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

  const SEARCH_IN_OPTIONS = [
    { value: 'all', label: t('searchFilter.all') },
    { value: 'spam', label: t('gmail.spam') },
    { value: 'phishing', label: t('gmail.phishing') },
    { value: 'malware', label: t('gmail.malware') },
  ]

  const SIZE_OPERATOR_OPTIONS = [
    { value: 'gt', label: t('searchFilter.sizeLargerThan') },
    { value: 'lt', label: t('searchFilter.sizeSmallerThan') },
  ]

  const SIZE_UNIT_OPTIONS = [
    { value: 'MB', label: 'MB' },
    { value: 'KB', label: 'KB' },
    { value: 'B', label: t('searchFilter.sizeByte') },
  ]

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
    if (searchIn !== 'all') params.set('category', searchIn)
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
            <span className={styles.label}>{t('searchFilter.from')}</span>
            <div className={styles.inputWrap}>
              <input
                className={styles.input}
                type="text"
                placeholder={t('searchFilter.fromPlaceholder')}
                value={from}
                onChange={(e) => setFrom(e.target.value)}
                id="filter-from"
                autoComplete="off"
              />
            </div>
          </div>

          {/* Kepada */}
          <div className={styles.row}>
            <span className={styles.label}>{t('searchFilter.to')}</span>
            <div className={styles.inputWrap}>
              <input
                className={styles.input}
                type="text"
                placeholder={t('searchFilter.toPlaceholder')}
                value={to}
                onChange={(e) => setTo(e.target.value)}
                id="filter-to"
                autoComplete="off"
              />
            </div>
          </div>

          {/* Subjek */}
          <div className={styles.row}>
            <span className={styles.label}>{t('common.subject')}</span>
            <div className={styles.inputWrap}>
              <input
                className={styles.input}
                type="text"
                placeholder={t('common.subject')}
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                id="filter-subject"
                autoComplete="off"
              />
            </div>
          </div>

          {/* Mengandung kata-kata */}
          <div className={styles.row}>
            <span className={styles.label}>{t('searchFilter.containsWords')}</span>
            <div className={styles.inputWrap}>
              <input
                className={styles.input}
                type="text"
                placeholder={t('searchFilter.containsWordsPlaceholder')}
                value={hasWords}
                onChange={(e) => setHasWords(e.target.value)}
                id="filter-has-words"
                autoComplete="off"
              />
            </div>
          </div>

          {/* Tidak mengandung */}
          <div className={styles.row}>
            <span className={styles.label}>{t('searchFilter.excludeWords')}</span>
            <div className={styles.inputWrap}>
              <input
                className={styles.input}
                type="text"
                placeholder={t('searchFilter.excludeWordsPlaceholder')}
                value={noWords}
                onChange={(e) => setNoWords(e.target.value)}
                id="filter-no-words"
                autoComplete="off"
              />
            </div>
          </div>

          {/* Ukuran */}
          <div className={styles.row}>
            <span className={styles.label}>{t('searchFilter.size')}</span>
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
            <span className={styles.label}>{t('searchFilter.dateRange')}</span>
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
            <span className={styles.label}>{t('searchFilter.searchIn')}</span>
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
                  {t('searchFilter.hasAttachment')}
                </label>
                <label className={styles.checkItem} id="filter-exclude-chat-label">
                  <input
                    type="checkbox"
                    checked={excludeChat}
                    onChange={(e) => setExcludeChat(e.target.checked)}
                    id="filter-exclude-chat"
                  />
                  {t('searchFilter.excludeChat')}
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <button className={styles.btnCancel} onClick={handleReset} id="filter-reset-btn">
            {t('searchFilter.clearFilter')}
          </button>
          <button className={styles.btnCancel} onClick={onClose} id="filter-cancel-btn">
            {t('btn.cancel')}
          </button>
          <button className={styles.btnSearch} onClick={handleSearch} id="filter-search-btn">
            <Search size={15} />
            {t('searchFilter.search')}
          </button>
        </div>
      </div>
    </>
  )
}
