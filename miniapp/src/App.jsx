import { useState } from 'react'
import useTelegram from './hooks/useTelegram'
import useSSE from './hooks/useSSE'
import StreamPage from './pages/StreamPage'
import PalacePage from './pages/PalacePage'

function MoonPhase({ active }) {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      style={{
        opacity: active ? 0.85 : 0.35,
        transition: 'opacity 600ms ease',
      }}
    >
      <defs>
        <mask id="moon-phase-mask">
          <rect width="24" height="24" fill="black" />
          <circle cx="12" cy="12" r="10" fill="white" />
        </mask>
      </defs>
      <circle
        cx="12"
        cy="12"
        r="10"
        fill="none"
        stroke="var(--border-strong)"
        strokeWidth="0.75"
      />
      <ellipse
        cx="12"
        cy="12"
        rx="10"
        ry="10"
        fill="var(--accent)"
        mask="url(#moon-phase-mask)"
        style={{
          animation: active ? 'moon-phase 8s ease-in-out infinite' : 'none',
          transformOrigin: '12px 12px',
        }}
      />
    </svg>
  )
}

function Header({ sseStatus }) {
  return (
    <header
      className="px-4 pt-3 pb-2 flex items-center"
      style={{ gap: '12px' }}
    >
      <MoonPhase active={sseStatus !== 'idle' && sseStatus !== 'done'} />
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
