import { useNavigate, useSearchParams } from 'react-router-dom'
import styles from './CategoryTabs.module.css'

const IconInbox = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
    <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5v-3h3.56c.69 1.19 1.97 2 3.45 2s2.75-.81 3.45-2H19v3zm0-5h-4.99c0 1.1-.9 2-2.01 2s-2.01-.9-2.01-2H5V5h14v9z"/>
  </svg>
)

const TABS = [
  { key: 'all',        label: 'Utama',      Icon: IconInbox,  color: '#1a73e8' },
]

export default function CategoryTabs({ activeFilter = 'all' }) {
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
          </button>
        )
      })}
    </div>
  )
}
