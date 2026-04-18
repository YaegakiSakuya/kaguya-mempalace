import { useEffect, useState } from 'react'
import useTelegram from '../../hooks/useTelegram'
import useApi from '../../hooks/useApi'

function entityLabel(e) {
  if (!e) return ''
  if (typeof e === 'string') return e
  return e.name || e.entity || e.id || ''
}

function tripleLabel(t) {
  if (!t) return ''
  if (typeof t === 'string') return t
  const s = t.subject || t.s || ''
  const p = t.predicate || t.p || ''
  const o = t.object || t.o || ''
  return [s, p, o].filter(Boolean).join(' → ')
}

export default function RecentConcepts() {
  const { initData } = useTelegram()
  const { get } = useApi(initData)
  const [entities, setEntities] = useState([])
  const [triples, setTriples] = useState([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      const data = await get('/miniapp/palace/kg/timeline?limit=5')
      if (cancelled) return
      setEntities(Array.isArray(data?.entities) ? data.entities : [])
      setTriples(Array.isArray(data?.triples) ? data.triples : [])
      setLoaded(true)
    }
    load()
    return () => { cancelled = true }
  }, [get])

  const hasAny = entities.length > 0 || triples.length > 0

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
        RECENT CONCEPTS
      </div>
      {!loaded ? (
        <div
          className="text-sm text-center"
          style={{ padding: '16px', color: 'var(--text-muted)' }}
        >
          loading...
        </div>
      ) : !hasAny ? (
        <div
          className="text-sm text-center"
          style={{ padding: '16px', color: 'var(--text-muted)' }}
        >
          no recent concepts
        </div>
      ) : (
        <>
          {entities.length > 0 && (
            <div>
              <div
                className="font-mono"
                style={{
                  padding: '8px 12px 4px 12px',
                  fontSize: '10px',
                  color: 'var(--text-muted)',
                  letterSpacing: '0.08em',
                }}
              >
                NEW ENTITIES
              </div>
              {entities.map((e, i) => (
                <div
                  key={i}
                  style={{
                    padding: '6px 12px',
                    fontSize: '12px',
                    color: 'var(--text)',
                    fontFamily: 'var(--font-mono)',
                    borderBottom: i === entities.length - 1 && triples.length === 0 ? 'none' : '1px solid var(--border)',
                  }}
                >
                  {entityLabel(e)}
                </div>
              ))}
            </div>
          )}
          {triples.length > 0 && (
            <div>
              <div
                className="font-mono"
                style={{
                  padding: '8px 12px 4px 12px',
                  fontSize: '10px',
                  color: 'var(--text-muted)',
                  letterSpacing: '0.08em',
                }}
              >
                NEW RELATIONS
              </div>
              {triples.map((t, i) => (
                <div
                  key={i}
                  style={{
                    padding: '6px 12px',
                    fontSize: '12px',
                    color: 'var(--text)',
                    fontFamily: 'var(--font-mono)',
                    borderBottom: i === triples.length - 1 ? 'none' : '1px solid var(--border)',
                    whiteSpace: 'normal',
                    wordBreak: 'break-word',
                  }}
                >
                  {tripleLabel(t)}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
