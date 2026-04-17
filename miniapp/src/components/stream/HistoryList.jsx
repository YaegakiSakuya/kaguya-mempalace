import { useState } from 'react'
import { IconRefresh } from '../icons'

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
  if (!ts) return ''
  const then = new Date(ts)
  if (isNaN(then.getTime())) return ''
  const now = new Date()
  const diffMs = Math.max(0, now.getTime() - then.getTime())
  const diffMin = Math.floor(diffMs / 60000)
  const diffHr = Math.floor(diffMs / 3600000)

  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHr < 24 && then.toDateString() === now.toDateString()) return `${diffHr}h ago`

  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (then.toDateString() === yesterday.toDateString()) return 'yesterday'

  const sameYear = then.getFullYear() === now.getFullYear()
  const opts = sameYear
    ? { month: 'short', day: 'numeric' }
    : { year: 'numeric', month: 'short', day: 'numeric' }
  return then.toLocaleDateString('en-US', opts).toLowerCase()
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
      : typeof rawPalaceWrites === 'object' && Object.values(rawPalaceWrites).some(v => v)
  )
  const thinkingPreview = item.thinking_text || item.thinking_preview || null
  const thinkingNeedsCollapse = (thinkingPreview || '').length > THINKING_COLLAPSE_THRESHOLD
  const thinkingCollapsed = thinkingNeedsCollapse && !thinkingExpanded
  const responsePreview = item.response_preview || ''
  const rawReply = responsePreview || item.reply_text || ''
  const normalizedReply = rawReply.replace(/\s+/g, ' ').trim()
  const replyPreviewSummary = normalizedReply.slice(0, 80) + (normalizedReply.length > 80 ? '\u2026' : '')

  return (
    <div
      style={{
        position: 'relative',
        borderBottom: isLast ? 'none' : '1px solid',
        borderBottomColor: expanded ? 'var(--border-strong)' : 'var(--border)',
        transition: 'border-bottom-color 200ms ease',
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          bottom: 0,
          width: expanded ? '2px' : '0px',
          background: 'var(--accent)',
          transition: 'width 200ms ease',
        }}
      />
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          cursor: 'pointer',
          padding: '12px 16px',
          transition: 'background 150ms ease',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)' }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
      >
        <div
          style={{
            fontSize: '13px',
            color: 'var(--text)',
            lineHeight: 1.5,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            marginBottom: '4px',
          }}
        >
          {normalizedReply
            ? replyPreviewSummary
            : <span style={{ color: 'var(--text-secondary)' }}>no reply</span>}
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            color: 'var(--text-muted)',
          }}
        >
          <span>{formatTime(item.ts || item.timestamp)}</span>
          {toolCount > 0 && (
            <>
              <span>{'\u00b7'}</span>
              <span>{toolCount} {toolCount === 1 ? 'tool' : 'tools'}</span>
            </>
          )}
        </div>
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
            padding: '12px 16px 20px 16px',
            borderTop: '1px solid var(--border)',
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
                <span>in {inputTokens.toLocaleString()}</span>
                <span>{'\u00b7'}</span>
                <span>out {outputTokens.toLocaleString()}</span>
                {rounds != null && (
                  <>
                    <span>{'\u00b7'}</span>
                    <span>{rounds} rounds</span>
                  </>
                )}
                {hasPalaceWrites && (
                  <>
                    <span>{'\u00b7'}</span>
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
    <div style={{ position: 'relative' }}>
      <button
        onClick={(e) => { e.stopPropagation(); onRefresh() }}
        disabled={loading}
        aria-label="refresh history"
        style={{
          position: 'absolute',
          top: 0,
          right: 0,
          background: 'transparent',
          border: 'none',
          padding: '6px',
          cursor: loading ? 'default' : 'pointer',
          opacity: loading ? 0.3 : 0.6,
          transition: 'opacity 150ms ease',
          zIndex: 1,
        }}
        onMouseEnter={(e) => { if (!loading) e.currentTarget.style.opacity = '1' }}
        onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.6' }}
      >
        <IconRefresh color="var(--text-muted)" />
      </button>
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
