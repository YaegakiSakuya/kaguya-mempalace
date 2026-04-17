import { useState } from 'react'

function stripMempalacePrefix(name) {
  if (typeof name !== 'string') return String(name ?? '')
  return name.replace(/^mempalace_/, '')
}

function formatPalaceWrites(writes) {
  if (!writes || typeof writes !== 'object') return ''
  return Object.entries(writes)
    .filter(([, v]) => v)
    .map(([k, v]) => `${v} ${k}`)
    .join(' / ')
}

function formatTime(ts) {
  if (!ts) return '--:--'
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const THINKING_COLLAPSE_THRESHOLD = 500

function HistoryItem({ item, isLast }) {
  const [expanded, setExpanded] = useState(false)
  const [thinkingExpanded, setThinkingExpanded] = useState(false)

  const inputTokens = item.total_prompt_tokens ?? item.input_tokens ?? item.prompt_tokens ?? 0
  const outputTokens = item.total_completion_tokens ?? item.output_tokens ?? item.completion_tokens ?? 0
  const rounds = item.total_rounds ?? item.rounds ?? null
  const tools = item.tools_called || item.tools || []
  const toolCount = Array.isArray(tools) ? tools.length : (tools ? 1 : 0)
  const rawPalaceWrites = item.palace_writes
  const hasPalaceWrites = rawPalaceWrites && (
    typeof rawPalaceWrites === 'string'
      ? rawPalaceWrites.trim() !== ''
      : typeof rawPalaceWrites === 'object' && Object.keys(rawPalaceWrites).length > 0
  )
  const thinkingPreview = item.thinking_text || item.thinking_preview || null
  const thinkingNeedsCollapse = (thinkingPreview || '').length > THINKING_COLLAPSE_THRESHOLD
  const thinkingCollapsed = thinkingNeedsCollapse && !thinkingExpanded
  const responsePreview = item.response_preview || ''
  const totalTokens = inputTokens + outputTokens
  const summary = item.turn_type || item.summary || responsePreview || '—'

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      style={{
        cursor: 'pointer',
        borderBottom: isLast ? 'none' : '1px solid var(--border)',
        transition: 'background 150ms ease',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)' }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '12px 16px',
        }}
      >
        <span
          className="font-mono"
          style={{ fontSize: '11px', color: 'var(--text-secondary)', flexShrink: 0 }}
        >
          {formatTime(item.ts || item.timestamp)}
        </span>
        <span
          style={{
            flex: 1,
            fontSize: '13px',
            color: 'var(--text)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {summary}
        </span>
        <span
          className="font-mono"
          style={{ fontSize: '11px', color: 'var(--text-muted)', flexShrink: 0 }}
        >
          {toolCount}t · {totalTokens.toLocaleString()}
        </span>
        <span
          style={{
            fontSize: '14px',
            color: 'var(--text-muted)',
            flexShrink: 0,
            width: '14px',
            textAlign: 'center',
          }}
        >
          {expanded ? '\uFF0D' : '\uFF0B'}
        </span>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateRows: expanded ? '1fr' : '0fr',
          transition: 'grid-template-rows 300ms ease-out',
        }}
      >
        <div style={{ overflow: 'hidden', minHeight: 0 }}>
        <div
          className="text-sm"
          style={{
            padding: '0 16px 20px 16px',
            borderTop: '1px solid var(--border)',
            paddingTop: '12px',
          }}
        >
          {thinkingPreview && (
            <div className="mb-3">
              <div className="text-xs mb-1" style={{ color: 'var(--accent)' }}>thinking</div>
              <div style={{ position: 'relative' }}>
                <div
                  className="text-xs leading-relaxed"
                  style={{
                    color: 'var(--text-muted)',
                    whiteSpace: 'pre-wrap',
                    maxHeight: thinkingCollapsed ? '200px' : 'none',
                    overflow: thinkingCollapsed ? 'hidden' : 'visible',
                  }}
                >
                  {thinkingPreview}
                </div>
                {thinkingCollapsed && (
                  <div
                    style={{
                      position: 'absolute',
                      left: 0,
                      right: 0,
                      bottom: 0,
                      height: '60px',
                      pointerEvents: 'none',
                      background: 'linear-gradient(to bottom, rgba(0,0,0,0), var(--bg-card))',
                    }}
                  />
                )}
              </div>
              {thinkingNeedsCollapse && (
                <button
                  onClick={(e) => { e.stopPropagation(); setThinkingExpanded(!thinkingExpanded) }}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: '4px 0 0 0',
                    color: 'var(--accent)',
                    fontSize: '12px',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                  }}
                >
                  {thinkingExpanded ? 'collapse' : 'expand'}
                </button>
              )}
            </div>
          )}

          {responsePreview && (
            <div className="mb-1">
              <div className="text-xs mb-1" style={{ color: 'var(--accent)' }}>reply</div>
              <div
                className="text-sm leading-relaxed"
                style={{ color: 'var(--text)', whiteSpace: 'pre-wrap' }}
              >
                {responsePreview}
              </div>
            </div>
          )}

          {!toolCount && !hasPalaceWrites && !thinkingPreview && !responsePreview && (
            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              no details
            </div>
          )}

          {(toolCount > 0 || rounds != null || hasPalaceWrites) && (
            <div
              style={{
                marginTop: '12px',
                paddingTop: '10px',
                borderTop: '1px solid var(--border)',
                fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                fontSize: '11px',
                color: 'var(--text-secondary)',
                lineHeight: 1.6,
              }}
            >
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0 10px' }}>
                {rounds != null && <span>{rounds} rounds</span>}
                {hasPalaceWrites && (
                  <>
                    {rounds != null && <span>{'\u00b7'}</span>}
                    <span>{typeof rawPalaceWrites === 'string' ? rawPalaceWrites : formatPalaceWrites(rawPalaceWrites)}</span>
                  </>
                )}
              </div>
              {tools && (Array.isArray(tools) ? tools.length > 0 : String(tools).trim() !== '') && (
                <div style={{ marginTop: '4px', display: 'flex', flexWrap: 'wrap', gap: '0 12px' }}>
                  {(Array.isArray(tools) ? tools : String(tools).split(/\s*,\s*/)).map((t, i) => (
                    <span key={i}>{stripMempalacePrefix(t)}</span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
        </div>
      </div>
    </div>
  )
}

export default function HistoryList({ items, onRefresh, loading }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          history
        </span>
        <button
          onClick={(e) => { e.stopPropagation(); onRefresh() }}
          disabled={loading}
          style={{
            background: 'transparent',
            border: 'none',
            padding: 0,
            fontSize: '12px',
            fontFamily: 'inherit',
            color: 'var(--text-muted)',
            cursor: loading ? 'default' : 'pointer',
            opacity: loading ? 0.5 : 1,
            transition: 'color 150ms ease',
          }}
          onMouseEnter={(e) => { if (!loading) e.currentTarget.style.color = 'var(--accent)' }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
        >
          {loading ? '...' : 'refresh'}
        </button>
      </div>
      {items.length === 0 ? (
        <div className="card p-5 text-center">
          <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
            no history
          </span>
        </div>
      ) : (
        <div className="card">
          {items.map((item, i) => (
            <HistoryItem
              key={item.id || i}
              item={item}
              isLast={i === items.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}
