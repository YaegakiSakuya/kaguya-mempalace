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
    <span className="dots" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
      <span>·</span>
      <span>·</span>
      <span>·</span>
    </span>
  )
}

const SYSTEM_TEXT_STYLE = {
  fontFamily: 'var(--font-mono)',
  fontSize: '12px',
  color: 'var(--text-muted)',
  lineHeight: 1.5,
}

function EventContent({ event }) {
  const { type, data } = event

  if (type === 'processing') {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: '8px',
          width: '100%',
        }}
      >
        <WaitingDots />
        <span style={SYSTEM_TEXT_STYLE}>
          {translateProcessingMessage(data)}
        </span>
      </div>
    )
  }

  if (type === 'thinking') {
    return (
      <div>
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
        <div
          style={{
            fontFamily: 'var(--font-serif)',
            fontSize: '13px',
            color: 'var(--text-muted)',
            whiteSpace: 'pre-wrap',
            lineHeight: 1.6,
          }}
        >
          {data.chunk}
        </div>
      </div>
    )
  }

  if (type === 'replying') {
    return (
      <div>
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            color: 'var(--accent)',
            marginBottom: '4px',
          }}
        >
          replying
        </div>
        <div
          style={{
            fontFamily: 'var(--font-serif)',
            fontSize: '13px',
            color: 'var(--text)',
            whiteSpace: 'pre-wrap',
            lineHeight: 1.6,
          }}
        >
          {data.chunk}
        </div>
      </div>
    )
  }

  if (type === 'tool_call') {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: '8px',
          width: '100%',
        }}
      >
        <span style={{ ...SYSTEM_TEXT_STYLE, color: 'var(--accent)' }}>
          {data.tool}
        </span>
        <span style={{ ...SYSTEM_TEXT_STYLE, fontSize: '11px', color: 'var(--text-secondary)' }}>
          (round {data.round})
        </span>
      </div>
    )
  }

  if (type === 'tool_done') {
    const success = data.success !== false
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: '8px',
          width: '100%',
        }}
      >
        <span
          style={{
            ...SYSTEM_TEXT_STYLE,
            color: success ? 'var(--success)' : 'var(--fail)',
          }}
        >
          {success ? 'done' : 'failed'}
        </span>
        {data.duration_ms != null && (
          <span
            style={{
              marginLeft: 'auto',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--text-secondary)',
            }}
          >
            {data.duration_ms}ms
          </span>
        )}
      </div>
    )
  }

  return null
}

function TimelineEvent({ children }) {
  return (
    <div
      style={{
        position: 'relative',
        paddingBottom: '10px',
        minHeight: '16px',
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: '-16px',
          top: '6px',
          width: '7px',
          height: '7px',
          borderRadius: '50%',
          background: 'var(--accent)',
          border: '1.5px solid var(--bg)',
        }}
      />
      {children}
    </div>
  )
}

function StatSummary({ stats }) {
  const toolCount = Array.isArray(stats.tools) ? stats.tools.length : (stats.tools ? 1 : 0)
  const hasPalaceWrites =
    stats.palace_writes &&
    typeof stats.palace_writes === 'object' &&
    Object.values(stats.palace_writes).some(v => v)

  return (
    <div>
      <div
        style={{
          fontFamily: 'var(--font-mono)',
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
            fontFamily: 'var(--font-mono)',
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

export default function LiveProcess({ status, events, stats, connected }) {
  const bottomRef = useRef(null)
  const mergedEvents = useMemo(() => mergeStreamEvents(events), [events])

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' })
    }
  }, [mergedEvents])

  if (status === 'idle') {
    return (
      <div style={{ padding: '12px 4px 24px 4px', minHeight: '200px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '180px',
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            color: 'var(--text-secondary)',
            opacity: 0.5,
          }}
        >
          waiting
          <span
            style={{
              display: 'inline-block',
              width: '4px',
              height: '4px',
              borderRadius: '1px',
              background: connected ? 'var(--success)' : 'var(--text-secondary)',
              marginLeft: '8px',
            }}
          />
        </div>
      </div>
    )
  }

  return (
    <div style={{ padding: '12px 4px 24px 4px', minHeight: '200px' }}>
      <div style={{ position: 'relative', paddingLeft: '16px' }}>
        <div
          style={{
            position: 'absolute',
            left: '4px',
            top: '6px',
            bottom: '6px',
            width: '1px',
            background: 'var(--border)',
          }}
        />
        {mergedEvents.map((event, i) => (
          <TimelineEvent key={i}>
            <EventContent event={event} />
          </TimelineEvent>
        ))}
        {status === 'done' && stats && (
          <TimelineEvent>
            <StatSummary stats={stats} />
          </TimelineEvent>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
