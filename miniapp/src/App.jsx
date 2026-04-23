import { useState } from 'react'
import useTelegram from './hooks/useTelegram'
import useSSE from './hooks/useSSE'
import useHaptic from './hooks/useHaptic'
import StreamPage from './pages/StreamPage'
import PalacePage from './pages/PalacePage'
import MoonDot from './components/MoonDot'
import { IconStream, IconPalace } from './components/icons'

function Header({ connected }) {
  return (
    <header
      className="px-4 pt-3 pb-2 flex items-center"
      style={{ gap: '12px' }}
    >
      <MoonDot size={14} period={6} connected={connected} />
    </header>
  )
}

function TabBar({ tab, onTabChange }) {
  const { impact } = useHaptic()
  const tabs = ['stream', 'palace']
  return (
    <div
      style={{
        display: 'flex',
        margin: '0 16px 16px',
      }}
    >
      {tabs.map(t => {
        const isActive = tab === t
        const color = isActive ? 'var(--text)' : 'var(--text-muted)'
        return (
          <button
            key={t}
            onClick={() => { impact('light'); onTabChange(t) }}
            aria-label={t}
            aria-pressed={isActive}
            style={{
              position: 'relative',
              flex: 1,
              padding: '12px 0',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              transition: 'color 250ms ease-out',
            }}
          >
            {t === 'stream' ? <IconStream color={color} /> : <IconPalace color={color} />}
            <span
              style={{
                position: 'absolute',
                left: '50%',
                bottom: 0,
                transform: 'translateX(-50%)',
                width: isActive ? '18px' : '0px',
                height: '1px',
                background: 'var(--accent)',
                transition: 'all 250ms ease-out',
              }}
            />
          </button>
        )
      })}
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState('stream')
  const { initData } = useTelegram()
  const sse = useSSE(initData)

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
      <Header connected={sse.connected} />
      <TabBar tab={tab} onTabChange={setTab} />
      {tab === 'stream' ? <StreamPage sse={sse} /> : <PalacePage />}
    </div>
  )
}
