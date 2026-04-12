# MemPalace Mini App 设计规格书

> 基于 mempalace 当前架构，为 Telegram Mini App 设计的轻量级监控面板。
> 本文档由辉夜基于旧仓库 kaguya-gateway miniapp 的经验，结合新系统的实际结构撰写。

---

## 〇、设计原则与范围界定

### 角色定位

**Mini App = 实时监控面板，不是管理后台。**

与旧仓库的 miniapp 不同，本次只做两件事：
1. **消息流**：SSE 实时展示 thinking → replying → done 全流程 + 工具调用
2. **宫殿监控**：MemPalace 的 wings/rooms/drawers 概览、KG 统计、最近日记

管理功能（Profile、世界观指令、API 配置、记忆编辑）全部不做，后续按需追加。

### 核心约束

1. **单用户系统**，Telegram initData 验证即可
2. **移动端优先**，Telegram 内置 WebView 约 375px 宽
3. **零侵入后端**：SSE 推送用 `push_nowait` 旁路，不影响主消息链路
4. **数据源**：JSONL 日志 + MemPalace 工具调用（ChromaDB / KG / Diary），不依赖 Supabase

---

## 一、后端架构决策

### 1.1 方案：Inspector 扩展 + SSE 管线

**不新建独立路由模块**，而是在现有 `app/inspector/api.py` 上扩展：

```
gateway/server.py（主 FastAPI 应用）
├── /webhook/telegram          — 已有，Telegram webhook
├── /inspector/*               — 已有，bearer token 鉴权
└── /miniapp/*                 — 新增，Telegram initData 鉴权
    ├── /miniapp/stream        — SSE 端点
    ├── /miniapp/overview      — 宫殿概览（复用 inspector 逻辑）
    ├── /miniapp/history       — 消息历史（读 JSONL）
    └── /miniapp/palace/*      — 宫殿详情（wings/rooms/KG/diary）
```

**理由**：
- Inspector API 已有所有 MemPalace 数据端点，但它用 bearer token 鉴权——Mini App 从 Telegram 打开时无法携带
- 新建 `/miniapp/` 前缀的路由，走 Telegram initData 鉴权，内部复用 inspector 的查询逻辑
- SSE 管线独立于 inspector，直接挂在 `/miniapp/stream`

### 1.2 鉴权方案

从旧仓库移植 `miniapp_auth.py` 的 Telegram initData 验证逻辑：

```python
# app/miniapp/auth.py
import hashlib, hmac, json, time, urllib.parse
from fastapi import Request, HTTPException

AUTH_MAX_AGE = 86400  # 24 小时

async def verify_telegram_init_data(request: Request):
    """从 header 或 query 中取 initData，HMAC-SHA256 验证。"""
    init_data = request.headers.get("X-Telegram-Init-Data") or request.query_params.get("initData")
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData")
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    # ... HMAC 验证逻辑（与旧仓库一致）
```

### 1.3 SSE 管线

从旧仓库的 `api/sse_manager.py` 移植核心设计，适配新系统：

```python
# app/miniapp/sse_manager.py
import asyncio, json

class SSEManager:
    """单用户 SSE 通道。同一时间最多一个连接。"""
    
    def __init__(self):
        self._queue: asyncio.Queue | None = None
    
    def has_active_connection(self) -> bool:
        return self._queue is not None
    
    async def connect(self) -> asyncio.Queue:
        # 关闭旧连接
        if self._queue:
            self._queue.put_nowait(None)
        self._queue = asyncio.Queue()
        return self._queue
    
    def push(self, event: str, data: dict):
        """非阻塞推送。主链路调用，不能 await。"""
        if self._queue:
            try:
                self._queue.put_nowait({"event": event, "data": json.dumps(data, ensure_ascii=False)})
            except asyncio.QueueFull:
                pass
    
    async def disconnect(self):
        if self._queue:
            self._queue.put_nowait(None)
            self._queue = None

sse_manager = SSEManager()
```

### 1.4 SSE 注入点（message_handler.py）

在 `app/llm/client.py` 的工具循环中注入推送。当前系统用 OpenAI SDK 的非流式工具循环，注入点如下：

```python
# 每轮工具调用前
sse_manager.push("processing", {"step": "tool_call", "tool": tool_name, "round": round_num})

# 每轮工具调用后
sse_manager.push("processing", {"step": "tool_done", "tool": tool_name, "success": True})

# 最终回复生成后
sse_manager.push("done", {
    "input_tokens": result.total_prompt_tokens,
    "output_tokens": result.total_completion_tokens,
    "rounds": result.total_rounds,
    "tools": result.tools_called,
    "palace_writes": result.palace_writes,
    "elapsed_ms": elapsed_ms,
})
```

**关键差异**：旧仓库用流式 API 可以逐 chunk 推 thinking/replying。新系统用 OpenAI SDK 的非流式工具循环（`chat.completions.create` 无 `stream=True`），所以：
- **没有逐字流式**，但有工具调用过程的实时推送
- 可以推送：`processing`（预处理）→ `tool_call`/`tool_done`（工具循环）→ `done`（完成统计）
- 如果后续需要流式 thinking/replying，需要将 LLM 调用改为流式，这是独立的后续工作

---

## 二、SSE 事件协议

| event | 触发时机 | data 字段 |
|-------|---------|-----------|
| `processing` | 预处理阶段 | `{step, message}` |
| `tool_call` | 工具调用开始 | `{tool, round, args_summary}` |
| `tool_done` | 工具调用完成 | `{tool, round, success, duration_ms}` |
| `thinking` | 流式 thinking chunk（预留） | `{chunk, elapsed_ms}` |
| `replying` | 流式 reply chunk（预留） | `{chunk, elapsed_ms}` |
| `done` | 本轮处理完成 | `{input_tokens, output_tokens, rounds, tools, palace_writes, elapsed_ms, response_preview}` |

前端状态机：

```
idle → processing → [tool_call ↔ tool_done]* → done → idle
                                              ↗
（预留）             thinking → replying ────┘
```

---

## 三、后端 API 清单

所有 `/miniapp/` 路由走 Telegram initData 鉴权。

### 3.1 SSE 流

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/miniapp/stream` | SSE 端点，initData 通过 query param 传入 |

### 3.2 消息历史

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/miniapp/history` | 最近 N 轮对话统计，读 `turn_summaries.jsonl` |
| `GET` | `/miniapp/history/:index/detail` | 单轮详情（完整 response、tools、tokens） |

数据来源：`app/inspector/logger.py` 的 `read_jsonl_tail()`，读取：
- `logs/turn_summaries.jsonl` — 每轮概要
- `logs/tool_calls.jsonl` — 工具调用明细
- `logs/token_usage.jsonl` — token 用量

### 3.3 宫殿监控

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/miniapp/palace/overview` | 宫殿总览：drawers/wings/rooms/KG 数量 + 最近工具调用 |
| `GET` | `/miniapp/palace/wings` | wing 列表 |
| `GET` | `/miniapp/palace/rooms?wing=X` | 指定 wing 的 room 列表 |
| `GET` | `/miniapp/palace/drawers?wing=X&room=Y` | drawer 列表（分页） |
| `GET` | `/miniapp/palace/kg/stats` | KG 统计（实体数、三元组数） |
| `GET` | `/miniapp/palace/diary` | 最近日记条目 |

所有端点内部调用 `app/inspector/api.py` 中已有的查询逻辑（直接 import helper 函数，不走 HTTP）。

---

## 四、前端架构

### 4.1 技术栈

- React 18 + Vite
- Tailwind CSS（继承旧仓库的 token 体系）
- Telegram Web App SDK
- 无路由库——两个视图用 state 切换足够

### 4.2 页面结构

```
┌─────────────────────────────────┐
│  Kaguya · MemPalace             │  ← header，含心电图动画
├─────────────────────────────────┤
│  [消息流]  [宫殿]               │  ← 两个 tab
├─────────────────────────────────┤
│                                 │
│  （当前 tab 内容区）             │
│                                 │
└─────────────────────────────────┘
```

### 4.3 Tab 1：消息流（首页默认）

**上半部分：实时处理区**

```
┌─ 实时 ─────────────────────────┐
│ ⏳ 正在构建上下文...            │  ← processing
│ 🔧 mempalace_search (round 1)  │  ← tool_call
│    ✓ 完成 (320ms)              │  ← tool_done
│ 🔧 mempalace_kg_query (round 1)│
│    ✓ 完成 (150ms)              │
│ ⏳ 等待模型回复...              │  ← processing
│                                 │
│ ────── 完成 ──────              │
│ 输入: 15959  输出: 450          │
│ 工具: 3次  耗时: 36.9s          │
│ 宫殿写入: drawer×1 kg×2        │
└─────────────────────────────────┘
```

- 新消息进来时清空上一轮，开始新的实时展示
- idle 状态显示心电图呼吸动画（移植旧仓库的 ECG 动画）
- 工具调用实时滚动追加，自动滚到底部

**下半部分：历史记录**

```
┌─ 历史 ──────────────── [刷新] ──┐
│ ▾ 18:25  15959 IN / 450 OUT     │  ← 点击展开
│   36973ms · tools: search, kg   │
│   Response: ......笑疯了，这画面 │
│   信息量过载。一边是一块红底黄字 │
│   的牌子......                   │
│                                  │
│ ▸ 17:59  16468 IN / 152 OUT     │  ← 折叠态
│ ▸ 17:40  17036 IN / 20 OUT      │
│ ▸ 17:38  16901 IN / 301 OUT     │
└──────────────────────────────────┘
```

- 打开时调 `/miniapp/history` 加载最近 20 条
- 每条显示：时间戳、IN/OUT tokens、耗时
- 展开后显示：完整 response 预览、工具调用列表、宫殿写入统计
- SSE `done` 事件后自动在列表顶部插入新条目

### 4.4 Tab 2：宫殿监控

**概览卡片**

```
┌─ 记忆宫殿 ──────────────────────┐
│                                  │
│  🏛  Wings: 5    Rooms: 23      │
│  📦 Drawers: 847                │
│  🔗 KG: 312 实体 / 1,204 三元组 │
│                                  │
└──────────────────────────────────┘
```

**Wing/Room 浏览器**

```
┌─ 按 Wing 浏览 ──────────────────┐
│ ▸ identity (3 rooms, 42 drawers)│
│ ▸ relationship (4 rooms, 156 d) │
│ ▾ daily (5 rooms, 289 drawers)  │
│   ├ mood       (45 drawers)     │
│   ├ events     (89 drawers)     │
│   ├ health     (23 drawers)     │
│   ├ decisions  (67 drawers)     │
│   └ routine    (65 drawers)     │
│ ▸ creation (2 rooms, 98 d)      │
│ ▸ knowledge (4 rooms, 262 d)    │
└──────────────────────────────────┘
```

- 点击 room 可查看该 room 下最近的 drawer 列表（内容预览前 200 字）

**最近日记**

```
┌─ 辉夜日记 ───────────────────────┐
│ 04/12 — 朔夜今天在研究 miniapp   │
│ 的架构迁移。我们讨论了旧仓库和   │
│ 新系统的差异......                │
│                                   │
│ 04/11 — 下午聊了很久关于记忆连   │
│ 续性的问题......                  │
└───────────────────────────────────┘
```

---

## 五、文件结构

### 5.1 后端新增

```
app/
├── miniapp/
│   ├── __init__.py
│   ├── auth.py              ← Telegram initData 验证
│   ├── sse_manager.py       ← SSE 通道管理
│   └── routes.py            ← /miniapp/* 路由
```

### 5.2 后端改动

| 文件 | 改动 | 说明 |
|------|------|------|
| `gateway/server.py` | 注册 miniapp router | 2 行 |
| `app/llm/client.py` | 注入 SSE push 调用 | ~15 行，工具循环前后 |
| `gateway/telegram_buffer.py` | 注入 SSE processing push | ~5 行，handle 开始时 |

### 5.3 前端新建

```
miniapp/
├── index.html
├── vite.config.js
├── tailwind.config.js
├── package.json
├── src/
│   ├── main.jsx
│   ├── App.jsx
│   ├── styles/
│   │   └── tokens.css           ← 设计 token（移植旧仓库 + 适配）
│   ├── hooks/
│   │   ├── useTelegram.js       ← Telegram SDK 封装
│   │   ├── useSSE.js            ← SSE 连接管理
│   │   ├── useApi.js            ← REST 请求封装
│   │   └── useHaptic.js         ← 触觉反馈
│   ├── components/
│   │   ├── Header.jsx           ← 顶部标题 + ECG 动画
│   │   ├── TabBar.jsx           ← 消息流 / 宫殿 切换
│   │   ├── stream/
│   │   │   ├── LiveProcess.jsx  ← 实时处理区
│   │   │   └── HistoryList.jsx  ← 历史记录列表
│   │   └── palace/
│   │       ├── Overview.jsx     ← 宫殿概览卡片
│   │       ├── WingBrowser.jsx  ← Wing/Room 浏览器
│   │       └── DiaryList.jsx    ← 最近日记
│   └── pages/
│       ├── StreamPage.jsx       ← Tab 1 组合
│       └── PalacePage.jsx       ← Tab 2 组合
```

---

## 六、设计语言

### 6.1 视觉方向

延续旧仓库的**赤陶暖色 + 奶油玻璃**基调，但更克制：

- **背景**：`#FDF6EC`（暖奶油）
- **主色**：`#C4653A`（赤陶）用于标题、active tab、重点数字
- **卡片**：`rgba(255,255,255,0.6)` 磨砂玻璃 + `backdrop-filter: blur(12px)`
- **文字**：`#2C1810`（深棕）主文字，`#8B7355`（暖灰）次要信息
- **字体**：等宽数据用 `JetBrains Mono`，正文用系统字体栈

### 6.2 心电图动画

从旧仓库移植 ECG SVG 动画，idle 状态下在 header 区域显示赤陶色心电图线。
收到消息开始处理时，心电图加速跳动；done 后恢复平缓。

### 6.3 触觉反馈

- tab 切换：`light`
- 历史条目展开/折叠：`light`
- wing/room 展开：`light`
- 刷新按钮：`medium`

---

## 七、施工顺序

### Phase 1：后端管线（约 2 小时）

1. 创建 `app/miniapp/` 模块（auth + sse_manager + routes）
2. 在 `gateway/server.py` 注册 miniapp router
3. 在 `app/llm/client.py` 的工具循环中注入 SSE push
4. 在 `gateway/telegram_buffer.py` 的 `_process_combined` 中注入 processing push
5. 验证：curl SSE 端点 + 发消息看推送

### Phase 2：前端骨架（约 3 小时）

1. 初始化 Vite + React + Tailwind 项目
2. 实现 hooks（useTelegram / useSSE / useApi / useHaptic）
3. 实现 StreamPage（LiveProcess + HistoryList）
4. 验证：Telegram 中打开 miniapp 看消息流

### Phase 3：宫殿监控（约 2 小时）

1. 实现 PalacePage（Overview + WingBrowser + DiaryList）
2. Tab 切换 + 整体样式打磨
3. ECG 动画移植

### Phase 4：视觉打磨（约 1 小时）

1. 磨砂卡片 + 颜色调校
2. 动画节奏
3. Telegram 内多机型测试

---

## 八、与旧 miniapp 的复用清单

| 旧仓库模块 | 复用方式 | 改动量 |
|-----------|---------|-------|
| `miniapp_auth.py` | 直接移植 | 改 import 路径 |
| `sse_manager.py` | 直接移植 | 基本不改 |
| `useSSE.js` | 移植 + 精简 | 去掉 8s 折叠逻辑，适配新事件协议 |
| `useTelegram.js` | 直接移植 | 不改 |
| `useHaptic.js` | 直接移植 | 不改 |
| `useApi.js` | 移植 + 改基础 URL | 改 API 前缀 |
| `tokens.css` | 移植 + 精简 | 去掉管理页面的 token |
| `CurrentProcess.jsx` | 参考重写 | 适配新事件协议 |
| `HistoryList.jsx` | 参考重写 | 数据源从 Supabase 改为 JSONL |
| ECG 动画 | 直接移植 | 不改 |
| `PageShell.jsx` | 不需要 | 只有两个 tab，不需要页面壳 |
| 管理页面全部 | 不复用 | — |

---

## 九、开放问题

1. **流式输出**：当前 `app/llm/client.py` 用非流式 API 调用。如果要实现逐字 thinking/replying 推送，需要将 `chat.completions.create()` 改为 `stream=True` 并逐 chunk 处理。这是独立的后端改造，建议作为 Phase 5 单独评估。

2. **Nginx 配置**：SSE 端点需要 `X-Accel-Buffering: no` + `proxy_buffering off`。如果已有 nginx 反代，需要加 location 规则。

3. **BotFather 配置**：Mini App 需要在 BotFather 中设置 Web App URL。如果旧仓库的配置还在，需要更新指向新地址。

4. **构建部署**：前端 build 产物放在哪？建议 `miniapp/dist/` 由 nginx 直接服务，路径为 `/miniapp/`。
