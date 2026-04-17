import { useState } from 'react'

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
  const elapsed = item.elapsed_ms
  const rounds = item.total_rounds ?? item.rounds ?? 0
  const tools = item.tools_called || item.tools || []
  const toolCount = Array.isArray(tools) ? tools.length : (tools ? 1 : 0)
  const palaceWrites = typeof item.palace_writes === 'object'
    ? JSON.stringify(item.palace_writes)
    : item.palace_writes
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
          maxHeight: expanded ? '2000px' : '0px',
          overflow: 'hidden',
          transition: 'max-height 300ms ease-out',
        }}
      >
        <div
          className="text-sm"
          style={{
            padding: '0 16px 20px 16px',
            borderTop: '1px solid var(--border)',
            paddingTop: '12px',
          }}
        >
          {toolCount > 0 && (
            <div className="mb-2">
              <span style={{ color: 'var(--text-muted)' }}>工具: </span>
              <span className="font-mono text-xs">
                {Array.isArray(tools) ? tools.join(', ') : String(tools)}
              </span>
            </div>
          )}

          {rounds != null && (
            <div className="mb-2">
              <span style={{ color: 'var(--text-muted)' }}>轮次: </span>
              <span className="font-mono text-xs">{rounds}</span>
            </div>
          )}

          <div className="mb-2">
            <span style={{ color: 'var(--text-muted)' }}>tokens: </span>
            <span className="font-mono text-xs">
              {inputTokens.toLocaleString()} IN / {outputTokens.toLocaleString()} OUT
            </span>
            {elapsed != null && (
              <span className="font-mono text-xs" style={{ marginLeft: '12px', color: 'var(--text-muted)' }}>
                {(elapsed / 1000).toFixed(1)}s
              </span>
            )}
          </div>

          {palaceWrites && (
            <div className="mb-2">
              <span style={{ color: 'var(--text-muted)' }}>宫殿写入: </span>
              <span className="font-mono text-xs">{palaceWrites}</span>
            </div>
          )}

          {thinkingPreview && (
            <div className="mb-3">
              <div className="text-xs mb-1" style={{ color: 'var(--accent)' }}>思维链</div>
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
                  {thinkingExpanded ? '收起' : '展开全部'}
                </button>
              )}
            </div>
          )}

          {responsePreview && (
            <div className="mb-1">
              <div className="text-xs mb-1" style={{ color: 'var(--accent)' }}>回复</div>
              <div
                className="text-sm leading-relaxed"
                style={{ color: 'var(--text)', whiteSpace: 'pre-wrap' }}
              >
                {responsePreview}
              </div>
            </div>
          )}

          {!toolCount && !palaceWrites && !thinkingPreview && !responsePreview && (
            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              无详细信息
            </div>
          )}
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
          历史
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
          {loading ? '...' : '刷新'}
        </button>
      </div>
      {items.length === 0 ? (
        <div className="card p-5 text-center">
          <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
            暂无历史记录
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
