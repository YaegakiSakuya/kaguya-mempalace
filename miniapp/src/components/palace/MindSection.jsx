import DiaryList from './DiaryList'
import RecentConcepts from './RecentConcepts'

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

export default function MindSection({ diary }) {
  return (
    <section className="space-y-4">
      <SectionHeader title="MIND" subtitle="INNER LIFE" />
      <DiaryList entries={diary} />
      <RecentConcepts />
    </section>
  )
}
