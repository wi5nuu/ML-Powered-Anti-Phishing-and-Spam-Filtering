import { useNavigate, useSearchParams } from 'react-router-dom'
import styles from './CategoryTabs.module.css'

// SVG icons matching Gmail's tab style
const IconInbox = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
    <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5v-3h3.56c.69 1.19 1.97 2 3.45 2s2.75-.81 3.45-2H19v3zm0-5h-4.99c0 1.1-.9 2-2.01 2s-2.01-.9-2.01-2H5V5h14v9z"/>
  </svg>
)

const IconTag = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
    <path d="M21.41 11.58l-9-9C12.05 2.22 11.55 2 11 2H4c-1.1 0-2 .9-2 2v7c0 .55.22 1.05.59 1.42l9 9c.36.36.86.58 1.41.58.55 0 1.05-.22 1.41-.59l7-7c.37-.36.59-.86.59-1.41 0-.55-.23-1.06-.59-1.42zM5.5 7C4.67 7 4 6.33 4 5.5S4.67 4 5.5 4 7 4.67 7 5.5 6.33 7 5.5 7z"/>
  </svg>
)

const IconPeople = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
    <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
  </svg>
)

const IconShield = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/>
  </svg>
)

const IconCheck = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
  </svg>
)

const TABS = [
  { key: 'all',        label: 'Utama',      Icon: IconInbox,  color: '#1a73e8' },
  { key: 'quarantine', label: 'Karantina',  Icon: IconShield, color: '#ea4335' },
  { key: 'warn',       label: 'Peringatan', Icon: IconTag,    color: '#f29900' },
  { key: 'clean',      label: 'Bersih',     Icon: IconCheck,  color: '#34a853' },
]

export default function CategoryTabs({ activeFilter = 'all', quarantineCount = 0, warnCount = 0, cleanCount = 0 }) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const handleTab = (key) => {
    const params = new URLSearchParams(searchParams)
    if (key === 'all') params.delete('filter')
    else params.set('filter', key)
    params.delete('page')
    navigate(`/inbox?${params.toString()}`)
  }

  return (
    <div className={styles.tabs}>
      {TABS.map((tab) => {
        const isActive = activeFilter === tab.key
        return (
          <button
            key={tab.key}
            className={`${styles.tab} ${isActive ? styles.active : ''}`}
            onClick={() => handleTab(tab.key)}
            style={isActive ? { '--tab-color': tab.color } : {}}
          >
            <span className={styles.iconWrap} style={isActive ? { color: tab.color } : {}}>
              <tab.Icon />
            </span>
            <span className={styles.label}>{tab.label}</span>
            {tab.key === 'all' && quarantineCount > 0 && (
              <span className={styles.badge}>{quarantineCount} baru</span>
            )}
            {tab.key === 'quarantine' && quarantineCount > 0 && (
              <span className={styles.badgeRed}>{quarantineCount}</span>
            )}
            {tab.key === 'warn' && warnCount > 0 && (
              <span className={styles.badgeYellow}>{warnCount}</span>
            )}
            {tab.key === 'clean' && cleanCount > 0 && (
              <span className={styles.badgeGreen}>{cleanCount}</span>
            )}
          </button>
        )
      })}
    </div>
  )
}
