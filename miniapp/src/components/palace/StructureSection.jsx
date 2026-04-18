import PalaceSearch from './PalaceSearch'
import WingBrowser from './WingBrowser'

function SectionHeader({ title, subtitle }) {
  return (
    <div
      className="font-mono"
      style={{
        padding: '0 4px',
        fontSize: '12px',
        letterSpacing: '0.1em',
      }}
    >
      <span style={{ color: 'var(--accent)' }}>{title}</span>
      <span style={{ color: 'var(--text-muted)', margin: '0 6px' }}>·</span>
      <span style={{ color: 'var(--text-muted)' }}>{subtitle}</span>
    </div>
  )
}

function SubHeader({ title, note }) {
  return (
    <div
      className="font-mono"
      style={{
        padding: '0 4px',
        fontSize: '11px',
        letterSpacing: '0.08em',
        color: 'var(--accent)',
        display: 'flex',
        alignItems: 'baseline',
        gap: '8px',
      }}
    >
      <span>{title}</span>
      {note && (
        <span style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>{note}</span>
      )}
    </div>
  )
}

function splitWings(wings) {
  const primary = []
  const legacy = []
  for (const w of wings || []) {
    const name = typeof w === 'string' ? w : (w?.name || '')
    if (!name) continue
    const isLegacy = !name.startsWith('wing_') || name === 'wing_kaguya'
    if (isLegacy) legacy.push(w)
    else primary.push(w)
  }
  return { primary, legacy }
}

export default function StructureSection({ wings }) {
  const { primary, legacy } = splitWings(wings)

  return (
    <section className="space-y-4">
      <SectionHeader title="STRUCTURE" subtitle="SKELETON" />
      <PalaceSearch />

      <div className="space-y-2">
        <SubHeader title="WINGS" />
        <WingBrowser wings={primary} emptyLabel="No wings" />
      </div>

      <div className="space-y-2">
        <SubHeader title="LEGACY" note="(read-only)" />
        <WingBrowser wings={legacy} readOnly emptyLabel="No legacy wings" />
      </div>
    </section>
  )
}
