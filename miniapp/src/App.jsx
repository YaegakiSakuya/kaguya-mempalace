import { useState } from 'react'
import useTelegram from './hooks/useTelegram'
import useSSE from './hooks/useSSE'
import StreamPage from './pages/StreamPage'
import PalacePage from './pages/PalacePage'

function ECGLine({ active }) {
  return (
    <svg width="80" height="24" viewBox="0 0 80 24" style={{
      opacity: active ? 0.8 : 0.4,
      transition: 'opacity 0.5s ease',
    }}>
      <path
        d="M0,12 L15,12 L20,4 L25,20 L30,8 L35,16 L40,12 L80,12"
        fill="none"
        stroke="var(--accent)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray="160"
      >
        <animate
          attributeName="stroke-dashoffset"
          from="160"
          to="0"
          dur={active ? '1.5s' : '3s'}
          repeatCount="indefinite"
        />
      </path>
    </svg>
  )
}

function Header({ sseStatus }) {
  return (
    <header className="px-4 pt-4 pb-2 flex items-center justify-between">
      <h1 className="text-lg font-semibold" style={{ color: 'var(--accent)' }}>
        Kaguya · MemPalace
      </h1>
      <ECGLine active={sseStatus !== 'idle' && sseStatus !== 'done'} />
    </header>
  )
}

function TabBar({ tab, onTabChange }) {
  return (
    <div style={{
      background: 'var(--bg-card)',
      backdropFilter: 'blur(12px)',
      WebkitBackdropFilter: 'blur(12px)',
      borderRadius: '9999px',
      padding: '4px',
      display: 'flex',
      margin: '0 16px 16px',
    }}>
      {['stream', 'palace'].map(t => (
        <button
          key={t}
          onClick={() => onTabChange(t)}
          style={{
            flex: 1,
            padding: '8px 0',
            borderRadius: '9999px',
            border: 'none',
            background: tab === t ? 'var(--accent)' : 'transparent',
            color: tab === t ? '#fff' : 'var(--text-muted)',
            fontSize: '0.85rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'background 0.2s ease, color 0.2s ease',
          }}
        >
          {t === 'stream' ? '消息流' : '宫殿'}
        </button>
      ))}
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
