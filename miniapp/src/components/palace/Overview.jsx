export default function Overview({ data }) {
  const metrics = [
    { label: 'drawers', key: 'drawers' },
    { label: 'wings', key: 'wings' },
    { label: 'rooms', key: 'rooms' },
    { label: 'kg entities', key: 'kg_entities' },
    { label: 'kg triples', key: 'kg_triples' },
  ]

  const formatValue = (val) => {
    if (val == null) return '\u2014'
    return Number(val).toLocaleString()
  }

  return (
    <div
      className="card"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'stretch',
        padding: '4px 0',
      }}
    >
      {metrics.map((m, idx) => (
        <div
          key={m.key}
          style={{
            flex: '1 1 20%',
            minWidth: '64px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '10px 4px',
            borderRight: idx < metrics.length - 1 ? '1px solid var(--border)' : 'none',
          }}
        >
          <span
            className="font-mono"
            style={{
              fontSize: '10px',
              color: 'var(--text-muted)',
              letterSpacing: '0.05em',
              textAlign: 'center',
              lineHeight: 1.3,
            }}
          >
            {m.label}
          </span>
          <span
            className="font-mono"
            style={{
              fontSize: '20px',
              color: 'var(--accent)',
              fontWeight: 400,
              marginTop: '4px',
              lineHeight: 1.2,
            }}
          >
            {data ? formatValue(data[m.key]) : '\u2014'}
          </span>
        </div>
      ))}
    </div>
  )
}
