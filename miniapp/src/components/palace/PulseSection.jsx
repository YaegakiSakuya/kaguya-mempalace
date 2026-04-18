import Overview from './Overview'
import RecentActivity from './RecentActivity'
import WingActivity from './WingActivity'

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

export default function PulseSection({ overview }) {
  return (
    <section className="space-y-4">
      <SectionHeader title="PULSE" subtitle="HEARTBEAT" />
      <Overview data={overview} />
      <RecentActivity />
      <WingActivity />
    </section>
  )
}
