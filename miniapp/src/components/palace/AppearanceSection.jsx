import { useTheme } from '../../theme/ThemeContext'
import useHaptic from '../../hooks/useHaptic'

const TONE_SWATCHES = [
  { id: 'parchment', hex: '#ede4d1' },
  { id: 'ivory',     hex: '#f4efe6' },
  { id: 'rice',      hex: '#efeae0' },
  { id: 'bone',      hex: '#f5f2ec' },
  { id: 'linen',     hex: '#ece7dc' },
  { id: 'sand',      hex: '#e9dfcc' },
  { id: 'mist',      hex: '#e7e7e2' },
  { id: 'pearl',     hex: '#ecebe7' },
  { id: 'celadon',   hex: '#e2e6de' },
  { id: 'rose',      hex: '#ebe2de' },
  { id: 'dusk',      hex: '#1c1814' },
  { id: 'ink',       hex: '#14171a' },
]

export default function AppearanceSection() {
  const { state, setTone } = useTheme()
  const { impact } = useHaptic()

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div
        className="font-mono"
        style={{
          padding: '0 4px',
          fontSize: '12px',
          letterSpacing: '0.1em',
        }}
      >
        <span style={{ color: 'var(--accent)' }}>APPEARANCE</span>
      </div>
      <div className="card" style={{ padding: '14px 16px' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(6, 1fr)',
            gap: '8px',
          }}
        >
          {TONE_SWATCHES.map(({ id, hex }) => {
            const active = state.tone === id
            const isDark = id === 'dusk' || id === 'ink'
            return (
              <button
                key={id}
                onClick={() => { impact('light'); setTone(id) }}
                title={id}
                aria-label={`Switch to ${id} tone`}
                aria-pressed={active}
                style={{
                  aspectRatio: '1',
                  borderRadius: '2px',
                  background: hex,
                  cursor: 'pointer',
                  padding: 0,
                  border: active
                    ? '2px solid var(--accent)'
                    : `1px solid ${isDark ? 'rgba(255,255,255,0.15)' : 'var(--border-strong)'}`,
                  boxShadow: active
                    ? `inset 0 0 0 2px ${isDark ? '#000' : '#fff'}`
                    : 'none',
                  transition: 'border-color 150ms ease, box-shadow 150ms ease',
                }}
              />
            )
          })}
        </div>
        <div
          className="font-mono"
          style={{
            marginTop: '10px',
            fontSize: '10px',
            color: 'var(--text-secondary)',
            letterSpacing: '0.08em',
            textAlign: 'center',
          }}
        >
          {state.tone}
        </div>
      </div>
    </section>
  )
}
