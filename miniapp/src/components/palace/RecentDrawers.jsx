import { useEffect, useState } from 'react'
import useApi from '../../hooks/useApi'
import useTelegram from '../../hooks/useTelegram'
import useHaptic from '../../hooks/useHaptic'

function formatTimestamp(meta) {
  const ts = meta?.timestamp || meta?.created_at || meta?.ts
  if (!ts) return null
  if (typeof ts === 'number') {
    try {
      const d = new Date(ts > 1e12 ? ts : ts * 1000)
      return d.toISOString().replace('T', ' ').slice(0, 16)
    } catch {
      return String(ts)
    }
  }
  return String(ts)
}

function DrawerRow({ drawer, isLast }) {
  const { impact } = useHaptic()
  const [active, setActive] = useState(false)
  const preview = (drawer.content_preview || drawer.content_full || '(empty)').slice(0, 120)
  const meta = drawer.metadata || {}
  const wing = meta.wing ? String(meta.wing).replace(/^wing_/, '') : null
  const room = meta.room || null
  const ts = formatTimestamp(meta)

  return (
    <div
      onClick={() => { impact('light'); setActive((v) => !v) }}
      style={{
        cursor: 'pointer',
        padding: '12px 16px',
        borderBottom: isLast ? 'none' : '1px solid var(--border)',
        transition: 'background 150ms ease',
        background: active ? 'var(--bg-hover)' : 'transparent',
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.background = 'var(--bg-hover)'
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.background = 'transparent'
      }}
    >
      <div
        style={{
          fontSize: '13px',
          lineHeight: 1.5,
          color: 'var(--text)',
          whiteSpace: 'pre-wrap',
        }}
      >
        {preview}
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          marginTop: '6px',
          flexWrap: 'wrap',
        }}
      >
        {wing && (
          <span className="font-mono" style={{ fontSize: '11px', color: 'var(--accent-dim)' }}>
            {wing}
          </span>
        )}
        {room && (
          <span className="font-mono" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
            {room}
          </span>
        )}
        {ts && (
          <span className="font-mono" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
            {ts}
          </span>
        )}
      </div>
    </div>
  )
}

export default function RecentDrawers() {
  const { initData } = useTelegram()
  const { get } = useApi(initData)
  const [drawers, setDrawers] = useState([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      const data = await get('/miniapp/palace/drawers?limit=20')
      if (cancelled) return
      let list = []
      if (data?.drawers) {
        list = Array.isArray(data.drawers) ? data.drawers : Object.values(data.drawers)
      } else if (Array.isArray(data)) {
        list = data
      }
      setDrawers(list)
      setLoaded(true)
    }
    load()
    return () => { cancelled = true }
  }, [get])

  if (!loaded) {
    return (
      <div className="card p-5 text-center">
        <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Loading...
        </span>
      </div>
    )
  }

  if (drawers.length === 0) {
    return (
      <div className="card p-5 text-center">
        <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
          No drawers
        </span>
      </div>
    )
  }

  return (
    <div className="card">
      {drawers.map((d, i) => (
        <DrawerRow
          key={d.id || i}
          drawer={d}
          isLast={i === drawers.length - 1}
        />
      ))}
    </div>
  )
}
