import { useState } from 'react'
import { IconRefresh } from '../icons'
import useHaptic from '../../hooks/useHaptic'

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

function HistoryItem({ item, index, isLast }) {
  const { impact } = useHaptic()
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
  const replyPreviewSummary = normalizedReply.slice(0, 80) + (normalizedReply.length > 80 ? '…' : '')

  return (
    <div style={{ borderBottom: isLast ? 'none' : '1px solid var(--border)' }}>
      {/* ─── collapsed row: [index] [time] [preview] [chevron] ─── */}
      <button
        onClick={() => { impact('light'); setExpanded(!expanded) }}
        style={{
          width: '100%',
          textAlign: 'left',
          display: 'flex',
          gap: '10px',
          alignItems: 'center',
          padding: '9px 2px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: 'inherit',
          fontFamily: 'inherit',
        }}
      >
        <span
          style={{
            flexShrink: 0,
            width: '18px',
            fontFamily: 'var(--font-mono)',
            fontSize: '9px',
            color: 'var(--accent)',
            letterSpacing: '0.1em',
          }}
        >
          {String(index).padStart(2, '0')}
        </span>
        <span
          style={{
            flexShrink: 0,
            width: '52px',
            fontFamily: 'var(--font-mono)',
            fontSize: '8.5px',
            color: 'var(--text-secondary)',
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
          }}
        >
          {formatTime(item.ts || item.timestamp)}
        </span>
        <span
          style={{
            flex: 1,
            minWidth: 0,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            fontFamily: 'var(--font-serif)',
            fontSize: '12px',
            color: 'var(--text-muted)',
          }}
        >
          {normalizedReply
            ? replyPreviewSummary
            : <span style={{ color: 'var(--text-secondary)' }}>no reply</span>}
        </span>
        <svg
          width="7"
          height="7"
          viewBox="0 0 9 9"
          style={{
            flexShrink: 0,
            opacity: 0.55,
            transition: 'transform 0.25s',
            transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
          }}
        >
          <path d="M2 1L6 4.5L2 8" stroke="var(--text-muted)" strokeWidth="1" fill="none" strokeLinecap="round" />
        </svg>
      </button>

      {/* ─── expanded detail ─── */}
      <div
        style={{
          maxHeight: expanded ? '9999px' : '0',
          overflow: 'hidden',
          transition: 'max-height 0.28s ease',
        }}
      >
        <div
          style={{
            padding: '2px 0 14px 74px',
            fontSize: '13px',
            lineHeight: 1.75,
          }}
        >
          {thinkingPreview && (
            <div style={{ marginBottom: '12px' }}>
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  color: 'var(--accent)',
                  marginBottom: '4px',
                }}
              >
                thinking
              </div>
              <div style={{ position: 'relative' }}>
                <div
                  style={{
                    fontFamily: 'var(--font-serif)',
                    fontSize: '12px',
                    lineHeight: 1.6,
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
                      background: 'linear-gradient(to bottom, transparent, var(--bg))',
                    }}
                  />
                )}
              </div>
              {thinkingNeedsCollapse && (
                <button
                  onClick={(e) => { e.stopPropagation(); impact('light'); setThinkingExpanded(!thinkingExpanded) }}
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
            <div style={{ marginBottom: '4px' }}>
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  color: 'var(--accent)',
                  marginBottom: '4px',
                }}
              >
                reply
              </div>
              <div
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: '13px',
                  lineHeight: 1.6,
                  color: 'var(--text)',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {responsePreview}
              </div>
            </div>
          )}

          {!toolCount && !hasPalaceWrites && !thinkingPreview && !responsePreview && (
            <div
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                color: 'var(--text-secondary)',
              }}
            >
              no details
            </div>
          )}

          {(toolCount > 0 || rounds != null || hasPalaceWrites) && (
            <div
              style={{
                marginTop: '12px',
                paddingTop: '10px',
                borderTop: '1px solid var(--border)',
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                color: 'var(--text-secondary)',
                lineHeight: 1.6,
              }}
            >
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0 10px' }}>
                <span>in {inputTokens.toLocaleString()}</span>
                <span>{'·'}</span>
                <span>out {outputTokens.toLocaleString()}</span>
                {rounds != null && (
                  <>
                    <span>{'·'}</span>
                    <span>{rounds} rounds</span>
                  </>
                )}
                {hasPalaceWrites && (
                  <>
                    <span>{'·'}</span>
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
  )
}

export default function HistoryList({ items, onRefresh, loading }) {
  const { impact } = useHaptic()
  const [drawerOpen, setDrawerOpen] = useState(false)

  return (
    <div style={{ borderTop: '1px solid var(--border-strong)', paddingTop: '10px' }}>
      {/* ─── drawer header ─── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 0',
        }}
      >
        <button
          onClick={() => { impact('light'); setDrawerOpen(!drawerOpen) }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            flex: 1,
            background: 'transparent',
            border: 'none',
            padding: 0,
            cursor: 'pointer',
            color: 'inherit',
          }}
        >
          <svg
            width="9"
            height="9"
            viewBox="0 0 9 9"
            style={{
              transition: 'transform 0.25s',
              transform: drawerOpen ? 'rotate(90deg)' : 'rotate(0deg)',
            }}
          >
            <path d="M2 1L6 4.5L2 8" stroke="var(--text-muted)" strokeWidth="1" fill="none" strokeLinecap="round" />
          </svg>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '9px',
              letterSpacing: '0.32em',
              textTransform: 'uppercase',
              color: 'var(--accent)',
            }}
          >
            history
          </span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '9px',
              letterSpacing: '0.2em',
              color: 'var(--text-secondary)',
            }}
          >
            · {items.length}
          </span>
          <div style={{ flex: 1, height: '1px', background: 'var(--border)' }} />
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); impact('medium'); onRefresh() }}
          disabled={loading}
          aria-label="refresh history"
          style={{
            background: 'transparent',
            border: 'none',
            padding: '4px',
            cursor: loading ? 'default' : 'pointer',
            opacity: loading ? 0.3 : 0.5,
            transition: 'opacity 150ms ease',
            flexShrink: 0,
          }}
        >
          <IconRefresh color="var(--text-muted)" />
        </button>
      </div>

      {/* ─── drawer content ─── */}
      <div
        style={{
          maxHeight: drawerOpen ? '9999px' : '0',
          overflow: 'hidden',
          transition: 'max-height 0.35s ease',
        }}
      >
        <div style={{ paddingTop: '4px' }}>
          {items.length === 0 ? (
            <div
              style={{
                padding: '16px 0',
                textAlign: 'center',
                fontFamily: 'var(--font-serif)',
                fontSize: '12.5px',
                fontStyle: 'italic',
                color: 'var(--text-muted)',
              }}
            >
              no history
            </div>
          ) : (
            items.map((item, i) => (
              <HistoryItem
                key={item.id || i}
                item={item}
                index={i + 1}
                isLast={i === items.length - 1}
              />
            ))
          )}
        </div>
      </div>
    </div>
  )
}
