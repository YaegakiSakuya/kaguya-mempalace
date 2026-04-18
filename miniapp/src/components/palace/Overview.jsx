import useHaptic from '../../hooks/useHaptic'

export default function Overview({ data, selected, onSelect }) {
  const { impact } = useHaptic()

  const metrics = [
    { label: 'Wings', key: 'wings' },
    { label: 'Rooms', key: 'rooms' },
    { label: 'Drawers', key: 'drawers' },
    { label: 'KG Entities', key: 'kg_entities' },
    { label: 'KG Triples', key: 'kg_triples' },
  ]

  const formatValue = (val) => {
    if (val == null) return '\u2014'
    return Number(val).toLocaleString()
  }

  const handleClick = (key) => {
    impact('light')
    onSelect?.(key)
  }

  return (
    <div className="card" style={{ paddingTop: '4px', paddingBottom: '4px' }}>
      {metrics.map((m, idx) => {
        const isActive = selected === m.key
        return (
          <div
            key={m.key}
            onClick={() => handleClick(m.key)}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
              padding: '12px 16px 12px 13px',
              borderLeft: isActive ? '3px solid var(--accent)' : '3px solid transparent',
              borderBottom: idx === metrics.length - 1 ? 'none' : '1px solid var(--border)',
              cursor: 'pointer',
              background: isActive ? 'var(--bg-hover)' : 'transparent',
              transition: 'background 150ms ease',
            }}
            onMouseEnter={(e) => {
              if (!isActive) e.currentTarget.style.background = 'var(--bg-hover)'
            }}
            onMouseLeave={(e) => {
              if (!isActive) e.currentTarget.style.background = 'transparent'
            }}
          >
            <span
              style={{
                fontSize: '12px',
                color: isActive ? 'var(--text)' : 'var(--text-muted)',
              }}
            >
              {m.label}
            </span>
            <span
              className="font-mono"
              style={{
                fontSize: '24px',
                color: 'var(--accent)',
                fontWeight: 400,
              }}
            >
              {data ? formatValue(data[m.key]) : '\u2014'}
            </span>
          </div>
        )
      })}
    </div>
  )
}
