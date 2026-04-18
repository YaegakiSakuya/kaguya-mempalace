import { useEffect, useState } from 'react'
import useTelegram from '../../hooks/useTelegram'
import useApi from '../../hooks/useApi'

const TOOL_LABELS = {
  mempalace_add_drawer: '+ drawer',
  mempalace_search: 'search',
  mempalace_delete_drawer: '- drawer',
  mempalace_kg_add: '+ kg',
  mempalace_kg_query: '? kg',
  mempalace_kg_timeline: 'kg timeline',
  mempalace_kg_stats: 'kg stats',
  mempalace_kg_invalidate: '~ kg',
  mempalace_diary_read: 'diary r',
  mempalace_diary_write: 'diary w',
  mempalace_check_duplicate: 'dup?',
  mempalace_list_wings: 'wings',
  mempalace_list_rooms: 'rooms',
  mempalace_get_taxonomy: 'taxonomy',
  mempalace_status: 'status',
  mempalace_traverse: 'traverse',
  mempalace_find_tunnels: 'tunnels',
  mempalace_graph_stats: 'graph',
  mempalace_get_aaak_spec: 'aaak',
}

function toolLabel(toolName) {
  if (!toolName) return '\u2014'
  if (TOOL_LABELS[toolName]) return TOOL_LABELS[toolName]
  return toolName.replace(/^mempalace_/, '')
}

function formatHHMM(ts) {
  if (!ts) return '\u2014'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return '\u2014'
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

function extractPreview(item) {
  const args = item.arguments || item.args || {}
  if (!args || typeof args !== 'object') return ''
  const tool = item.tool_name
  if (tool === 'mempalace_search' || tool === 'mempalace_kg_query') {
    return (args.query || args.entity || '').toString()
  }
  if (tool === 'mempalace_add_drawer') {
    return (args.content_summary || args.content || args.type || '').toString()
  }
  if (tool === 'mempalace_kg_add') {
    const s = args.subject || ''
    const p = args.predicate || ''
    const o = args.object || ''
    return [s, p, o].filter(Boolean).join(' → ')
  }
  if (tool === 'mempalace_diary_write') {
    return (args.content || args.entry || '').toString()
  }
  // fallback: first string-ish value
  for (const v of Object.values(args)) {
    if (typeof v === 'string' && v) return v
  }
  return ''
}

function ActivityRow({ item, isLast }) {
  const tool = item.tool_name
  const args = item.arguments || item.args || {}
  const rawWing = (args && typeof args === 'object' && args.wing) ? String(args.wing) : ''
  const rawRoom = (args && typeof args === 'object' && args.room) ? String(args.room) : ''
  const wing = rawWing.replace(/^wing_/, '')
  const preview = extractPreview(item).slice(0, 50)

  return (
    <div
      style={{
        padding: '8px 12px',
        borderBottom: isLast ? 'none' : '1px solid var(--border)',
        display: 'flex',
        alignItems: 'baseline',
        gap: '8px',
        minWidth: 0,
      }}
    >
      <span
        className="font-mono"
        style={{
          fontSize: '11px',
          color: 'var(--text-secondary)',
          flexShrink: 0,
        }}
      >
        {formatHHMM(item.ts || item.timestamp)}
      </span>
      <span
        className="font-mono"
        style={{
          fontSize: '11px',
          color: 'var(--accent)',
          background: 'var(--bg-hover)',
          padding: '1px 6px',
          borderRadius: '2px',
          flexShrink: 0,
          whiteSpace: 'nowrap',
        }}
      >
        {toolLabel(tool)}
      </span>
      {(wing || rawRoom) && (
        <span
          className="font-mono"
          style={{
            fontSize: '11px',
            color: 'var(--accent-dim)',
            flexShrink: 0,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            maxWidth: '40%',
          }}
        >
          {wing}{rawRoom ? `/${rawRoom}` : ''}
        </span>
      )}
      {preview && (
        <span
          style={{
            fontSize: '12px',
            color: 'var(--text-muted)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            flex: 1,
            minWidth: 0,
          }}
        >
          {preview}
        </span>
      )}
    </div>
  )
}

export default function RecentActivity() {
  const { initData } = useTelegram()
  const { get } = useApi(initData)
  const [items, setItems] = useState([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      const data = await get('/miniapp/history/tools?limit=15')
      if (cancelled) return
      const list = Array.isArray(data?.items) ? data.items : []
      setItems(list)
      setLoaded(true)
    }
    load()
    return () => { cancelled = true }
  }, [get])

  return (
    <div className="card">
      <div
        className="font-mono"
        style={{
          padding: '10px 12px',
          fontSize: '11px',
          color: 'var(--accent)',
          letterSpacing: '0.08em',
          borderBottom: '1px solid var(--border)',
        }}
      >
        RECENT ACTIVITY
      </div>
      {!loaded ? (
        <div
          className="text-sm text-center"
          style={{ padding: '16px', color: 'var(--text-muted)' }}
        >
          loading...
        </div>
      ) : items.length === 0 ? (
        <div
          className="text-sm text-center"
          style={{ padding: '16px', color: 'var(--text-muted)' }}
        >
          no activity
        </div>
      ) : (
        items.map((it, i) => (
          <ActivityRow key={i} item={it} isLast={i === items.length - 1} />
        ))
      )}
    </div>
  )
}
