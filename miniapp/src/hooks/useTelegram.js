import { useMemo } from 'react'

export default function useTelegram() {
  return useMemo(() => {
    const webApp = window.Telegram?.WebApp
    const initData = webApp?.initData || ''
    const user = webApp?.initDataUnsafe?.user || null
    const colorScheme = webApp?.colorScheme || 'light'

    if (webApp) {
      webApp.ready()
      webApp.expand()
    }

    return { webApp, initData, user, colorScheme }
  }, [])
}
