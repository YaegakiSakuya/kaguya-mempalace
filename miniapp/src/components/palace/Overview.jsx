export default function Overview({ data }) {
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

  return (
    <div className="card" style={{ paddingLeft: '20px', paddingRight: '20px', paddingTop: '8px', paddingBottom: '8px' }}>
      {metrics.map((m, idx) => (
        <div
          key={m.key}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            padding: '12px 0',
            borderBottom: idx === metrics.length - 1 ? 'none' : '1px solid var(--border)',
          }}
        >
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
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
      ))}
    </div>
  )
}
