import { useState } from 'react'
import useApi from '../../hooks/useApi'
import useTelegram from '../../hooks/useTelegram'
import useHaptic from '../../hooks/useHaptic'

function DrawerItem({ drawer, isLast }) {
  const { impact } = useHaptic()
  const [expanded, setExpanded] = useState(false)
  const preview = drawer.content_preview
    ? drawer.content_preview.slice(0, 200)
    : '(empty)'
  const full = drawer.content_full || drawer.content_preview || '(empty)'
  const type = drawer.metadata?.type
  const importance = drawer.metadata?.importance

  return (
    <div
      onClick={() => { impact('light'); setExpanded(!expanded) }}
      style={{
        cursor: 'pointer',
        padding: '10px 16px 10px 32px',
        borderBottom: isLast ? 'none' : '1px solid var(--border)',
        transition: 'background 150ms ease',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)' }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
    >
      <div
        style={{
          color: 'var(--text-muted)',
          fontSize: '13px',
          lineHeight: 1.5,
          whiteSpace: 'pre-wrap',
        }}
      >
        {expanded ? full : preview}
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          marginTop: '6px',
        }}
      >
        <span
          className="font-mono"
          style={{ fontSize: '11px', color: 'var(--text-secondary)' }}
        >
          {expanded ? 'collapse' : 'expand'}
        </span>
        {type && (
          <span className="font-mono" style={{ fontSize: '11px', color: 'var(--accent-dim)' }}>
            {type}
          </span>
        )}
        {importance && (
          <span className="font-mono" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
            imp:{importance}
          </span>
        )}
      </div>
    </div>
  )
}

function RoomItem({ wing, room, isLast }) {
  const { initData } = useTelegram()
  const { get } = useApi(initData)
  const { impact } = useHaptic()
  const [expanded, setExpanded] = useState(false)
  const [drawers, setDrawers] = useState([])
  const [loaded, setLoaded] = useState(false)

  const handleClick = async () => {
    impact('light')
    if (expanded) {
      setExpanded(false)
      return
    }
    setExpanded(true)
    if (!loaded) {
      const data = await get(
        `/miniapp/palace/drawers?wing=${encodeURIComponent(wing)}&room=${encodeURIComponent(room)}&limit=10`
      )
      if (data?.drawers) {
        setDrawers(Array.isArray(data.drawers) ? data.drawers : Object.values(data.drawers))
        setLoaded(true)
      } else if (Array.isArray(data)) {
        setDrawers(data)
        setLoaded(true)
      }
    }
  }

  return (
    <div
      style={{
        borderBottom: isLast ? 'none' : '1px solid var(--border)',
      }}
    >
      <div
        onClick={handleClick}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 16px',
          cursor: 'pointer',
          transition: 'background 150ms ease',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)' }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
      >
        <span style={{ fontSize: '13px', color: 'var(--text)' }}>
          {room}
        </span>
        <span
          style={{
            fontSize: '14px',
            color: 'var(--text-muted)',
          }}
        >
          {expanded ? '\uFF0D' : '\uFF0B'}
        </span>
      </div>
      {expanded && (
        <div style={{ borderTop: '1px solid var(--border)' }}>
          {drawers.length === 0 ? (
            <div
              style={{
                fontSize: '11px',
                padding: '10px 16px',
                color: 'var(--text-secondary)',
              }}
            >
              {loaded ? 'No drawers' : 'Loading...'}
            </div>
          ) : (
            drawers.map((d, i) => (
              <DrawerItem
                key={d.id || i}
                drawer={d}
                isLast={i === drawers.length - 1}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

function WingItem({ wing, isOpen, onToggle, isLast }) {
  const { initData } = useTelegram()
  const { get } = useApi(initData)
  const { impact } = useHaptic()
  const [rooms, setRooms] = useState([])
  const [loaded, setLoaded] = useState(false)

  const displayName = wing.replace(/^wing_/, '')

  const handleClick = async () => {
    impact('light')
    onToggle()
    if (!isOpen && !loaded) {
      const data = await get(
        `/miniapp/palace/rooms?wing=${encodeURIComponent(wing)}`
      )
      if (data?.rooms) {
        setRooms(Array.isArray(data.rooms) ? data.rooms : Object.keys(data.rooms))
        setLoaded(true)
      } else if (Array.isArray(data)) {
        setRooms(data)
        setLoaded(true)
      }
    }
  }

  return (
    <div
      style={{
        borderBottom: isLast ? 'none' : '1px solid var(--border)',
      }}
    >
      <div
        onClick={handleClick}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 16px',
          cursor: 'pointer',
          transition: 'background 150ms ease',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)' }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
      >
        <span style={{ fontSize: '13px', color: 'var(--accent)' }}>
          {displayName}
        </span>
        <span
          style={{
            fontSize: '14px',
            color: 'var(--text-muted)',
          }}
        >
          {isOpen ? '\uFF0D' : '\uFF0B'}
        </span>
      </div>
      {isOpen && (
        <div style={{ borderTop: '1px solid var(--border)' }}>
          {rooms.length === 0 ? (
            <div
              style={{
                fontSize: '11px',
                padding: '10px 16px',
                color: 'var(--text-secondary)',
              }}
            >
              {loaded ? 'No rooms' : 'Loading...'}
            </div>
          ) : (
            rooms.map((room, i) => (
              <RoomItem
                key={room + i}
                wing={wing}
                room={room}
                isLast={i === rooms.length - 1}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default function WingBrowser({ wings }) {
  const [openWing, setOpenWing] = useState(null)

  if (!wings || wings.length === 0) {
    return (
      <div className="card p-5 text-center">
        <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
          No wings found
        </span>
      </div>
    )
  }

  return (
    <div className="card">
      {wings.map((wing, i) => (
        <WingItem
          key={wing}
          wing={wing}
          isOpen={openWing === wing}
          onToggle={() => setOpenWing(openWing === wing ? null : wing)}
          isLast={i === wings.length - 1}
        />
      ))}
    </div>
  )
}
