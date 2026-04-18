import { useEffect, useState } from 'react'
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
    </div>
  )
}

function FlatRoomItem({ wing, room, isLast }) {
  const { initData } = useTelegram()
  const { get } = useApi(initData)
  const { impact } = useHaptic()
  const [expanded, setExpanded] = useState(false)
  const [drawers, setDrawers] = useState([])
  const [loaded, setLoaded] = useState(false)

  const displayWing = wing.replace(/^wing_/, '')

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
    <div style={{ borderBottom: isLast ? 'none' : '1px solid var(--border)' }}>
      <div
        onClick={handleClick}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          cursor: 'pointer',
          transition: 'background 150ms ease',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)' }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
      >
        <span style={{ fontSize: '13px', color: 'var(--text)' }}>
          <span className="font-mono" style={{ color: 'var(--accent)' }}>
            {displayWing}
          </span>
          <span style={{ color: 'var(--text-secondary)', margin: '0 6px' }}>/</span>
          <span>{room}</span>
        </span>
        <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>
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

export default function AllRoomsFlat({ wings }) {
  const { initData } = useTelegram()
  const { get } = useApi(initData)
  const [pairs, setPairs] = useState([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      if (!wings || wings.length === 0) {
        setPairs([])
        setLoaded(true)
        return
      }
      const results = await Promise.all(
        wings.map(async (wing) => {
          const data = await get(
            `/miniapp/palace/rooms?wing=${encodeURIComponent(wing)}`
          )
          let rooms = []
          if (data?.rooms) {
            rooms = Array.isArray(data.rooms) ? data.rooms : Object.keys(data.rooms)
          } else if (Array.isArray(data)) {
            rooms = data
          }
          return rooms.map((room) => ({ wing, room }))
        })
      )
      if (!cancelled) {
        setPairs(results.flat())
        setLoaded(true)
      }
    }
    load()
    return () => { cancelled = true }
  }, [wings, get])

  if (!loaded) {
    return (
      <div className="card p-5 text-center">
        <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Loading...
        </span>
      </div>
    )
  }

  if (pairs.length === 0) {
    return (
      <div className="card p-5 text-center">
        <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
          No rooms found
        </span>
      </div>
    )
  }

  return (
    <div className="card">
      {pairs.map((p, i) => (
        <FlatRoomItem
          key={`${p.wing}/${p.room}/${i}`}
          wing={p.wing}
          room={p.room}
          isLast={i === pairs.length - 1}
        />
      ))}
    </div>
  )
}
