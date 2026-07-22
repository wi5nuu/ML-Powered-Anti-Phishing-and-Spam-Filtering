import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { Inbox, Tag, Users, Info, MessageSquare } from 'lucide-react'
import styles from './CategoryTabs.module.css'

const TABS = [
  { key: 'all',        label: 'Utama',        Icon: Inbox,          color: '#0b57d0' },
  { key: 'promotions', label: 'Promosi',      Icon: Tag,            color: '#1e8e3e' },
  { key: 'social',     label: 'Sosial',       Icon: Users,          color: '#0b57d0' },
  { key: 'updates',    label: 'Info Terbaru', Icon: Info,           color: '#e37400' },
  { key: 'forums',     label: 'Forum',        Icon: MessageSquare,  color: '#444746' },
]

export default function CategoryTabs() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const currentTab = searchParams.get('category') || searchParams.get('filter') || 'all'

  const handleTab = (key) => {
    const params = new URLSearchParams(searchParams)
    if (key === 'all') {
      params.delete('filter')
      params.delete('category')
    } else {
      params.set('category', key)
    }
    params.delete('page')
    // Preserve the current path (e.g. /mail/:id/inbox) instead of hardcoding /inbox
    navigate(`${location.pathname}?${params.toString()}`)
  }

  return (
    <div className={styles.tabs}>
      {TABS.map((tab) => {
        const isActive = currentTab === tab.key
        const Icon = tab.Icon
        return (
          <button
            key={tab.key}
            className={`${styles.tab} ${isActive ? styles.active : ''}`}
            onClick={() => handleTab(tab.key)}
            style={isActive ? { '--tab-color': tab.color } : {}}
          >
            <span className={styles.iconWrap} style={{ color: isActive ? tab.color : 'inherit' }}>
              <Icon size={18} />
            </span>
            <span className={styles.label}>{tab.label}</span>
          </button>
        )
      })}
    </div>
  )
}

