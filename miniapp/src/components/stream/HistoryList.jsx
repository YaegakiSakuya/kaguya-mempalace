import { useState } from 'react'

function formatTime(ts) {
  if (!ts) return '--:--'
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const THINKING_COLLAPSE_THRESHOLD = 500

function HistoryItem({ item }) {
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

  return (
    <div className="card p-3" onClick={() => setExpanded(!expanded)}>
      <div className="flex items-center justify-between cursor-pointer">
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {expanded ? '▾' : '▸'}
          </span>
          <span className="text-sm font-mono" style={{ color: 'var(--accent)' }}>
            {formatTime(item.ts || item.timestamp)}
          </span>
          <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
            {inputTokens.toLocaleString()} IN / {outputTokens.toLocaleString()} OUT
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
            tools:{toolCount}
          </span>
          {elapsed != null && (
            <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
              {(elapsed / 1000).toFixed(1)}s
            </span>
          )}
        </div>
      </div>

      {expanded && (
        <div className="mt-2 pt-2 text-sm" style={{ borderTop: '1px solid var(--border)' }}>
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
                      background: 'linear-gradient(to bottom, rgba(0,0,0,0), var(--bg))',
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
      )}
    </div>
  )
}

export default function HistoryList({ items, onRefresh, loading }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
          历史
        </span>
        <button
          onClick={(e) => { e.stopPropagation(); onRefresh() }}
          disabled={loading}
          className="text-xs px-2 py-0.5 rounded"
          style={{
            color: 'var(--accent)',
            border: '1px solid var(--border)',
            opacity: loading ? 0.5 : 1,
          }}
        >
          {loading ? '...' : '刷新'}
        </button>
      </div>
      <div className="flex flex-col gap-2">
        {items.length === 0 ? (
          <div className="card p-4 text-center">
            <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
              暂无历史记录
            </span>
          </div>
        ) : (
          items.map((item, i) => <HistoryItem key={item.id || i} item={item} />)
        )}
      </div>
    </div>
  )
}
