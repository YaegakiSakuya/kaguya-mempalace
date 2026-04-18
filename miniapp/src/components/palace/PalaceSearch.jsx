import { useState } from 'react'
import useTelegram from '../../hooks/useTelegram'
import useApi from '../../hooks/useApi'
import useHaptic from '../../hooks/useHaptic'

function ResultRow({ item, isLast }) {
  const { impact } = useHaptic()
  const [expanded, setExpanded] = useState(false)
  const meta = item.metadata || {}
  const wing = meta.wing ? String(meta.wing).replace(/^wing_/, '') : ''
  const room = meta.room || ''
  const preview = (item.content_preview || '').slice(0, 100)
  const full = item.content_full || item.content_preview || ''
  const dist = item.distance
  const sim = typeof dist === 'number' ? Math.max(0, 1 - dist).toFixed(2) : null

  return (
    <div
      onClick={() => { impact('light'); setExpanded(!expanded) }}
      style={{
        cursor: 'pointer',
        padding: '10px 12px',
        borderBottom: isLast ? 'none' : '1px solid var(--border)',
        transition: 'background 150ms ease',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)' }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: '8px',
          marginBottom: '4px',
          minWidth: 0,
        }}
      >
        {wing && (
          <span
            className="font-mono"
            style={{ fontSize: '11px', color: 'var(--accent-dim)', flexShrink: 0 }}
          >
            {wing}{room ? `/${room}` : ''}
          </span>
        )}
        {sim != null && (
          <span
            className="font-mono"
            style={{
              marginLeft: 'auto',
              fontSize: '11px',
              color: 'var(--text-secondary)',
              flexShrink: 0,
            }}
          >
            sim {sim}
          </span>
        )}
      </div>
      <div
        style={{
          fontSize: '13px',
          color: 'var(--text)',
          lineHeight: 1.5,
          whiteSpace: 'pre-wrap',
        }}
      >
        {expanded ? full : preview}
      </div>
    </div>
  )
}

export default function PalaceSearch() {
  const { initData } = useTelegram()
  const { get } = useApi(initData)
  const { impact } = useHaptic()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)

  const runSearch = async () => {
    const q = query.trim()
    if (!q) return
    impact('medium')
    setLoading(true)
    const data = await get(`/miniapp/palace/search?q=${encodeURIComponent(q)}&limit=10`)
    setLoading(false)
    setResults(Array.isArray(data) ? data : [])
  }

  const clear = () => {
    setQuery('')
    setResults(null)
  }

  return (
    <div className="space-y-3">
      <div style={{ display: 'flex', gap: '8px' }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              runSearch()
            }
          }}
          placeholder="Search the palace..."
          style={{
            flex: 1,
            minWidth: 0,
            background: 'var(--bg-card)',
            color: 'var(--text)',
            border: '1px solid var(--border)',
            borderRadius: '2px',
            padding: '8px 10px',
            fontSize: '13px',
            fontFamily: 'var(--font-mono)',
          }}
        />
        {query && (
          <button
            onClick={clear}
            style={{
              background: 'transparent',
              color: 'var(--text-muted)',
              border: '1px solid var(--border)',
              borderRadius: '2px',
              padding: '4px 10px',
              fontSize: '12px',
              cursor: 'pointer',
              fontFamily: 'var(--font-mono)',
            }}
          >
            clear
          </button>
        )}
      </div>
      {loading && (
        <div
          className="card text-center"
          style={{ padding: '12px', color: 'var(--text-muted)', fontSize: '12px' }}
        >
          searching...
        </div>
      )}
      {!loading && results != null && (
        results.length === 0 ? (
          <div
            className="card text-center"
            style={{ padding: '12px', color: 'var(--text-muted)', fontSize: '12px' }}
          >
            no results
          </div>
        ) : (
          <div className="card">
            {results.map((r, i) => (
              <ResultRow key={r.id || i} item={r} isLast={i === results.length - 1} />
            ))}
          </div>
        )
      )}
    </div>
  )
}
