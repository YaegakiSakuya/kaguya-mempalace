import { useEffect, useMemo, useRef } from 'react'

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

function translateProcessingMessage(data) {
  const msg = data?.message || ''
  if (!msg) return data?.step || ''
  if (msg.includes('正在处理消息')) return 'processing...'
  const roundMatch = msg.match(/第\s*(\d+)\s*轮思考中/)
  if (roundMatch) return `thinking (round ${roundMatch[1]})...`
  return msg
}

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

function WaitingDots() {
  return (
    <span className="dots font-mono" style={{ color: 'var(--text-muted)' }}>
      <span>·</span>
      <span>·</span>
      <span>·</span>
    </span>
  )
}

function EventLine({ event }) {
  const { type, data } = event

  if (type === 'processing') {
    return (
      <div className="flex items-start gap-2 py-1">
        <WaitingDots />
        <span style={{ color: 'var(--text-muted)' }}>{translateProcessingMessage(data)}</span>
      </div>
    )
  }

  if (type === 'thinking') {
    return (
      <div className="py-1">
        <div className="text-xs mb-1" style={{ color: 'var(--accent)' }}>thinking</div>
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
        <div className="text-xs mb-1" style={{ color: 'var(--accent)' }}>replying</div>
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
        <span style={{ color: 'var(--accent)', fontSize: '8px', lineHeight: '20px' }}>
          {'\u25CB'}
        </span>
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
        <span className="text-sm" style={{ color: success ? 'var(--success)' : 'var(--fail)' }}>
          {success ? 'done' : 'failed'}
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
  const toolCount = Array.isArray(stats.tools) ? stats.tools.length : (stats.tools ? 1 : 0)
  const hasPalaceWrites =
    stats.palace_writes &&
    typeof stats.palace_writes === 'object' &&
    Object.keys(stats.palace_writes).length > 0

  return (
    <div className="mt-3">
      <div style={{ height: '1px', background: 'var(--border)', margin: '8px 0' }} />
      <div
        style={{
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          fontSize: '11px',
          color: 'var(--text-secondary)',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0 10px',
          lineHeight: 1.6,
        }}
      >
        <span>in {stats.input_tokens?.toLocaleString() ?? '\u2014'}</span>
        <span>{'\u00b7'}</span>
        <span>out {stats.output_tokens?.toLocaleString() ?? '\u2014'}</span>
        <span>{'\u00b7'}</span>
        <span>{toolCount} calls</span>
        <span>{'\u00b7'}</span>
        <span>{stats.elapsed_ms != null ? `${(stats.elapsed_ms / 1000).toFixed(1)}s` : '\u2014'}</span>
        {hasPalaceWrites && (
          <>
            <span>{'\u00b7'}</span>
            <span>{formatPalaceWrites(stats.palace_writes)}</span>
          </>
        )}
      </div>

      {Array.isArray(stats.tools) && stats.tools.length > 0 && (
        <div
          style={{
            fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
            fontSize: '11px',
            color: 'var(--text-secondary)',
            marginTop: '4px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '0 12px',
            lineHeight: 1.6,
          }}
        >
          {stats.tools.map((t, i) => (
            <span key={i}>{stripMempalacePrefix(t)}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function StatusDot({ connected }) {
  return (
    <span
      style={{
        display: 'inline-block',
        width: '4px',
        height: '4px',
        borderRadius: '1px',
        background: connected ? 'var(--success)' : 'var(--fail)',
      }}
    />
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
      <div className="card p-5">
        <div className="flex items-center justify-between">
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            waiting for messages...
          </p>
          <StatusDot connected={connected} />
        </div>
      </div>
    )
  }

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          live
        </span>
        <StatusDot connected={connected} />
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
