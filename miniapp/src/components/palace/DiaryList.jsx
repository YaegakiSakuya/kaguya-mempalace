import { useState } from 'react'

function DiaryEntry({ entry }) {
  const [expanded, setExpanded] = useState(false)

  const title = entry.date || entry.title || null
  const content = entry.content || entry.text || ''

  return (
    <div className="card p-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
      {title && (
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium" style={{ color: 'var(--accent)' }}>
            {title}
          </span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {expanded ? '\u25BE' : '\u25B8'}
          </span>
        </div>
      )}
      {!title && (
        <span
          className="text-xs float-right"
          style={{ color: 'var(--text-muted)' }}
        >
          {expanded ? '\u25BE' : '\u25B8'}
        </span>
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
      <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
        辉夜日记
      </span>
      <div className="flex flex-col gap-2 mt-2">
        {!entries || entries.length === 0 ? (
          <div className="card p-4 text-center">
            <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
              暂无日记
            </span>
          </div>
        ) : (
          entries.map((entry, i) => (
            <DiaryEntry key={entry.id || i} entry={entry} />
          ))
        )}
      </div>
    </div>
  )
}
