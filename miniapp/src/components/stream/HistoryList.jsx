import { useState } from 'react'

function formatTime(ts) {
  if (!ts) return '--:--'
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function HistoryItem({ item }) {
  const [expanded, setExpanded] = useState(false)

  const inputTokens = item.total_prompt_tokens ?? item.input_tokens ?? item.prompt_tokens ?? 0
  const outputTokens = item.total_completion_tokens ?? item.output_tokens ?? item.completion_tokens ?? 0
  const elapsed = item.elapsed_ms
  const rounds = item.total_rounds ?? item.rounds ?? 0
  const tools = item.tools_called || item.tools || []

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
        {elapsed != null && (
          <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
            {(elapsed / 1000).toFixed(1)}s
          </span>
        )}
      </div>

      {expanded && (
        <div className="mt-2 pt-2 text-sm" style={{ borderTop: '1px solid var(--border)' }}>
          {tools.length > 0 && (
            <div className="mb-2">
              <span style={{ color: 'var(--text-muted)' }}>工具: </span>
              <span className="font-mono text-xs">
                {Array.isArray(tools) ? tools.join(', ') : tools}
              </span>
            </div>
          )}
          {item.palace_writes && (
            <div className="mb-2">
              <span style={{ color: 'var(--text-muted)' }}>宫殿写入: </span>
              <span className="font-mono text-xs">{item.palace_writes}</span>
            </div>
          )}
          {item.response_preview && (
            <div
              className="text-xs leading-relaxed mt-1"
              style={{ color: 'var(--text-muted)' }}
            >
              {item.response_preview}
            </div>
          )}
          {!tools.length && !item.palace_writes && !item.response_preview && (
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
