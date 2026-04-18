import { useEffect, useState } from 'react'
import useApi from '../../hooks/useApi'
import useTelegram from '../../hooks/useTelegram'
import useHaptic from '../../hooks/useHaptic'

function formatNumber(val) {
  if (val == null) return '\u2014'
  return Number(val).toLocaleString()
}

export default function KGSummary({ initialTab = 'entities' }) {
  const { initData } = useTelegram()
  const { get } = useApi(initData)
  const { impact } = useHaptic()
  const [stats, setStats] = useState(null)
  const [loaded, setLoaded] = useState(false)
  const [tab, setTab] = useState(initialTab)

  useEffect(() => {
    setTab(initialTab)
  }, [initialTab])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      const data = await get('/miniapp/palace/kg')
      if (cancelled) return
      setStats(data || {})
      setLoaded(true)
    }
    load()
    return () => { cancelled = true }
  }, [get])

  const entityCount = stats?.entities ?? stats?.entity_count ?? null
  const tripleCount = stats?.triples ?? stats?.triple_count ?? null

  const tabs = [
    { key: 'entities', label: 'Entities', value: entityCount },
    { key: 'triples', label: 'Triples', value: tripleCount },
  ]

  const handleSelect = (key) => {
    impact('light')
    setTab(key)
  }

  return (
    <div className="card">
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
        {tabs.map((t) => {
          const isActive = tab === t.key
          return (
            <div
              key={t.key}
              onClick={() => handleSelect(t.key)}
              style={{
                flex: 1,
                cursor: 'pointer',
                padding: '14px 12px',
                textAlign: 'center',
                borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                background: isActive ? 'var(--bg-hover)' : 'transparent',
                transition: 'background 150ms ease',
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.currentTarget.style.background = 'var(--bg-hover)'
              }}
              onMouseLeave={(e) => {
                if (!isActive) e.currentTarget.style.background = 'transparent'
              }}
            >
              <div
                style={{
                  fontSize: '11px',
                  letterSpacing: '0.05em',
                  color: isActive ? 'var(--accent)' : 'var(--text-muted)',
                  marginBottom: '4px',
                }}
                className="font-mono"
              >
                {t.label}
              </div>
              <div
                className="font-mono"
                style={{
                  fontSize: '22px',
                  color: 'var(--accent)',
                }}
              >
                {loaded ? formatNumber(t.value) : '\u2014'}
              </div>
            </div>
          )
        })}
      </div>
      <div
        style={{
          padding: '20px 16px',
          fontSize: '12px',
          color: 'var(--text-secondary)',
          textAlign: 'center',
          lineHeight: 1.6,
        }}
      >
        {tab === 'entities'
          ? 'Entity browsing coming soon'
          : 'Triple browsing coming soon'}
      </div>
    </div>
  )
}
