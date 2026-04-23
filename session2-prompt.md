# Session 2 — Stream 页视觉重构

## 背景

你接手的是一个 React 18 + Vite 8 + TailwindCSS v4 的 Telegram Mini App。Session 1 已完成主题系统基座（`src/theme/` 目录、`:root` CSS 变量同步、字体引入）。

本 session 的目标：**重构 stream 页的视觉表现**。

具体变化：
1. SSE 空闲态（idle）从简陋的 "waiting" 文字 → 纸页感 WaitingHero（同心脉冲环 + LISTENING 带红线）
2. 历史列表从平铺卡片 → 可折叠抽屉（bold 风格：编号 + accent 时间 + 折叠）
3. Header 的月相图标升级为真实盈亏动画
4. 删除 "stream is live listening for the next word" 副文案

**数据逻辑和 props 接口完全不变。**

## 仓库

```
git@github.com:YaegakiSakuya/kaguya-mempalace.git
分支: main
工作目录: miniapp/
```

## 工作流程

```bash
git clone git@github.com:YaegakiSakuya/kaguya-mempalace.git
cd kaguya-mempalace
git checkout -b feat/miniapp-stream-visual
cd miniapp
npm install
# ... 完成下述工单 ...
npm run build
git add -A
git commit -m "feat(miniapp): stream page visual overhaul · WaitingHero + bold drawer + MoonDot"
git push -u origin feat/miniapp-stream-visual
# 开 PR 到 main
```

## 工单总览

| 操作 | 文件 | 说明 |
|---|---|---|
| 新建 | `src/components/MoonDot.jsx` | 月相盈亏心跳组件 |
| 覆盖 | `src/components/stream/LiveProcess.jsx` | idle 态改为 WaitingHero |
| 覆盖 | `src/components/stream/HistoryList.jsx` | 改为可折叠 bold 抽屉 |
| 覆盖 | `src/App.jsx` | MoonPhase → MoonDot，传 connected |
| 修改 | `src/pages/StreamPage.jsx` | 布局微调（flex 填充） |
| 追加 | `src/index.css` | 新增 2 个 keyframe 动画 |

---

## 步骤 1：新建 `src/components/MoonDot.jsx`

完整内容，逐字照搬：

```jsx
import { useState, useEffect, useId } from 'react'

export default function MoonDot({ size = 22, period = 6, connected = true }) {
  const [phase, setPhase] = useState(0)
  const uid = useId()

  useEffect(() => {
    if (!connected) return
    let raf
    const start = performance.now()
    const tick = (t) => {
      setPhase(((t - start) / 1000) % period / period)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [connected, period])

  const r = size / 2
  let shadowX
  if (phase < 0.5) {
    shadowX = -2 * r * (phase * 2)
  } else {
    shadowX = 2 * r - 2 * r * ((phase - 0.5) * 2)
  }

  return (
    <div
      title={connected ? 'SSE · connected' : 'SSE · offline'}
      style={{
        width: size,
        height: size,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <radialGradient id={`glow-${uid}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.28" />
            <stop offset="60%" stopColor="var(--accent)" stopOpacity="0.08" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </radialGradient>
          <clipPath id={`clip-${uid}`}>
            <circle cx={r} cy={r} r={r - 0.3} />
          </clipPath>
        </defs>
        {connected && (
          <circle cx={r} cy={r} r={r * 1.9} fill={`url(#glow-${uid})`} />
        )}
        <circle
          cx={r} cy={r} r={r - 0.6}
          fill="none"
          stroke={connected ? 'var(--accent-dim)' : 'var(--text-muted)'}
          strokeWidth="0.8"
          opacity={connected ? 0.55 : 0.7}
        />
        {connected && (
          <g clipPath={`url(#clip-${uid})`}>
            <circle cx={r} cy={r} r={r - 0.3} fill="var(--accent)" />
            <circle cx={r * 0.7} cy={r * 0.7} r={r * 0.9} fill="var(--accent-dim)" opacity="0.35" />
            <circle cx={r + shadowX} cy={r} r={r - 0.3} fill="var(--bg)" />
          </g>
        )}
      </svg>
    </div>
  )
}
```

---

## 步骤 2：覆盖 `src/components/stream/LiveProcess.jsx`

用下面的完整内容**整体替换**现有文件。所有数据处理函数（stripMempalacePrefix、formatPalaceWrites、translateProcessingMessage、mergeStreamEvents）以及事件渲染组件（EventContent、TimelineEvent、StatSummary）与原文件完全一致，**唯一变化**是：
- 新增 `PulseRing` 组件
- `idle` 状态的返回 JSX 改为 WaitingHero

```jsx
import { useEffect, useMemo, useRef } from 'react'

function stripMempalacePrefix(name) {
  if (typeof name !== 'string') return String(name ?? '')
  return name.replace(/^mempalace_/, '')
}

function formatPalaceWrites(writes) {
  if (!writes || typeof writes !== 'object') return ''
  return Object.entries(writes)
    .filter(([, v]) => v)
    .map(([k, v]) => `${v} ${k}`)
    .join(' / ')
}

function translateProcessingMessage(data) {
  const msg = data?.message || ''
  if (!msg) return data?.step || ''
  if (msg.includes('正在处理消息')) return 'processing...'
  const roundMatch = msg.match(/第\s*(\d+)\s*轮思考中/)
  if (roundMatch) return `thinking (round ${roundMatch[1]})...`
  return msg
}

function mergeStreamEvents(events) {
  const merged = []

  for (const event of events.filter(e => e.type !== 'done')) {
    if (event.type === 'thinking' || event.type === 'replying') {
      const last = merged[merged.length - 1]
      const chunk = event.data?.chunk || ''

      if (last && last.type === event.type) {
        last.data = {
          ...(last.data || {}),
          chunk: (last.data?.chunk || '') + chunk,
        }
      } else {
        merged.push({
          ...event,
          data: {
            ...(event.data || {}),
            chunk,
          },
        })
      }
      continue
    }

    merged.push(event)
  }

  return merged
}

function WaitingDots() {
  return (
    <span className="dots" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
      <span>·</span>
      <span>·</span>
      <span>·</span>
    </span>
  )
}

const SYSTEM_TEXT_STYLE = {
  fontFamily: 'var(--font-mono)',
  fontSize: '12px',
  color: 'var(--text-muted)',
  lineHeight: 1.5,
}

function PulseRing({ delay = 0 }) {
  return (
    <div style={{
      position: 'absolute',
      width: '110px',
      height: '110px',
      borderRadius: '50%',
      border: '1px solid var(--accent)',
      animation: `ringExpand 3.2s ease-out ${delay}s infinite`,
      opacity: 0,
    }} />
  )
}

function EventContent({ event }) {
  const { type, data } = event

  if (type === 'processing') {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: '8px',
          width: '100%',
        }}
      >
        <WaitingDots />
        <span style={SYSTEM_TEXT_STYLE}>
          {translateProcessingMessage(data)}
        </span>
      </div>
    )
  }

  if (type === 'thinking') {
    return (
      <div>
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            color: 'var(--accent)',
            marginBottom: '4px',
          }}
        >
          thinking
        </div>
        <div
          style={{
            fontFamily: 'var(--font-serif)',
            fontSize: '13px',
            color: 'var(--text-muted)',
            whiteSpace: 'pre-wrap',
            lineHeight: 1.6,
          }}
        >
          {data.chunk}
        </div>
      </div>
    )
  }

  if (type === 'replying') {
    return (
      <div>
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            color: 'var(--accent)',
            marginBottom: '4px',
          }}
        >
          replying
        </div>
        <div
          style={{
            fontFamily: 'var(--font-serif)',
            fontSize: '13px',
            color: 'var(--text)',
            whiteSpace: 'pre-wrap',
            lineHeight: 1.6,
          }}
        >
          {data.chunk}
        </div>
      </div>
    )
  }

  if (type === 'tool_call') {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: '8px',
          width: '100%',
        }}
      >
        <span style={{ ...SYSTEM_TEXT_STYLE, color: 'var(--accent)' }}>
          {data.tool}
        </span>
        <span style={{ ...SYSTEM_TEXT_STYLE, fontSize: '11px', color: 'var(--text-secondary)' }}>
          (round {data.round})
        </span>
      </div>
    )
  }

  if (type === 'tool_done') {
    const success = data.success !== false
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: '8px',
          width: '100%',
        }}
      >
        <span
          style={{
            ...SYSTEM_TEXT_STYLE,
            color: success ? 'var(--success)' : 'var(--fail)',
          }}
        >
          {success ? 'done' : 'failed'}
        </span>
        {data.duration_ms != null && (
          <span
            style={{
              marginLeft: 'auto',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--text-secondary)',
            }}
          >
            {data.duration_ms}ms
          </span>
        )}
      </div>
    )
  }

  return null
}

function TimelineEvent({ children }) {
  return (
    <div
      style={{
        position: 'relative',
        paddingBottom: '10px',
        minHeight: '16px',
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: '-16px',
          top: '6px',
          width: '7px',
          height: '7px',
          borderRadius: '50%',
          background: 'var(--accent)',
          border: '1.5px solid var(--bg)',
        }}
      />
      {children}
    </div>
  )
}

function StatSummary({ stats }) {
  const toolCount = Array.isArray(stats.tools) ? stats.tools.length : (stats.tools ? 1 : 0)
  const hasPalaceWrites =
    stats.palace_writes &&
    typeof stats.palace_writes === 'object' &&
    Object.values(stats.palace_writes).some(v => v)

  return (
    <div>
      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '11px',
          color: 'var(--text-secondary)',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0 10px',
          lineHeight: 1.6,
        }}
      >
        <span>in {stats.input_tokens?.toLocaleString() ?? '\u2014'}</span>
        <span>{'\u00b7'}</span>
        <span>out {stats.output_tokens?.toLocaleString() ?? '\u2014'}</span>
        <span>{'\u00b7'}</span>
        <span>{toolCount} calls</span>
        <span>{'\u00b7'}</span>
        <span>{stats.elapsed_ms != null ? `${(stats.elapsed_ms / 1000).toFixed(1)}s` : '\u2014'}</span>
        {hasPalaceWrites && (
          <>
            <span>{'\u00b7'}</span>
            <span>{formatPalaceWrites(stats.palace_writes)}</span>
          </>
        )}
      </div>

      {Array.isArray(stats.tools) && stats.tools.length > 0 && (
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            color: 'var(--text-secondary)',
            marginTop: '4px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '0 12px',
            lineHeight: 1.6,
          }}
        >
          {stats.tools.map((t, i) => (
            <span key={i}>{stripMempalacePrefix(t)}</span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function LiveProcess({ status, events, stats, connected }) {
  const bottomRef = useRef(null)
  const mergedEvents = useMemo(() => mergeStreamEvents(events), [events])

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' })
    }
  }, [mergedEvents])

  // ─── idle: WaitingHero with pulse rings ───
  if (status === 'idle') {
    return (
      <div
        style={{
          flex: '1 0 auto',
          minHeight: '340px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '56px 0 44px',
          textAlign: 'center',
        }}
      >
        <div
          style={{
            position: 'relative',
            width: '110px',
            height: '110px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {connected && <PulseRing delay={0} />}
          {connected && <PulseRing delay={1.2} />}
          <div
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '7px',
              background: connected ? 'var(--accent)' : 'var(--text-secondary)',
              boxShadow: connected ? '0 0 18px var(--accent-dim)' : 'none',
              animation: connected ? 'corePulse 2.8s ease-in-out infinite' : 'none',
            }}
          />
        </div>
        <div
          style={{
            marginTop: '22px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontFamily: 'var(--font-mono)',
            fontSize: '9.5px',
            letterSpacing: '0.42em',
            textTransform: 'uppercase',
            color: 'var(--text-muted)',
          }}
        >
          <span style={{ width: '14px', height: '0.6px', background: 'var(--accent)' }} />
          listening
          <span style={{ width: '14px', height: '0.6px', background: 'var(--accent)' }} />
        </div>
      </div>
    )
  }

  // ─── streaming / done: timeline (unchanged) ───
  return (
    <div style={{ padding: '12px 4px 24px 4px', minHeight: '200px' }}>
      <div style={{ position: 'relative', paddingLeft: '16px' }}>
        <div
          style={{
            position: 'absolute',
            left: '4px',
            top: '6px',
            bottom: '6px',
            width: '1px',
            background: 'var(--border)',
          }}
        />
        {mergedEvents.map((event, i) => (
          <TimelineEvent key={i}>
            <EventContent event={event} />
          </TimelineEvent>
        ))}
        {status === 'done' && stats && (
          <TimelineEvent>
            <StatSummary stats={stats} />
          </TimelineEvent>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
```

---

## 步骤 3：覆盖 `src/components/stream/HistoryList.jsx`

用下面的完整内容**整体替换**现有文件。变化点：
- 外层改为可折叠抽屉（默认折叠）
- 每条记录增加左侧编号（01, 02…）+ accent 时间标签
- 展开详情的左边距调整为对齐编号后的文本起始位置
- 刷新按钮移入抽屉标题栏
- 所有数据处理函数与展开态详情逻辑完全保留

```jsx
import { useState } from 'react'
import { IconRefresh } from '../icons'
import useHaptic from '../../hooks/useHaptic'

function stripMempalacePrefix(name) {
  if (typeof name !== 'string') return String(name ?? '')
  return name.replace(/^mempalace_/, '')
}

function formatPalaceWrites(writes) {
  if (!writes || typeof writes !== 'object') return ''
  return Object.entries(writes)
    .filter(([, v]) => v)
    .map(([k, v]) => `${v} ${k}`)
    .join(' / ')
}

function formatTime(ts) {
  if (!ts) return ''
  const then = new Date(ts)
  if (isNaN(then.getTime())) return ''
  const now = new Date()
  const diffMs = Math.max(0, now.getTime() - then.getTime())
  const diffMin = Math.floor(diffMs / 60000)
  const diffHr = Math.floor(diffMs / 3600000)

  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHr < 24 && then.toDateString() === now.toDateString()) return `${diffHr}h ago`

  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (then.toDateString() === yesterday.toDateString()) return 'yesterday'

  const sameYear = then.getFullYear() === now.getFullYear()
  const opts = sameYear
    ? { month: 'short', day: 'numeric' }
    : { year: 'numeric', month: 'short', day: 'numeric' }
  return then.toLocaleDateString('en-US', opts).toLowerCase()
}

const THINKING_COLLAPSE_THRESHOLD = 500

function HistoryItem({ item, index, isLast }) {
  const { impact } = useHaptic()
  const [expanded, setExpanded] = useState(false)
  const [thinkingExpanded, setThinkingExpanded] = useState(false)

  const inputTokens = item.total_prompt_tokens ?? item.input_tokens ?? item.prompt_tokens ?? 0
  const outputTokens = item.total_completion_tokens ?? item.output_tokens ?? item.completion_tokens ?? 0
  const rounds = item.total_rounds ?? item.rounds ?? null
  const tools = item.tools_called || item.tools || []
  const toolCount = Array.isArray(tools) ? tools.length : (tools ? 1 : 0)
  const rawPalaceWrites = item.palace_writes
  const hasPalaceWrites = rawPalaceWrites && (
    typeof rawPalaceWrites === 'string'
      ? rawPalaceWrites.trim() !== ''
      : typeof rawPalaceWrites === 'object' && Object.values(rawPalaceWrites).some(v => v)
  )
  const thinkingPreview = item.thinking_text || item.thinking_preview || null
  const thinkingNeedsCollapse = (thinkingPreview || '').length > THINKING_COLLAPSE_THRESHOLD
  const thinkingCollapsed = thinkingNeedsCollapse && !thinkingExpanded
  const responsePreview = item.response_preview || ''
  const rawReply = responsePreview || item.reply_text || ''
  const normalizedReply = rawReply.replace(/\s+/g, ' ').trim()
  const replyPreviewSummary = normalizedReply.slice(0, 80) + (normalizedReply.length > 80 ? '\u2026' : '')

  return (
    <div style={{ borderBottom: isLast ? 'none' : '1px solid var(--border)' }}>
      {/* ─── collapsed row: [index] [time] [preview] [chevron] ─── */}
      <button
        onClick={() => { impact('light'); setExpanded(!expanded) }}
        style={{
          width: '100%',
          textAlign: 'left',
          display: 'flex',
          gap: '10px',
          alignItems: 'center',
          padding: '9px 2px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: 'inherit',
          fontFamily: 'inherit',
        }}
      >
        <span
          style={{
            flexShrink: 0,
            width: '18px',
            fontFamily: 'var(--font-mono)',
            fontSize: '9px',
            color: 'var(--accent)',
            letterSpacing: '0.1em',
          }}
        >
          {String(index).padStart(2, '0')}
        </span>
        <span
          style={{
            flexShrink: 0,
            width: '52px',
            fontFamily: 'var(--font-mono)',
            fontSize: '8.5px',
            color: 'var(--text-secondary)',
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
          }}
        >
          {formatTime(item.ts || item.timestamp)}
        </span>
        <span
          style={{
            flex: 1,
            minWidth: 0,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            fontFamily: 'var(--font-serif)',
            fontSize: '12px',
            color: 'var(--text-muted)',
          }}
        >
          {normalizedReply
            ? replyPreviewSummary
            : <span style={{ color: 'var(--text-secondary)' }}>no reply</span>}
        </span>
        <svg
          width="7"
          height="7"
          viewBox="0 0 9 9"
          style={{
            flexShrink: 0,
            opacity: 0.55,
            transition: 'transform 0.25s',
            transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
          }}
        >
          <path d="M2 1L6 4.5L2 8" stroke="var(--text-muted)" strokeWidth="1" fill="none" strokeLinecap="round" />
        </svg>
      </button>

      {/* ─── expanded detail ─── */}
      <div
        style={{
          maxHeight: expanded ? '800px' : '0',
          overflow: 'hidden',
          transition: 'max-height 0.28s ease',
        }}
      >
        <div
          style={{
            padding: '2px 0 14px 74px',
            fontSize: '13px',
            lineHeight: 1.75,
          }}
        >
          {thinkingPreview && (
            <div style={{ marginBottom: '12px' }}>
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  color: 'var(--accent)',
                  marginBottom: '4px',
                }}
              >
                thinking
              </div>
              <div style={{ position: 'relative' }}>
                <div
                  style={{
                    fontFamily: 'var(--font-serif)',
                    fontSize: '12px',
                    lineHeight: 1.6,
                    color: 'var(--text-muted)',
                    whiteSpace: 'pre-wrap',
                    maxHeight: thinkingCollapsed ? '200px' : 'none',
                    overflow: thinkingCollapsed ? 'hidden' : 'visible',
                  }}
                >
                  {thinkingPreview}
                </div>
                {thinkingCollapsed && (
                  <div
                    style={{
                      position: 'absolute',
                      left: 0,
                      right: 0,
                      bottom: 0,
                      height: '60px',
                      pointerEvents: 'none',
                      background: 'linear-gradient(to bottom, transparent, var(--bg))',
                    }}
                  />
                )}
              </div>
              {thinkingNeedsCollapse && (
                <button
                  onClick={(e) => { e.stopPropagation(); impact('light'); setThinkingExpanded(!thinkingExpanded) }}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: '4px 0 0 0',
                    color: 'var(--accent)',
                    fontSize: '12px',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                  }}
                >
                  {thinkingExpanded ? 'collapse' : 'expand'}
                </button>
              )}
            </div>
          )}

          {responsePreview && (
            <div style={{ marginBottom: '4px' }}>
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  color: 'var(--accent)',
                  marginBottom: '4px',
                }}
              >
                reply
              </div>
              <div
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: '13px',
                  lineHeight: 1.6,
                  color: 'var(--text)',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {responsePreview}
              </div>
            </div>
          )}

          {!toolCount && !hasPalaceWrites && !thinkingPreview && !responsePreview && (
            <div
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                color: 'var(--text-secondary)',
              }}
            >
              no details
            </div>
          )}

          {(toolCount > 0 || rounds != null || hasPalaceWrites) && (
            <div
              style={{
                marginTop: '12px',
                paddingTop: '10px',
                borderTop: '1px solid var(--border)',
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                color: 'var(--text-secondary)',
                lineHeight: 1.6,
              }}
            >
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0 10px' }}>
                <span>in {inputTokens.toLocaleString()}</span>
                <span>{'\u00b7'}</span>
                <span>out {outputTokens.toLocaleString()}</span>
                {rounds != null && (
                  <>
                    <span>{'\u00b7'}</span>
                    <span>{rounds} rounds</span>
                  </>
                )}
                {hasPalaceWrites && (
                  <>
                    <span>{'\u00b7'}</span>
                    <span>{typeof rawPalaceWrites === 'string' ? rawPalaceWrites : formatPalaceWrites(rawPalaceWrites)}</span>
                  </>
                )}
              </div>
              {tools && (Array.isArray(tools) ? tools.length > 0 : String(tools).trim() !== '') && (
                <div style={{ marginTop: '4px', display: 'flex', flexWrap: 'wrap', gap: '0 12px' }}>
                  {(Array.isArray(tools) ? tools : String(tools).split(/\s*,\s*/)).map((t, i) => (
                    <span key={i}>{stripMempalacePrefix(t)}</span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function HistoryList({ items, onRefresh, loading }) {
  const { impact } = useHaptic()
  const [drawerOpen, setDrawerOpen] = useState(false)

  return (
    <div style={{ borderTop: '1px solid var(--border-strong)', paddingTop: '10px' }}>
      {/* ─── drawer header ─── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 0',
        }}
      >
        <button
          onClick={() => { impact('light'); setDrawerOpen(!drawerOpen) }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            flex: 1,
            background: 'transparent',
            border: 'none',
            padding: 0,
            cursor: 'pointer',
            color: 'inherit',
          }}
        >
          <svg
            width="9"
            height="9"
            viewBox="0 0 9 9"
            style={{
              transition: 'transform 0.25s',
              transform: drawerOpen ? 'rotate(90deg)' : 'rotate(0deg)',
            }}
          >
            <path d="M2 1L6 4.5L2 8" stroke="var(--text-muted)" strokeWidth="1" fill="none" strokeLinecap="round" />
          </svg>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '9px',
              letterSpacing: '0.32em',
              textTransform: 'uppercase',
              color: 'var(--accent)',
            }}
          >
            history
          </span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '9px',
              letterSpacing: '0.2em',
              color: 'var(--text-secondary)',
            }}
          >
            · {items.length}
          </span>
          <div style={{ flex: 1, height: '1px', background: 'var(--border)' }} />
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); impact('medium'); onRefresh() }}
          disabled={loading}
          aria-label="refresh history"
          style={{
            background: 'transparent',
            border: 'none',
            padding: '4px',
            cursor: loading ? 'default' : 'pointer',
            opacity: loading ? 0.3 : 0.5,
            transition: 'opacity 150ms ease',
            flexShrink: 0,
          }}
        >
          <IconRefresh color="var(--text-muted)" />
        </button>
      </div>

      {/* ─── drawer content ─── */}
      <div
        style={{
          maxHeight: drawerOpen ? '9999px' : '0',
          overflow: 'hidden',
          transition: 'max-height 0.35s ease',
        }}
      >
        <div style={{ paddingTop: '4px' }}>
          {items.length === 0 ? (
            <div
              style={{
                padding: '16px 0',
                textAlign: 'center',
                fontFamily: 'var(--font-serif)',
                fontSize: '12.5px',
                fontStyle: 'italic',
                color: 'var(--text-muted)',
              }}
            >
              no history
            </div>
          ) : (
            items.map((item, i) => (
              <HistoryItem
                key={item.id || i}
                item={item}
                index={i + 1}
                isLast={i === items.length - 1}
              />
            ))
          )}
        </div>
      </div>
    </div>
  )
}
```

---

## 步骤 4：覆盖 `src/App.jsx`

用下面的完整内容替换。变化点：
- 删除内联 `MoonPhase` 函数
- 导入 `MoonDot` 组件
- `Header` 改用 `MoonDot`，接收 `connected` prop

```jsx
import { useState } from 'react'
import useTelegram from './hooks/useTelegram'
import useSSE from './hooks/useSSE'
import useHaptic from './hooks/useHaptic'
import StreamPage from './pages/StreamPage'
import PalacePage from './pages/PalacePage'
import MoonDot from './components/MoonDot'
import { IconStream, IconPalace } from './components/icons'

function Header({ connected }) {
  return (
    <header
      className="px-4 pt-3 pb-2 flex items-center"
      style={{ gap: '12px' }}
    >
      <MoonDot size={14} period={6} connected={connected} />
    </header>
  )
}

function TabBar({ tab, onTabChange }) {
  const { impact } = useHaptic()
  const tabs = ['stream', 'palace']
  return (
    <div
      style={{
        display: 'flex',
        margin: '0 16px 16px',
      }}
    >
      {tabs.map(t => {
        const isActive = tab === t
        const color = isActive ? 'var(--text)' : 'var(--text-muted)'
        return (
          <button
            key={t}
            onClick={() => { impact('light'); onTabChange(t) }}
            aria-label={t}
            aria-pressed={isActive}
            style={{
              position: 'relative',
              flex: 1,
              padding: '12px 0',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              transition: 'color 250ms ease-out',
            }}
          >
            {t === 'stream' ? <IconStream color={color} /> : <IconPalace color={color} />}
            <span
              style={{
                position: 'absolute',
                left: '50%',
                bottom: 0,
                transform: 'translateX(-50%)',
                width: isActive ? '18px' : '0px',
                height: '1px',
                background: 'var(--accent)',
                transition: 'all 250ms ease-out',
              }}
            />
          </button>
        )
      })}
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState('stream')
  const { initData } = useTelegram()
  const sse = useSSE(initData)

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
      <Header connected={sse.connected} />
      <TabBar tab={tab} onTabChange={setTab} />
      {tab === 'stream' ? <StreamPage sse={sse} /> : <PalacePage />}
    </div>
  )
}
```

---

## 步骤 5：修改 `src/pages/StreamPage.jsx`

**只修改 return 语句的容器 className/style**，让 WaitingHero 能 flex-grow 填充屏幕高度。其他所有代码不动。

把：
```jsx
return (
  <div className="px-4 flex flex-col gap-8 pb-6">
```

改成：
```jsx
return (
  <div className="flex flex-col" style={{ padding: '0 22px 60px', minHeight: 'calc(100vh - 100px)' }}>
```

**只改这一行**，其他全部原样。

---

## 步骤 6：在 `src/index.css` 末尾追加动画

在文件**最末尾**追加以下内容（不修改现有内容，只追加）：

```css
@keyframes ringExpand {
  0% { transform: scale(0.3); opacity: 0; }
  20% { opacity: 0.5; }
  100% { transform: scale(1); opacity: 0; }
}

@keyframes corePulse {
  0%, 100% { transform: scale(0.85); opacity: 0.55; }
  50% { transform: scale(1.15); opacity: 1; }
}
```

---

## 禁区（越界即 PR 驳回）

- ❌ 修改 `src/hooks/` 下任何文件
- ❌ 修改 `src/theme/` 下任何文件
- ❌ 修改 `src/pages/PalacePage.jsx`
- ❌ 修改 `src/components/palace/` 下任何文件
- ❌ 修改 `src/components/icons.jsx`（只读引用）
- ❌ 修改 `app/miniapp/*.py`（后端）
- ❌ 修改 `miniapp/index.html`
- ❌ 修改 `miniapp/vite.config.js`
- ❌ 修改 `miniapp/src/index.css` 的现有内容（只允许末尾追加）
- ❌ 修改 StreamPage.jsx 的 import 语句、hooks 调用或 props 传递
- ❌ "顺手优化"或重构任何现有代码

## 本地自验证

```bash
cd miniapp
npm run build
```

必须 build 成功无 error。

预期效果（`npm run dev` 后访问 `http://localhost:3000/miniapp/`）：
- Header 左上角：月相图标缓慢盈亏循环（比原来的更精致）
- stream 页 idle 态：中央脉冲环 + 小红点呼吸 + "── LISTENING ──"
- stream 页 streaming 态：左侧时间线仍正常（与原来一致）
- 历史区域：折叠抽屉，标题 "HISTORY · N"，点击展开后每条带 01/02 编号
- palace 页：不受影响，完全原样

## 交付

```bash
git add -A
git commit -m "feat(miniapp): stream page visual overhaul · WaitingHero + bold drawer + MoonDot"
git push -u origin feat/miniapp-stream-visual
```

在 GitHub 开 PR 到 main。标题：

```
feat(miniapp): stream 页视觉重构 · WaitingHero + 历史抽屉 + 月相升级
```

PR 描述列出：新增文件、修改文件、无新增依赖、build 结果。

## 交付后

PR 开好即完成，后续 session 在新窗口进行。
