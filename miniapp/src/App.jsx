import { useState } from 'react'
import useTelegram from './hooks/useTelegram'
import useSSE from './hooks/useSSE'
import useHaptic from './hooks/useHaptic'
import StreamPage from './pages/StreamPage'
import PalacePage from './pages/PalacePage'
import { IconStream, IconPalace } from './components/icons'

function MoonPhase({ active }) {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 22 22"
      style={{
        opacity: active ? 0.9 : 0.4,
        transition: 'opacity 600ms ease',
      }}
    >
      <defs>
        <mask id="moon-mask">
          <rect width="22" height="22" fill="white" />
          <circle r="9" cy="11" cx={active ? -9 : 30} fill="black">
            {active && (
              <animate
                attributeName="cx"
                values="-9;31;-9;11"
                keyTimes="0;0.5;0.5001;1"
                dur="8s"
                repeatCount="indefinite"
              />
            )}
          </circle>
        </mask>
      </defs>
      <circle
        cx="11"
        cy="11"
        r="9"
        fill="var(--accent)"
        mask="url(#moon-mask)"
      />
      <circle
        cx="11"
        cy="11"
        r="9"
        fill="none"
        stroke="var(--border-strong)"
        strokeWidth="0.5"
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
      <Header sseStatus={sse.status} />
      <TabBar tab={tab} onTabChange={setTab} />
      {tab === 'stream' ? <StreamPage sse={sse} /> : <PalacePage />}
    </div>
  )
}
