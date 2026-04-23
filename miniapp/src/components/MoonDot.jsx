import { useState, useEffect, useId } from 'react'

export default function MoonDot({ size = 22, period = 6, connected = true }) {
  const [phase, setPhase] = useState(0)
  const uid = useId()

  useEffect(() => {
    if (!connected) return
    let raf
    const start = performance.now()
    const tick = (t) => {
      setPhase(((t - start) / 1000) % period / period)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [connected, period])

  const r = size / 2
  let shadowX
  if (phase < 0.5) {
    shadowX = -2 * r * (phase * 2)
  } else {
    shadowX = 2 * r - 2 * r * ((phase - 0.5) * 2)
  }

  return (
    <div
      title={connected ? 'SSE · connected' : 'SSE · offline'}
      style={{
        width: size,
        height: size,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow: 'visible' }}>
        <defs>
          <radialGradient id={`glow-${uid}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.28" />
            <stop offset="60%" stopColor="var(--accent)" stopOpacity="0.08" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </radialGradient>
          <clipPath id={`clip-${uid}`}>
            <circle cx={r} cy={r} r={r - 0.3} />
          </clipPath>
        </defs>
        {connected && (
          <circle cx={r} cy={r} r={r * 1.9} fill={`url(#glow-${uid})`} />
        )}
        <circle
          cx={r} cy={r} r={r - 0.6}
          fill="none"
          stroke={connected ? 'var(--accent-dim)' : 'var(--text-muted)'}
          strokeWidth="0.8"
          opacity={connected ? 0.55 : 0.7}
        />
        {connected && (
          <g clipPath={`url(#clip-${uid})`}>
            <circle cx={r} cy={r} r={r - 0.3} fill="var(--accent)" />
            <circle cx={r * 0.7} cy={r * 0.7} r={r * 0.9} fill="var(--accent-dim)" opacity="0.35" />
            <circle cx={r + shadowX} cy={r} r={r - 0.3} fill="var(--bg)" />
          </g>
        )}
      </svg>
    </div>
  )
}
