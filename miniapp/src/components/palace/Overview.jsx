export default function Overview({ data }) {
  const metrics = [
    { label: 'Wings', key: 'wings', icon: '\u{1F3DB}' },
    { label: 'Rooms', key: 'rooms', icon: '\u{1F6AA}' },
    { label: 'Drawers', key: 'drawers', icon: '\u{1F4E6}' },
    { label: 'KG Entities', key: 'kg_entities', icon: '\u{1F517}' },
    { label: 'KG Triples', key: 'kg_triples', icon: '\u{1F578}' },
  ]

  if (!data) {
    return (
      <div className="card p-4">
        <div
          className="grid gap-3"
          style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}
        >
          {metrics.map(m => (
            <div key={m.key} className="text-center py-2">
              <div
                className="text-xl font-mono"
                style={{ color: 'var(--accent-dim)', opacity: 0.4 }}
              >
                --
              </div>
              <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                {m.icon} {m.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="card p-4">
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}
      >
        {metrics.map(m => (
          <div key={m.key} className="text-center py-2">
            <div
              className="text-xl font-mono font-semibold"
              style={{ color: 'var(--accent)' }}
            >
              {(data[m.key] ?? 0).toLocaleString()}
            </div>
            <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
              {m.icon} {m.label}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
