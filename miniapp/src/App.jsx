import { useState } from 'react'
import useTelegram from './hooks/useTelegram'
import useSSE from './hooks/useSSE'
import StreamPage from './pages/StreamPage'
import PalacePage from './pages/PalacePage'

function ECGLine({ active }) {
  return (
    <span
      style={{
        display: 'inline-block',
        width: '80px',
        height: '0.5px',
        minHeight: '1px',
        background: 'var(--accent)',
        opacity: 0.3,
        animation: active ? 'pulse-line 3s ease-in-out infinite' : 'none',
      }}
    />
  )
}

function Header({ sseStatus }) {
  return (
    <header
      className="px-4 pt-3 pb-2 flex items-center"
      style={{ gap: '12px' }}
    >
      <ECGLine active={sseStatus !== 'idle' && sseStatus !== 'done'} />
    </header>
  )
}

function TabBar({ tab, onTabChange }) {
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
        return (
          <button
            key={t}
            onClick={() => onTabChange(t)}
            style={{
              position: 'relative',
              flex: 1,
              padding: '10px 0',
              background: 'transparent',
              border: 'none',
              color: isActive ? 'var(--text)' : 'var(--text-muted)',
              fontSize: '14px',
              fontWeight: 400,
              fontFamily: 'inherit',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'color 250ms ease-out',
            }}
          >
            {t === 'stream' ? 'stream' : 'palace'}
            <span
              style={{
                position: 'absolute',
                left: '50%',
                bottom: 0,
                transform: 'translateX(-50%)',
                width: isActive ? '20px' : '0px',
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
      <Header sseStatus={sse.status} />
      <TabBar tab={tab} onTabChange={setTab} />
      {tab === 'stream' ? <StreamPage sse={sse} /> : <PalacePage />}
    </div>
  )
}
