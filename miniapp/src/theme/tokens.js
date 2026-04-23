// Paper tones — 12 种纸色底色
export const PAPER_TONES = {
  parchment: { bg:'#ede4d1', bgDeep:'#e5dcc5', card:'#f5ecd8', cardHi:'#faf2df',
    ink:'#2a2218', ink2:'#5a4e3a', ink3:'#8b7d63', ink4:'#b8ac92',
    rule:'rgba(68,52,28,0.16)', ruleSoft:'rgba(68,52,28,0.07)' },
  ivory: { bg:'#f4efe6', bgDeep:'#ece6d9', card:'#fbf7ee', cardHi:'#fffbf1',
    ink:'#3a3128', ink2:'#6a5f50', ink3:'#958a78', ink4:'#c9bda7',
    rule:'rgba(50,40,28,0.13)', ruleSoft:'rgba(50,40,28,0.06)' },
  rice: { bg:'#efeae0', bgDeep:'#e6e0d2', card:'#f7f3e9', cardHi:'#fdfaf1',
    ink:'#2a2a28', ink2:'#5c5a52', ink3:'#8a877b', ink4:'#bdbaac',
    rule:'rgba(30,30,24,0.13)', ruleSoft:'rgba(30,30,24,0.06)' },
  bone: { bg:'#f5f2ec', bgDeep:'#ece8df', card:'#fbf9f3', cardHi:'#ffffff',
    ink:'#1f1f1f', ink2:'#525050', ink3:'#85847f', ink4:'#bab8b1',
    rule:'rgba(0,0,0,0.11)', ruleSoft:'rgba(0,0,0,0.05)' },
  linen: { bg:'#ece7dc', bgDeep:'#e2dcce', card:'#f4efe4', cardHi:'#faf5ea',
    ink:'#2b2922', ink2:'#5c584c', ink3:'#8b8676', ink4:'#bbb5a3',
    rule:'rgba(40,36,24,0.13)', ruleSoft:'rgba(40,36,24,0.06)' },
  sand: { bg:'#e9dfcc', bgDeep:'#dfd4bb', card:'#f1e8d5', cardHi:'#f8efdb',
    ink:'#2a2116', ink2:'#5e5240', ink3:'#8e8269', ink4:'#baae94',
    rule:'rgba(70,52,24,0.15)', ruleSoft:'rgba(70,52,24,0.07)' },
  mist:  { bg:'#e7e7e2', bgDeep:'#dedfd9', card:'#eff0ea', cardHi:'#f6f7f1',
    ink:'#222421', ink2:'#52534e', ink3:'#84857f', ink4:'#b5b6ae',
    rule:'rgba(0,0,0,0.12)', ruleSoft:'rgba(0,0,0,0.05)' },
  pearl: { bg:'#ecebe7', bgDeep:'#e2e1dc', card:'#f5f4ef', cardHi:'#fbfaf5',
    ink:'#1f1f1d', ink2:'#53524f', ink3:'#85847f', ink4:'#b9b8b1',
    rule:'rgba(0,0,0,0.10)', ruleSoft:'rgba(0,0,0,0.05)' },
  celadon: { bg:'#e2e6de', bgDeep:'#d7dcd2', card:'#ebefe6', cardHi:'#f2f5ee',
    ink:'#1c2320', ink2:'#4f5853', ink3:'#7e8681', ink4:'#aeb5af',
    rule:'rgba(20,40,30,0.13)', ruleSoft:'rgba(20,40,30,0.06)' },
  rose: { bg:'#ebe2de', bgDeep:'#e1d7d2', card:'#f2eae6', cardHi:'#f8f1ed',
    ink:'#2a201d', ink2:'#5b4e49', ink3:'#8b7e78', ink4:'#bbaea9',
    rule:'rgba(60,30,20,0.13)', ruleSoft:'rgba(60,30,20,0.06)' },
  dusk: { bg:'#1c1814', bgDeep:'#14100c', card:'#241f19', cardHi:'#2c2720',
    ink:'#e9dfc9', ink2:'#b4a88d', ink3:'#7c7260', ink4:'#4a4439',
    rule:'rgba(233,223,201,0.13)', ruleSoft:'rgba(233,223,201,0.05)' },
  ink: { bg:'#14171a', bgDeep:'#0e1013', card:'#1b1e22', cardHi:'#22262b',
    ink:'#e4e7ec', ink2:'#a5aab0', ink3:'#6e7278', ink4:'#43464a',
    rule:'rgba(228,231,236,0.12)', ruleSoft:'rgba(228,231,236,0.05)' },
}

// Accent 色 — 5 档
export const ACCENTS = {
  vermilion: { main: '#8a2a2a', soft: '#a84545' },
  umber:     { main: '#5c2a1c', soft: '#7a4030' },
  sepia:     { main: '#7a4a2b', soft: '#a06a43' },
  indigo:    { main: '#2a3a52', soft: '#45587a' },
  moss:      { main: '#4a5a2e', soft: '#6a7a48' },
}

// 字体集 — 3 套
export const FONT_SETS = {
  serif: {
    display: '"Noto Serif SC","EB Garamond",Georgia,serif',
    body:    '"EB Garamond","Noto Serif SC",Georgia,serif',
    meta:    '"JetBrains Mono","SF Mono",ui-monospace,monospace',
  },
  mix: {
    display: '"Noto Serif SC","EB Garamond",Georgia,serif',
    body:    '"Inter","Noto Serif SC",system-ui,sans-serif',
    meta:    '"JetBrains Mono","SF Mono",ui-monospace,monospace',
  },
  sans: {
    display: '"Inter","Noto Serif SC",system-ui,sans-serif',
    body:    '"Inter","Noto Serif SC",system-ui,sans-serif',
    meta:    '"JetBrains Mono","SF Mono",ui-monospace,monospace',
  },
}

// 解析当前 state → 完整 theme 对象
export function resolveTheme({ tone = 'ivory', accent = 'vermilion', fonts = 'serif' } = {}) {
  const palette = PAPER_TONES[tone] || PAPER_TONES.ivory
  const acc     = ACCENTS[accent]   || ACCENTS.vermilion
  const font    = FONT_SETS[fonts]  || FONT_SETS.serif
  const dark    = tone === 'dusk' || tone === 'ink'
  return { ...palette, accent: acc.main, accentSoft: acc.soft, font, tone, accentName: accent, fontsName: fonts, dark }
}
