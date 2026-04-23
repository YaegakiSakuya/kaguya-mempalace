import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { resolveTheme } from './tokens'

const STORAGE_KEY = 'miniapp.theme'
const DEFAULTS = { tone: 'ivory', accent: 'vermilion', fonts: 'serif' }

const ThemeCtx = createContext(null)

function loadStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULTS
    return { ...DEFAULTS, ...JSON.parse(raw) }
  } catch {
    return DEFAULTS
  }
}

function saveStored(state) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)) } catch {}
}

// 把 theme 对象的颜色/字体同步写回到 :root CSS 变量。
// 这样现有组件里的 var(--bg) / var(--accent) 等引用 0 改动即可换皮。
function syncThemeToRoot(theme) {
  const r = document.documentElement.style
  r.setProperty('--bg', theme.bg)
  r.setProperty('--bg-deep', theme.bgDeep)
  r.setProperty('--bg-card', theme.card)
  r.setProperty('--bg-hover', theme.cardHi)
  r.setProperty('--text', theme.ink)
  r.setProperty('--text-2', theme.ink2)
  r.setProperty('--text-muted', theme.ink3)
  r.setProperty('--text-secondary', theme.ink4)
  r.setProperty('--accent', theme.accent)
  r.setProperty('--accent-dim', theme.accentSoft)
  r.setProperty('--border', theme.ruleSoft)
  r.setProperty('--border-strong', theme.rule)
  r.setProperty('--font-display', theme.font.display)
  r.setProperty('--font-serif', theme.font.body)
  r.setProperty('--font-mono', theme.font.meta)
  // color-scheme 让 iOS Telegram WebApp 的滚动条/表单控件跟随
  document.documentElement.style.colorScheme = theme.dark ? 'dark' : 'light'
}

export function ThemeProvider({ children }) {
  const [state, setState] = useState(loadStored)
  const theme = useMemo(() => resolveTheme(state), [state])

  useEffect(() => {
    syncThemeToRoot(theme)
    saveStored(state)
  }, [theme, state])

  const value = useMemo(() => ({
    theme,
    state,
    setTone:   (tone)   => setState(s => ({ ...s, tone })),
    setAccent: (accent) => setState(s => ({ ...s, accent })),
    setFonts:  (fonts)  => setState(s => ({ ...s, fonts })),
    reset:     () => setState(DEFAULTS),
  }), [theme, state])

  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>
}

export function useTheme() {
  const ctx = useContext(ThemeCtx)
  if (!ctx) throw new Error('useTheme must be used within <ThemeProvider>')
  return ctx
}
