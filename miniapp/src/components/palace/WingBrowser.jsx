import { useState } from 'react'
import useApi from '../../hooks/useApi'
import useTelegram from '../../hooks/useTelegram'

function DrawerItem({ drawer }) {
  const [expanded, setExpanded] = useState(false)
  const preview = drawer.content_preview
    ? drawer.content_preview.slice(0, 200)
    : '(empty)'
  const full = drawer.content_full || drawer.content_preview || '(empty)'
  const type = drawer.metadata?.type
  const importance = drawer.metadata?.importance

  return (
    <div
      className="px-3 py-2 rounded-lg cursor-pointer"
      style={{ background: 'rgba(255,255,255,0.3)' }}
      onClick={() => setExpanded(!expanded)}
    >
      <div
        style={{
          color: 'var(--text-muted)',
          fontSize: '0.8rem',
          lineHeight: 1.5,
          whiteSpace: 'pre-wrap',
        }}
      >
        {expanded ? full : preview}
      </div>
      <div className="flex items-center gap-2 mt-1">
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {expanded ? '▾ 收起全文' : '▸ 查看全文'}
        </span>
        {type && (
          <span className="text-xs font-mono" style={{ color: 'var(--accent-dim)' }}>
            {type}
          </span>
        )}
        {importance && (
          <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
            imp:{importance}
          </span>
        )}
      </div>
    </div>
  )
}

function RoomItem({ wing, room }) {
  const { initData } = useTelegram()
  const { get } = useApi(initData)
  const [expanded, setExpanded] = useState(false)
  const [drawers, setDrawers] = useState([])
  const [loaded, setLoaded] = useState(false)

  const handleClick = async () => {
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
    <div>
      <div
        className="flex items-center gap-2 px-3 py-2 cursor-pointer"
        onClick={handleClick}
      >
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {expanded ? '▾' : '▸'}
        </span>
        <span className="text-sm" style={{ color: 'var(--text)' }}>
          {room}
        </span>
      </div>
      {expanded && (
        <div className="pl-6 pr-2 pb-2 flex flex-col gap-1.5">
          {drawers.length === 0 ? (
            <div className="text-xs px-3 py-1" style={{ color: 'var(--text-secondary)' }}>
              {loaded ? 'No drawers' : 'Loading...'}
            </div>
          ) : (
            drawers.map((d, i) => <DrawerItem key={d.id || i} drawer={d} />)
          )}
        </div>
      )}
    </div>
  )
}

function WingItem({ wing, isOpen, onToggle }) {
  const { initData } = useTelegram()
  const { get } = useApi(initData)
  const [rooms, setRooms] = useState([])
  const [loaded, setLoaded] = useState(false)

  const displayName = wing.replace(/^wing_/, '')

  const handleClick = async () => {
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
    <div className="card">
      <div
        className="flex items-center gap-2 px-4 py-3 cursor-pointer"
        onClick={handleClick}
      >
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {isOpen ? '▾' : '▸'}
        </span>
        <span className="text-sm font-medium" style={{ color: 'var(--accent)' }}>
          {displayName}
        </span>
      </div>
      {isOpen && (
        <div
          className="pb-2"
          style={{ borderTop: '1px solid var(--border)' }}
        >
          {rooms.length === 0 ? (
            <div className="text-xs px-4 py-2" style={{ color: 'var(--text-secondary)' }}>
              {loaded ? 'No rooms' : 'Loading...'}
            </div>
          ) : (
            rooms.map((room, i) => (
              <RoomItem key={room + i} wing={wing} room={room} />
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
      <div>
        <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
          Wings
        </span>
        <div className="card p-4 mt-2 text-center">
          <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
            No wings found
          </span>
        </div>
      </div>
    )
  }

  return (
    <div>
      <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
        Wings
      </span>
      <div className="flex flex-col gap-2 mt-2">
        {wings.map(wing => (
          <WingItem
            key={wing}
            wing={wing}
            isOpen={openWing === wing}
            onToggle={() => setOpenWing(openWing === wing ? null : wing)}
          />
        ))}
      </div>
    </div>
  )
}
