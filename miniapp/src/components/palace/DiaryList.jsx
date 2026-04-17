import { useState } from 'react'
import useHaptic from '../../hooks/useHaptic'

function DiaryEntry({ entry, isLast }) {
  const { impact } = useHaptic()
  const [expanded, setExpanded] = useState(false)

  const title = entry.date || entry.title || null
  const content = entry.content || entry.text || ''

  return (
    <div
      onClick={() => { impact('light'); setExpanded(!expanded) }}
      style={{
        cursor: 'pointer',
        padding: '12px 16px',
        borderBottom: isLast ? 'none' : '1px solid var(--border)',
        transition: 'background 150ms ease',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)' }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
    >
      {title && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '6px',
          }}
        >
          <span className="font-mono" style={{ fontSize: '12px', color: 'var(--accent)' }}>
            {title}
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
      )}
      <div
        className="text-sm leading-relaxed"
        style={{
          color: 'var(--text)',
          ...(!expanded && {
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }),
        }}
      >
        {content}
      </div>
    </div>
  )
}

export default function DiaryList({ entries }) {
  return (
    <div>
      {!entries || entries.length === 0 ? (
        <div className="card p-5 text-center">
          <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
            no entries
          </span>
        </div>
      ) : (
        <div className="card">
          {entries.map((entry, i) => (
            <DiaryEntry
              key={entry.id || i}
              entry={entry}
              isLast={i === entries.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}
