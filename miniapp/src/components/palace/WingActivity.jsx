import { useEffect, useState } from 'react'
import useTelegram from '../../hooks/useTelegram'
import useApi from '../../hooks/useApi'

export default function WingActivity() {
  const { initData } = useTelegram()
  const { get } = useApi(initData)
  const [activity, setActivity] = useState([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      const data = await get('/miniapp/palace/wing-activity?days=7')
      if (cancelled) return
      const list = Array.isArray(data?.activity) ? data.activity.filter((x) => x.count > 0) : []
      setActivity(list)
      setLoaded(true)
    }
    load()
    return () => { cancelled = true }
  }, [get])

  const max = activity.reduce((acc, x) => Math.max(acc, x.count || 0), 0) || 1

  return (
    <div className="card">
      <div
        className="font-mono"
        style={{
          padding: '10px 12px',
          fontSize: '11px',
          color: 'var(--accent)',
          letterSpacing: '0.08em',
          borderBottom: '1px solid var(--border)',
        }}
      >
        WING ACTIVITY · 7D
      </div>
      {!loaded ? (
        <div
          className="text-sm text-center"
          style={{ padding: '16px', color: 'var(--text-muted)' }}
        >
          loading...
        </div>
      ) : activity.length === 0 ? (
        <div
          className="text-sm text-center"
          style={{ padding: '16px', color: 'var(--text-muted)' }}
        >
          no writes in last 7 days
        </div>
      ) : (
        activity.map((a, i) => {
          const displayName = (a.wing || '').replace(/^wing_/, '')
          const pct = Math.max(4, Math.round((a.count / max) * 100))
          return (
            <div
              key={a.wing || i}
              style={{
                padding: '8px 12px',
                borderBottom: i === activity.length - 1 ? 'none' : '1px solid var(--border)',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                minWidth: 0,
              }}
            >
              <span
                className="font-mono"
                style={{
                  fontSize: '11px',
                  color: 'var(--text)',
                  width: '72px',
                  flexShrink: 0,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {displayName}
              </span>
              <div
                style={{
                  flex: 1,
                  height: '6px',
                  background: 'var(--bg-hover)',
                  borderRadius: '1px',
                  minWidth: 0,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width: `${pct}%`,
                    height: '100%',
                    background: 'var(--accent-dim)',
                  }}
                />
              </div>
              <span
                className="font-mono"
                style={{
                  fontSize: '11px',
                  color: 'var(--text-muted)',
                  width: '24px',
                  textAlign: 'right',
                  flexShrink: 0,
                }}
              >
                {a.count}
              </span>
            </div>
          )
        })
      )}
    </div>
  )
}
