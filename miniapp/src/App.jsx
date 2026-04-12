import { useState } from 'react'
import StreamPage from './pages/StreamPage'
import PalacePage from './pages/PalacePage'

function Header() {
  return (
    <header className="px-4 pt-4 pb-2">
      <h1 className="text-lg font-semibold" style={{ color: 'var(--accent)' }}>
        Kaguya · MemPalace
      </h1>
    </header>
  )
}

function TabBar({ tab, onTabChange }) {
  const tabs = [
    { key: 'stream', label: '消息流' },
    { key: 'palace', label: '宫殿' },
  ]
  return (
    <div className="flex gap-2 px-4 pb-3">
      {tabs.map(t => (
        <button
          key={t.key}
          onClick={() => onTabChange(t.key)}
          className="px-4 py-1.5 text-sm font-medium rounded-full transition-colors"
          style={{
            background: tab === t.key ? 'var(--accent)' : 'transparent',
            color: tab === t.key ? '#FDF6EC' : 'var(--text-muted)',
            border: tab === t.key ? 'none' : '1px solid var(--border)',
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState('stream')
  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
      <Header />
      <TabBar tab={tab} onTabChange={setTab} />
      {tab === 'stream' ? <StreamPage /> : <PalacePage />}
    </div>
  )
}
