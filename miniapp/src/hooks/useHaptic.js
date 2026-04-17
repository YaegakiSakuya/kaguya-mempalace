import { useMemo } from 'react'

export default function useHaptic() {
  return useMemo(() => {
    const tg = typeof window !== 'undefined' ? window.Telegram?.WebApp : null
    const haptic = tg?.HapticFeedback

    return {
      impact: (style) => {
        try { haptic?.impactOccurred?.(style) } catch {}
      },
      notification: (type) => {
        try { haptic?.notificationOccurred?.(type) } catch {}
      },
      selection: () => {
        try { haptic?.selectionChanged?.() } catch {}
      },
    }
  }, [])
}
