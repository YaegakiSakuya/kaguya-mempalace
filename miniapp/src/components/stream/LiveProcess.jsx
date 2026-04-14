import { useEffect, useMemo, useRef } from 'react'

function mergeStreamEvents(events) {
  const merged = []

  for (const event of events.filter(e => e.type !== 'done')) {
    if (event.type === 'thinking' || event.type === 'replying') {
      const last = merged[merged.length - 1]
      const chunk = event.data?.chunk || ''

      if (last && last.type === event.type) {
        last.data = {
          ...(last.data || {}),
          chunk: (last.data?.chunk || '') + chunk,
        }
      } else {
        merged.push({
          ...event,
          data: {
            ...(event.data || {}),
            chunk,
          },
        })
      }
      continue
    }

    merged.push(event)
  }

  return merged
}

function EventLine({ event }) {
  const { type, data } = event

  if (type === 'processing') {
    return (
      <div className="flex items-start gap-2 py-1">
        <span>⏳</span>
        <span style={{ color: 'var(--text-muted)' }}>{data.message || data.step}</span>
      </div>
    )
  }

  if (type === 'thinking') {
    return (
      <div className="py-1">
        <div className="text-xs mb-1" style={{ color: 'var(--accent)' }}>思考中</div>
        <div
          className="text-sm"
          style={{ color: 'var(--text-muted)', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}
        >
          {data.chunk}
        </div>
      </div>
    )
  }

  if (type === 'replying') {
    return (
      <div className="py-1">
        <div className="text-xs mb-1" style={{ color: 'var(--accent)' }}>回复生成中</div>
        <div
          className="text-sm"
          style={{ color: 'var(--text)', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}
        >
          {data.chunk}
        </div>
      </div>
    )
  }

  if (type === 'tool_call') {
    return (
      <div className="flex items-start gap-2 py-1">
        <span>🔧</span>
        <span>
          <span className="font-mono text-sm" style={{ color: 'var(--accent)' }}>
            {data.tool}
          </span>
          <span className="text-xs ml-2" style={{ color: 'var(--text-muted)' }}>
            (round {data.round})
          </span>
        </span>
      </div>
    )
  }

  if (type === 'tool_done') {
    const success = data.success !== false
    return (
      <div className="flex items-start gap-2 py-0.5 pl-6">
        <span style={{ color: success ? 'var(--success)' : 'var(--fail)' }}>
          {success ? '✓' : '✗'}
        </span>
        <span className="text-sm" style={{ color: success ? 'var(--success)' : 'var(--fail)' }}>
          {success ? '完成' : '失败'}
          {data.duration_ms != null && (
            <span className="font-mono ml-1">({data.duration_ms}ms)</span>
          )}
        </span>
      </div>
    )
  }

  return null
}

function StatCard({ stats }) {
  const palaceWrites = typeof stats.palace_writes === 'object'
    ? JSON.stringify(stats.palace_writes)
    : stats.palace_writes
  const toolCount = Array.isArray(stats.tools) ? stats.tools.length : (stats.tools ? 1 : 0)

  return (
    <div className="mt-2 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
      <div className="text-xs font-medium mb-2" style={{ color: 'var(--text-muted)' }}>
        ── 完成 ──
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <div>
          <span style={{ color: 'var(--text-muted)' }}>输入: </span>
          <span className="font-mono" style={{ color: 'var(--accent)' }}>
            {stats.input_tokens?.toLocaleString()}
          </span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>输出: </span>
          <span className="font-mono" style={{ color: 'var(--accent)' }}>
            {stats.output_tokens?.toLocaleString()}
          </span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>工具: </span>
          <span className="font-mono">{toolCount}次</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>耗时: </span>
          <span className="font-mono">
            {stats.elapsed_ms != null ? `${(stats.elapsed_ms / 1000).toFixed(1)}s` : '-'}
          </span>
        </div>
        {palaceWrites && (
          <div className="col-span-2">
            <span style={{ color: 'var(--text-muted)' }}>宫殿写入: </span>
            <span className="font-mono text-sm">{palaceWrites}</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default function LiveProcess({ status, events, stats, connected }) {
  const scrollRef = useRef(null)
  const mergedEvents = useMemo(() => mergeStreamEvents(events), [events])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [mergedEvents])

  if (status === 'idle') {
    return (
      <div className="card p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            等待消息...
          </p>
          <span
            className="w-2 h-2 rounded-full"
            style={{ background: connected ? 'var(--success)' : 'var(--fail)' }}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
          实时
        </span>
        <span
          className="w-2 h-2 rounded-full"
          style={{ background: connected ? 'var(--success)' : 'var(--fail)' }}
        />
      </div>
      <div ref={scrollRef} className="max-h-64 overflow-y-auto">
        {mergedEvents.map((event, i) => (
          <EventLine key={i} event={event} />
        ))}
      </div>
      {status === 'done' && stats && <StatCard stats={stats} />}
    </div>
  )
}
