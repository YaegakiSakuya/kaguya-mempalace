export function IconStream({ size = 14, color = 'currentColor' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none">
      <line x1="2" y1="4" x2="8" y2="4" stroke={color} strokeWidth="1" strokeLinecap="round" />
      <line x1="2" y1="7" x2="12" y2="7" stroke={color} strokeWidth="1" strokeLinecap="round" />
      <line x1="2" y1="10" x2="10" y2="10" stroke={color} strokeWidth="1" strokeLinecap="round" />
    </svg>
  )
}

export function IconPalace({ size = 14, color = 'currentColor' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 14 14"
      fill="none"
      stroke={color}
      strokeWidth="1"
      strokeLinecap="round"
    >
      <line x1="1" y1="3" x2="13" y2="3" />
      <line x1="2" y1="5" x2="12" y2="5" />
      <line x1="4" y1="3" x2="4" y2="13" />
      <line x1="10" y1="3" x2="10" y2="13" />
    </svg>
  )
}

export function IconRefresh({ size = 14, color = 'currentColor' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 14 14"
      fill="none"
      stroke={color}
      strokeWidth="1"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 7a5 5 0 1 1-1.5-3.5" />
      <polyline points="12,2 12,5 9,5" />
    </svg>
  )
}
