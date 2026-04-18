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

function DiaryHeader() {
  return (
    <div
      className="font-mono"
      style={{
        padding: '12px 16px',
        fontSize: '12px',
        color: 'var(--accent)',
        letterSpacing: '0.05em',
        borderBottom: '1px solid var(--border)',
      }}
    >
      DIARY · 辉夜日记
    </div>
  )
}

export default function DiaryList({ entries }) {
  return (
    <div className="card">
      <DiaryHeader />
      {!entries || entries.length === 0 ? (
        <div
          className="text-sm text-center"
          style={{ padding: '20px', color: 'var(--text-muted)' }}
        >
          no entries
        </div>
      ) : (
        entries.map((entry, i) => (
          <DiaryEntry
            key={entry.id || i}
            entry={entry}
            isLast={i === entries.length - 1}
          />
        ))
      )}
    </div>
  )
}
