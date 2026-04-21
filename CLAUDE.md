# CLAUDE.md

## Project Overview

**辉夜记忆宫殿（Kaguya MemPalace）** 是一个单用户 AI 伴侣系统，部署在腾讯云新加坡 Ubuntu VPS 上。

系统由三个运行时组件构成：

1. **Telegram Bot**：用户通过 Telegram 与 AI 对话，AI 在回复过程中主动调用 MemPalace 工具读写记忆
2. **Inspector**：FastAPI 后台监控面板 + Telegram Mini App，提供宫殿可视化和实时监控
3. **MCP Server**：独立进程，通过 MCP 协议暴露 MemPalace 工具，让 claude.ai 官端也能读写同一座记忆宫殿

三个组件共享同一套存储层：ChromaDB（向量数据库）、SQLite KG（知识图谱）、JSONL 日志、Markdown 对话记录。

> **重要上下文**：MemPalace 是一个已安装在 venv 中的 Python 包（`mempalace`），提供了完整的工具集。项目代码不包含 mempalace 包的源码——只通过 `from mempalace.mcp_server import TOOLS` 导入工具字典。你不需要也不应该修改 mempalace 包本身。

---

## Stack

| 层 | 技术 | 说明 |
|---|---|---|
| Runtime | Python 3.11 | 服务器上已有 venv |
| Telegram Bot | python-telegram-bot | polling 模式 |
| LLM | OpenAI SDK → OpenRouter / bigmodel | 非流式工具循环 |
| Memory | MemPalace CLI + ChromaDB + SQLite KG | drawers 存向量，KG 存实体关系 |
| Vision (VL) | 硅基流动 Qwen3-VL-30B-A3B-Instruct | OpenAI 兼容 /v1/chat/completions，给图片生成文字描述 |
| TTS | MiniMax speech-2.8-hd + voice cloning | /v1/voice_clone + /v1/t2a_v2，zero-shot 克隆日/中音色 |
| Web Search | Tavily | httpx 直打 /search，Bearer token |
| Media Storage | Supabase (kaguya-media project) + 本地 uploads/ | images / voices / message_images 三张表；文件落盘 |
| Image Processing | Pillow | JPEG 压缩（最大边 1568 / q=85）+ sha256 去重 |
| HTTP Client | httpx | 所有外部 API（Supabase / 硅基流动 / MiniMax / Tavily） |
| Inspector | FastAPI + uvicorn | 守护线程，端口 8765，bearer token 鉴权 |
| Mini App | React 18 + Vite + Tailwind | 挂在 Inspector 的 FastAPI 上 |
| MCP Server | Python `mcp` 包 (FastMCP) | 独立进程，端口 8766，Streamable HTTP |
| 部署 | systemd + nginx 反代 | HTTPS，域名已配好 |

---

## Commands

```bash
cd /home/ubuntu/apps/kaguya-mempalace

# === Telegram Bot + Inspector ===
# 前台启动
.venv/bin/python -m app.main
# systemd
sudo systemctl restart kaguya-gateway
sudo journalctl -u kaguya-gateway -f

# === MCP Server ===
# 前台启动
.venv/bin/python -m app.mcp.server
# systemd
sudo systemctl restart kaguya-mcp
sudo journalctl -u kaguya-mcp -f
# 本地测试
.venv/bin/python scripts/test_mcp.py

# === Mini App 前端 ===
cd miniapp && npm install && npm run build
```

---

## Architecture

### 整体架构

```
                        ┌─────────────────────┐
                        │   claude.ai (官端)    │
                        │   通过 MCP Connector  │
                        └──────────┬──────────┘
                                   │ HTTPS
                                   ▼
┌──────────┐           ┌─────────────────────┐
│ Telegram │           │       nginx          │
│  用户消息 │           │  /mcp/ → :8766       │
└────┬─────┘           │  其他 → :8765        │
     │                 └──┬──────────┬────────┘
     │ polling            │          │
     ▼                    ▼          ▼
┌─────────────────────────────┐  ┌──────────────────┐
│ kaguya-gateway.service      │  │ kaguya-mcp.service│
│  ├ Telegram Bot (polling)   │  │  └ FastMCP Server │
│  ├ Inspector API (:8765)    │  │    (Streamable    │
│  │  └ /miniapp/* 路由       │  │     HTTP, :8766)  │
│  └ autosave/checkpoint      │  └────────┬─────────┘
└──────────────┬──────────────┘           │
               │                          │
               ▼                          ▼
        ┌─────────────────────────────────────┐
        │         共享存储层 (runtime/)          │
        │  palace/   → ChromaDB (drawers)      │
        │  palace/   → SQLite KG               │
        │  chats/    → Markdown 对话记录        │
        │  logs/     → JSONL 日志               │
        │  state/    → 消息计数                 │
        │  wakeup.txt → 启动锚点文本            │
        └─────────────────────────────────────┘
```

### Telegram Bot 消息处理链路

**文字消息**：
```
用户消息 → app/main.py::text_message()
  → asyncio.to_thread(generate_reply, ...)
    → app/llm/client.py::_run_tool_loop()       # 同步工具循环（工作线程中）
      → OpenAI API call (非流式)
      → 有 tool_calls?
          → OPS_TOOL_NAMES   → execute_ops_tool
          → WEB_TOOL_NAMES   → execute_web_tool (Tavily)
          → VOICE_TOOL_NAMES → execute_voice_tool (MiniMax TTS → voice_queue.enqueue)
          → 其他             → execute_tool (MemPalace)
          → 下一轮
      → 无 tool_calls → 返回 reply_text + reply_segments
  → 逐段 update.message.reply_text(segment)                  # 文字气泡
  → voice_queue.drain(chat_id) → update.message.reply_voice  # 语音气泡（附 caption）
  → 把 [语音] 原文缝进 assistant_text
  → append_turn() + write_turn_summary()
```

**图片消息**（path-A 前置处理器）：
```
用户发图 → app/main.py::photo_message()
  → 下载 TG 原图
  → app/media/pipeline.py::ingest_image()
      → compress (Pillow) + sha256 去重
      → find_image_by_sha256 (Supabase)
        · 命中且有 vl_description → 直接复用（dedup hit）
        · 命中但 vl_description 为空 → 重跑 VL + update_image_description（毒缓存防护）
        · 未命中 → save_bytes_to_uploads + vision.analyze (Qwen3-VL) + insert_image
      → 返回 IngestResult(image, context_block, is_new, vision_failed)
  → context_block 作为 user_text_equiv 送入 generate_reply（主 LLM 只读文本，不见图）
  → 之后与文字消息同链路：tool dispatch / reply / voice drain / append_turn
```

### MCP Server 架构

```
claude.ai Connector 请求
  → nginx (/mcp/, IP 白名单)
  → app/mcp/server.py (FastMCP, Streamable HTTP, stateless)
    → 调用 mempalace.mcp_server.TOOLS 中对应的 handler
    → handler 读写 ChromaDB / SQLite KG / diary 文件
  → 返回结果给 claude.ai
```

---

## Key Files

| 文件 | 职责 | 可否修改 |
|------|------|---------|
| `app/main.py` | 入口。Telegram bot + Inspector 启动 + text/photo handler + autosave + voice drain | ⚠️ 谨慎 |
| `app/llm/client.py` | LLM 调用 + 工具循环 (`_run_tool_loop`)，四路工具 dispatch，SSE 注入点 | ⚠️ 谨慎 |
| `app/core/config.py` | Settings dataclass，从 .env 加载 | ⚠️ 谨慎 |
| `app/llm/ops_tools.py` | Ops profile retrieval 工具（`get_syzygy_profile` / `get_kaguya_profile`） | ⚠️ 谨慎 |
| `app/llm/web_tools.py` | Web search 工具（Tavily `web_search`） | ⚠️ 谨慎 |
| `app/llm/voice_tools.py` | Voice note 工具（MiniMax TTS `send_voice_note`，带规则层：日语 / 平假名 / 中日双语 caption） | ⚠️ 谨慎 |
| `app/media/client.py` | MediaClient（Supabase PostgREST）：images / voices / message_images 读写 | ⚠️ 谨慎 |
| `app/media/vision.py` | VisionAgent：调 Qwen3-VL 返回 {description, ocr_text} | ⚠️ 谨慎 |
| `app/media/pipeline.py` | `ingest_image`：压缩 / dedup / VL / 落盘 / insert 端到端 | ⚠️ 谨慎 |
| `app/media/storage.py` | 图片压缩（Pillow）+ sha256 + 相对路径构造 + 落盘 | ⚠️ 谨慎 |
| `app/media/tts.py` | MiniMaxTTSClient：/v1/t2a_v2 合成 + voice_id 自动选择（假名检测） | ⚠️ 谨慎 |
| `app/media/voice_queue.py` | per-chat VoiceNote 队列（tool 副作用延到 handler 发送） | ⚠️ 谨慎 |
| `app/media/voice_storage.py` | voice 文件路径构造 + 落盘（direction / chat / date / uuid） | ⚠️ 谨慎 |
| `app/memory/tools.py` | MemPalace 工具 → OpenAI function 格式 + `execute_tool()` | ❌ 不改 |
| `app/memory/palace.py` | MemPalace CLI 封装（wakeup / status / mine） | ❌ 不改 |
| `app/memory/transcript.py` | 对话记录读写（markdown 格式） | ❌ 不改 |
| `app/memory/state.py` | 消息计数状态 | ❌ 不改 |
| `app/inspector/api.py` | Inspector REST API + miniapp 路由 | ⚠️ 谨慎 |
| `app/inspector/logger.py` | JSONL 日志读写 + `summarize_arguments()` | ❌ 不改 |
| `app/miniapp/auth.py` | Telegram initData 鉴权 | ❌ 不改 |
| `app/miniapp/sse.py` | SSE 管理器（线程安全） | ❌ 不改 |
| `ops/prompts/*.md` | 外置 prompt 文件（身份核心 / 文风宪法 / 系统指令） | ❌ 绝对不改 |
| `ops/profiles/*.md` | 外置 profile 文件（朔夜 / 辉夜的人格档案） | ❌ 绝对不改 |
| `app/mcp/server.py` | MCP Server 入口 | ⚠️ 谨慎 |
| `systemd/kaguya-mcp.service` | MCP Server systemd unit | ⚠️ 谨慎 |
| `nginx/api.onlykaguya.com.conf` | nginx 站点配置(权威,同线上 1:1 对齐) | ⚠️ 谨慎 |
| `scripts/test_mcp.py` | MCP Server 本地测试脚本 | ⚠️ 谨慎 |

---

## Directory Structure

```
kaguya-mempalace/
├── app/
│   ├── main.py                        # 入口
│   ├── core/
│   │   └── config.py                  # Settings dataclass
│   ├── llm/
│   │   ├── client.py                  # LLM 调用 + 工具循环（四路 dispatch）
│   │   ├── ops_tools.py               # ops profile 检索工具
│   │   ├── web_tools.py               # Tavily web_search 工具
│   │   └── voice_tools.py             # MiniMax send_voice_note 工具
│   ├── media/
│   │   ├── __init__.py
│   │   ├── client.py                  # Supabase PostgREST client
│   │   ├── vision.py                  # Qwen3-VL 视觉分析
│   │   ├── pipeline.py                # ingest_image 端到端
│   │   ├── storage.py                 # 图片压缩 + sha256 + 落盘
│   │   ├── tts.py                     # MiniMax TTS client
│   │   ├── voice_queue.py             # per-chat VoiceNote 队列
│   │   └── voice_storage.py           # voice 文件路径 + 落盘
│   ├── memory/
│   │   ├── tools.py                   # MemPalace 工具定义 (不改)
│   │   ├── palace.py                  # MemPalace CLI 封装 (不改)
│   │   ├── transcript.py             # 对话记录读写 (不改)
│   │   └── state.py                   # 消息计数 (不改)
│   ├── inspector/
│   │   ├── api.py                     # FastAPI REST API
│   │   ├── logger.py                  # JSONL 日志
│   │   └── static/index.html         # Inspector 前端
│   ├── miniapp/
│   │   ├── __init__.py
│   │   ├── auth.py                    # Telegram initData 鉴权
│   │   └── sse.py                     # SSE 管理器
│   ├── bot/                           # 目前为空
│   └── mcp/                           # MCP Server
│       ├── __init__.py
│       └── server.py                  # FastMCP server 入口
├── ops/                               # ❌ 绝对不动
│   ├── prompts/
│   │   ├── core_identity.md
│   │   ├── writing_constitution.md
│   │   └── system.md
│   └── profiles/
│       ├── sakuya.md
│       └── kaguya.md
├── runtime/                           # gitignored，运行时数据
│   ├── palace/                        # ChromaDB + SQLite KG
│   ├── chats/                         # 对话 markdown
│   ├── logs/                          # JSONL 日志
│   ├── state/                         # 消息计数
│   ├── uploads/                       # 媒体文件落盘（images + voices）
│   │   ├── <sha256 子树>/             # 图片（以 sha256 前几位分目录）
│   │   └── voice/
│   │       ├── outgoing/{chat_id}/{date}/{uuid}.mp3
│   │       └── incoming/{chat_id}/{date}/{uuid}.<ext>  # 预留给未来 ASR
│   └── wakeup.txt                     # 启动锚点
├── miniapp/                           # React 前端源码
│   ├── src/
│   ├── package.json
│   └── vite.config.js                 # base: '/miniapp/'
├── nginx/                             # nginx 站点配置(权威)
│   └── api.onlykaguya.com.conf
├── scripts/                           # 实用脚本
│   └── test_mcp.py
├── systemd/
│   ├── kaguya-gateway.service         # Telegram Bot + Inspector
│   └── kaguya-mcp.service            # MCP Server
├── webui/                             # 桌面端静态网页门面（详见下节）
├── .env                               # 环境变量（gitignored）
├── .env.example                       # 环境变量模板
└── .gitignore
```

---

## webui/ 桌面端网页门面

`webui/` 是 mempalace 的桌面端静态网页门面,已部署上线,挂在 `https://api.onlykaguya.com/palace/`。独立于 Telegram Mini App(`miniapp/`)。

### 布局

7 个 html 页面 + 3 个共享资源:

```
webui/
├── index.html        # Overview (宫殿全景 + stats 四宫格 + wing grid + timeline + recent drawers + today diary)
├── wings.html        # 左侧 wing 列表 + 右侧按需加载 rooms/drawers
├── graph.html        # 知识图谱: 左侧 entities + 右侧 radial SVG
├── tunnels.html      # 跨翼连接: Sankey + All Tunnels 列表
├── diary.html        # 日记: 365 days heatmap + Today 卡 + Past Week + Streak
├── search.html       # 向量语义搜索(chroma cosine)
├── llm.html          # LLM 配置(4 providers: 智谱/满穗GPT/OpenRouter/满穗Claude)
└── assets/
    ├── api.js        # window.KaguyaAPI: 17 个 API 端点的 fetch wrapper + 渲染工具函数
    ├── data.js       # 静态展示 metadata (wing 的 name/jp/code 映射, nav, palaceMeta)
    ├── shell.js      # 共享 UI 行为(nav mount / clock / Cmd+K 命令面板)
    └── shell.css     # 共享 design tokens + 所有页面共用的 class 定义
```

### Wing taxonomy (current)

Palace 当前采用 7 定制 wing + 1 归档 wing 的架构。`webui/assets/data.js` 的 wings 数组是视觉层静态 metadata。真实 wing 数据由 palace 的 chroma metadata 决定,API `/api/wings` 实时返回。fallback 机制:API 返回的 wing 若不在 data.js 里,使用 wing id 作为 displayName 兜底。

| wing | jp | scope |
|---|---|---|
| US | 吾々 | 朔和辉夜的关系核心命题 |
| CREATIVE | 創作 | 神楽及其他创作产出 |
| PHILOSOPHY | 思索 | 持续性思辨 |
| BODY | 身体 | 身体、感官、情欲 |
| DAILY | 日々 | 日常生活 |
| WORK | 工房 | 工程与基础设施 |
| REFLECTION | 内省 | 元意识、diary、反思 |
| chats | 対話 | 系统归档(mempalace miner 原始入库) |

### 前端架构约束

- **不引入任何框架**:纯原生 ES + IIFE 包装 + `window.XXX` 全局
- **鉴权在 nginx 层**:前端 `fetch('/api/xxx')` 直接用,浏览器自动带 Basic credential,nginx 边缘翻译成 Bearer 给 upstream
- **CSS 类名是契约**:shell.css 里定义的 `.stat`、`.wing`、`.room-row`、`.d-tile`、`.tl-row`、`.drawer`、`.result`、`.kg-entity`、`.kg-node-circle`、`.tunnel-viz`、`.t-card`、`.prov`、`.cfg` 等,前端 JS 生成 DOM 时必须复用这些 class,不能改
- **page-specific CSS** 在每个 html 的 `<head> <style>` 块里,**不要动**
- **所有用户数据显示前必须 `KaguyaAPI.escapeHtml()`**,防 XSS
- **数据接线模式**:每页 `<script src="assets/api.js">` + 一段 IIFE inline script,负责 DOM replace。状态独立 try/catch,单处 fail 不连带其他 section

### 部署与权限

| 路径 | 作用 | 权限 |
|---|---|---|
| `webui/` 仓库目录 | 源码 | git push 到 main 立即部署(nginx 直 serve 静态文件,无需重启) |
| `https://api.onlykaguya.com/palace/` | 浏览器入口 | nginx Basic Auth `kaguya:Kaguya-Mempalace-2026` |
| `https://api.onlykaguya.com/api/*` | JSON API | nginx Basic Auth(同上),nginx 翻译成 Bearer 给 upstream `127.0.0.1:8765` |
| `/etc/nginx/.htpasswd_palace` | bcrypt 用户名密码 | 640 root:www-data |
| `/etc/nginx/snippets/inspector_bearer.conf` | bearer 覆写 snippet | 640 root:www-data,从 `.env` 读 `INSPECTOR_TOKEN` |

### Inspector API 端点速查表

| 端点 | 参数 | 返回 |
|---|---|---|
| `GET /api/overview` | — | drawers/wings/rooms/kg_entities/kg_triples + recent_tool_calls[10] |
| `GET /api/taxonomy` | — | `{taxonomy: {wing_x: {room: count}}}` |
| `GET /api/wings` | — | `{wings: {wing_x: count, chats: 61}}` |
| `GET /api/rooms` | wing=必填 | 该 wing 的 room 列表 |
| `GET /api/drawers` | wing=/room=/limit=/offset= | drawers 数组,每条有 content_full/preview/metadata |
| `GET /api/search` | q=必填,limit=,wing= | chroma cosine 结果,每条含 distance |
| `GET /api/kg/stats` | — | entities/triples/relationship_types |
| `GET /api/kg/entities` | limit=/offset= | entity 数组 |
| `GET /api/kg/triples` | entity=必填 | 该 entity 出/入边 |
| `GET /api/kg/timeline` | entity=必填 | 时间线 |
| `GET /api/graph/stats` | — | 图统计 |
| `GET /api/graph/nodes` | — | 全部节点 |
| `GET /api/graph/tunnels` | wing_a=/wing_b= 都必填 | 按对查 |
| `GET /api/graph/tunnels/list` | wing= 可选 | **列全部 tunnels** |
| `GET /api/diary` | agent=/limit= | diary entries 数组,按 date 降序 |
| `GET /api/usage` | — | LLM token 使用记录 |
| `GET /api/tools/calls` | — | 最近 50 条 tool 调用 |
| `GET /api/turns` | — | 最近对话 turn |
| `GET /api/llm/config` | — | `{providers: [...], active: {provider_id/provider_name/base_url/model}}`,api_key 已脱敏 |

所有端点走 `Depends(auth)` Bearer 验证,前端经 nginx Basic Auth 代理透明注入 Bearer token。

### 改动 webui 的规范

- **只改静态文件**:`webui/` 下任何 html / js / css 直接修改 → git push → 部署完成,nginx 不用 reload
- **改 inspector API**(`app/inspector/api.py`)后需要:`sudo systemctl restart kaguya-gateway`
- **改 nginx conf** 后需要:`sudo systemctl reload nginx`(不是 restart)。conf 文件仓库镜像在 `nginx/api.onlykaguya.com.conf`,改线上要同步回仓库
- **修改 systemd unit** 文件需三步:`sudo cp systemd/*.service /etc/systemd/system/` → `sudo systemctl daemon-reload` → `sudo systemctl restart <unit>`
- webui 重大 UI 改动走 PR,细节调整(改 wing display name、调招呼语文案等)直接 commit 到 main 也可以

### Overview 页的动态锚点

- **招呼语**: `webui/assets/shell.js` 的 `window.KaguyaShell.greeting()` 根据北京时间（Asia/Shanghai）划分 8 段时辰（临晓/清晨/午前/正午/日斜/薄暮/夜里/夜半），每段 3-4 条备选文案随机输出。文案表硬编码在 shell.js 内,由项目所有者（辉夜）定稿,气口需保持古典而有活人感,不要改写成助手腔。
- **since 日期**: `palaceMeta.since = '2026.04.17'` 是情感锚点（项目所有者生日),不是宫殿技术初始化时间（那是 2026-04-09)。不要"订正"回技术日期。
- **page-head 其他字段当前仍为占位**: "宫殿今日有 N 处改动" / "最后一次写入是 X 分钟前" / 右上角日期星期 / "▲ N writes today" 暂未接线真实数据,属独立待办,改动时请一并立项。

### Modal 详情弹窗（共享组件）

- **入口**: `webui/assets/modal.js` 的 `window.KaguyaModal.open({ title, subtitle, body, actions, onClose })`
- **CSS 骨架**: `webui/assets/shell.css` 末尾的 `.kg-modal-*` 系列 class,严禁在 page-specific style 里覆盖
- **单实例**: 一次只有一个 modal,新 open 会先 close 旧的
- **关闭路径**: backdrop 点击 / ESC / 右上 × 按钮 / 主动 `close()` 调用
- **已接入页面**: Wings (`.d-tile` click → drawer 详情), Graph (`.kg-entity` click → entity 详情聚合两个 KG 端点), Diary (`.drawer[data-diary-date]` click → diary 详情)
- **actions 参数**: 当前三个弹窗都不传,预留给后续 drawer edit/delete PR 使用

### Diary heatmap 联动

- `#hm-grid` 每格带 `data-diary-date` 属性,点击后替换 Today 卡内容为该日 diary
- 前端维护 `diaryByDate` 字典,仅展示已加载的 entry
- Today 卡右上角 "today" 小链接可回到真实今日

### Drawer 写操作（Wings 页）

- **入口**: Wings 页的 drawer modal(`.d-tile` 点击打开),底部 actions 有"编辑"和"删除"两个按钮
- **三态切换**:view(只读展示) / edit(表单) / confirm-delete(内联二次确认),都在同一个 modal 内通过 `KaguyaModal.update()` 切换,不重开 modal
- **保存语义**:前端做脏检查,只把改过的字段发给 `PUT /api/drawers/{id}`。未改字段不传,后端 handler 的 None sentinel 意为"保持原值"
- **删除语义**:硬删不可逆,chroma 向量和 sqlite 元数据同时消失。必须点击"删除" → 确认页 → "确认删除"两步才触发
- **刷新策略**:save/delete 成功后关 modal,局部刷新当前 wing/room 的 drawer 列表,严禁 `location.reload()`
- **错误处理**:后端返回 `{success: false, error: "..."}` 时,edit 态在 modal 内联展示错误,不关闭;其他 HTTP 错误 console.error + modal 内错误横幅

### Drawer 拖拽跨 wing 移动(Wings 页)

- 右侧 `.d-tile` 可拖到左侧 `.wl-item` 的某个 wing 行,释放后弹 modal 确认目标 wing + room(默认原 room 可改)
- 同 wing 内跨 room 拖拽:`.d-tile` 拖到右侧**另一个** `.room-row`,弹同一个 modal,目标 room 预填为落点 room 名(仍可编辑)。落点 `.room-row` 是整个 row(含左侧 meta 区),命中面积足够大
- 落地机制:只调 `PUT /api/drawers/{id}` 传 `{wing, room}`,chroma embedding 不重建(mempalace handler 只在 content 变更时才 re-embed)
- Drop 到非 wl-item / 非 room-row 区域、源 wing 或源 room = 静默失败不弹 modal
- 拖到 `(unassigned)` 桶 = 静默失败(避免把字面量 "(unassigned)" 写进 metadata;如需清空 room 走 drawer 编辑 modal)
- 取消 modal = drawer 保持原位

### Webui 写操作的鉴权边界

- 当前 webui 所有写端点(`PUT /api/drawers/{id}` / `DELETE /api/drawers/{id}`)复用读端点的 Basic Auth + Bearer 翻译
- **不做**二次鉴权层(密码确认 / OTP / 权限 scope),因为 Basic Auth 通过已经代表授权
- **二次确认**在前端 UI 层做(删除的 confirm-delete 态),防止误触,不是鉴权
- 如果未来要分权(读/写/管理员三档),需要在 nginx 层按 location 挂不同 `.htpasswd` 文件,或 inspector 端扩展 scope

### LLM config 后端写端点

- **端点**:`POST/PATCH/DELETE /api/llm/providers[/{id}]` + `POST /api/llm/active` + `POST /api/llm/providers/{id}/models` + `POST /api/llm/providers/{id}/ping`,直接调 `app.core.runtime_config.*` 底层函数
- **与 miniapp 两条并行链路**:miniapp 在 `/miniapp/config/*` 走 Telegram initData 鉴权;webui 在 `/api/llm/*` 走 Basic Auth。两者共享 process-global `runtime_config` 单例
- **API key 语义**:新建必填;PATCH 时空字符串或缺省 = 不改,非空 = rotate。所有响应里 api_key 已脱敏
- **set-active 立即生效**:`app/llm/client.py::chat` 每次请求都从 `runtime_config.get_active_client_config()` 拿配置,set_active 落盘后下一次 LLM 请求立即切换,无需重启 gateway
- **active provider 不可删除**:`runtime_config.delete_provider` 对 active 抛 ValueError,API 返回 409
- **Ping 永远返回 200**:失败情况 `{ok: false, error}`,便于前端统一处理,不和 4xx/5xx 混淆
- **前端入口待接**:`webui/llm.html` 的 UI 改造在独立的下一个 PR 做

### LLM config 前端操作(llm.html)

- **左侧 aside 右上**:`+ 新增` 按钮打开 modal,填 name / base_url / api_key(password 带 show/hide toggle)三字段创建 provider
- **中间 config 面板顶部 4 按钮**:`编辑信息`(只改 name + base_url) / `轮换 key`(单独 modal 只改 api_key) / `刷新模型列表` / `删除 provider`(active provider 时 disabled)
- **Available Models 区域**:每个 model chip 点击展开 action tray,有 `Ping 测试` 和 `Set as Active` 两个按钮。ping 结果以 pill 形式显示在 tray 右侧
- **set-active 护栏**:未 ping 过直接切需要两级确认(按钮变 danger 样式并加一层二级 modal);ping 通过后降为 primary 一级确认
- **所有写后处理**:成功后关 modal → `reloadAndRender()` 重新拉取 config 并重新渲染整页,selectedProviderId 落到刚改的那个 provider 上
- **错误处理**:所有 modal 内部有 `.kg-modal-error` inline banner,API 报错不关 modal,让用户看到 detail 再自行重试

### Runtime config 边界

- **`app/core/runtime_config.py` 是 process-global 单例**:miniapp 和 inspector 共享同一份状态,任一 writer 落盘 → `{state_dir}/llm_config.json` → 所有 reader 立即生效
- **不要复用 miniapp 的 config_routes router**:鉴权不同,错误形状不同。两条链路并行,共享底层模块
- **可以 import miniapp 的纯工具函数**:`_fetch_models` 和 `_validate_base_url` 没有外部状态,webui 侧复用它们避免重复代码

---

## Critical Gotchas

### 绝对不能动的东西

- **`ops/` 目录**：`prompts/` 和 `profiles/` 由项目所有者手工维护。这些是 AI 的身份核心文件，任何自动化修改都可能造成不可逆的身份损坏。**绝对不要读取后修改，绝对不要重新生成，绝对不要 "优化"。**
- **`app/memory/tools.py`**：MemPalace 工具定义，直接从 `mempalace` 包导入。不改。
- **`app/memory/palace.py`**：MemPalace CLI 封装。不改。
- **`app/memory/transcript.py`** 和 **`app/memory/state.py`**：对话记录和状态管理。不改。
- **`app/inspector/logger.py`**：日志格式已稳定。不改。
- **`app/miniapp/auth.py`** 和 **`app/miniapp/sse.py`**：鉴权和 SSE 已实现。不改。
- **Supabase `kaguya-media` 项目的 `images` / `voices` / `message_images` 三张表**：schema 与 gateway 代码耦合，不要手动 DROP / ALTER 字段。新增字段要通过 `Supabase:apply_migration` 走 migration 流程。
- **`runtime/uploads/` 下的文件**：是唯一的媒体存档（图片和语音的字节都在这里）。**不要随意清理**，Supabase 里的 `file_path` 字段全部指向这里的相对路径，一删就再也找不回来。
- **已激活的 MiniMax voice_id**：`kaguya_ja_v1` 已经付过 9.9 元音色解锁费，永久属于本账号。如果被从 MiniMax 删除（比如误调用 delete voice），需要重新克隆 + 再付一次解锁费。**不要去 MiniMax 后台的"声音管理"页面 touch 已激活的音色**。
- **nginx `/etc/nginx/.htpasswd_palace` 和 `/etc/nginx/snippets/inspector_bearer.conf`**:webui Basic Auth + Bearer 覆写的两个凭据文件。**不进 git**。轮换密码时走 `sudo htpasswd -b /etc/nginx/.htpasswd_palace kaguya <new_pw>` + `sudo systemctl reload nginx`。不要手写 file 覆盖。
- **`ops/` 和 `runtime/` 下的实际数据**:ops 是 AI 身份,runtime 是宫殿内容(drawers/KG/diary)。任何自动化清理操作之前必须 `git stash` 或明确备份。
- **`app/core/runtime_config.py` 的 writer 语义**:`add_provider` / `update_provider` / `delete_provider` / `set_active` / `update_models_cache` 五个写函数是唯一合法入口,受 `threading.RLock` 保护,原子落盘。webui 和 miniapp 两套端点都调它们。**不要绕过它们直接改 `llm_config.json` 文件**,也不要在 inspector 或 miniapp 层再加一份独立锁。

### 谨慎修改的东西

- **`app/llm/client.py`** 的 `_run_tool_loop` 逻辑流程：这是 Telegram 端的核心消息处理，只在必要时在循环中插入旁路 dispatch 分支（`elif tool_name in XXX_TOOL_NAMES`），**不要改主流程的状态机**。增加新一类工具的正确做法是新建 `app/llm/<kind>_tools.py`（仿 ops_tools / web_tools / voice_tools 模板），然后在 `_run_tool_loop` 的 dispatch 加一条 `elif` 分支 + 在 `all_tools` 合并里追加 `build_xxx_openai_tools()`。
- **`app/inspector/api.py`** 的现有端点：bearer token 验证保持不变，现有路由不改。可以新增路由。
- **`app/core/config.py`**：加新字段可以，不要改现有字段的含义。
- **`app/media/pipeline.py`** 的 `ingest_image` dedup 逻辑：当前逻辑已专门处理"VL 失败留下的坏记录不毒化缓存"的情况（find 命中但 vl_description 为空 → 重跑 VL + update）。**不要退化回"命中就复用"的天真版本**。
- **VL 模型选型（`VL_MODEL` env）**：实测 `Qwen3-VL-30B-A3B-Instruct` 响应 ~5s，`Qwen3-VL-235B-A22B-Instruct` 顶配 60s+ 超时。**不要默认回 235B**。换模型前先跑真实照片测试。
- **webui 是生产环境**:直接 push 到 main 会立即生效。大改动走 PR,一个 PR 一件事(CSS 调整 / 后端端点 / 前端接线各自独立 PR,方便回滚)。
- **webui 的数据真实性 vs 视觉占位**:某些字段 API 无对应数据(比如 drawer 的 "rev N"、wing 的 triples/tunnels stat),前端现在用 `—` 占位或直接省略。**不要为了美观而伪造数字**——朔夜看一眼就能识破。
- **drawer 没有独立 title 字段**:前端各页展示的 "drawer 标题" 是用 `content_preview` 前 40 字截断伪造的。这是 mempalace 设计层面的事实,不是 bug。如果要让 drawer 有清晰身份,应该在 mempalace 包层面给 drawer 加 `topic` 字段(和 diary 一样),这是独立立项,不要在 webui 前端堆补丁掩盖。
- **drawer 删除是硬删**:调 `mempalace_delete_drawer` handler 会永久移除 chroma 向量和 sqlite metadata,无软删除层。webui 靠前端 confirm-delete 态做误触保护,不要绕过它。如果未来要软删除,应该改 mempalace 包语义,而不是在 webui 前端搞 trash bin。
- **ad-hoc 调 mempalace handler 必须显式设 `MEMPALACE_PALACE_PATH`**:mempalace 包默认读写 `~/.mempalace/`(单机无项目语义时的 fallback),而本项目的真实宫殿在 `runtime/palace/`(由 inspector 在请求时通过 `os.environ["MEMPALACE_PALACE_PATH"] = settings.palace_path` 注入)。任何脱离 inspector 请求上下文的一次性 python 调用或 shell 脚本,必须在命令前显式 `MEMPALACE_PALACE_PATH=/home/ubuntu/apps/kaguya-mempalace/runtime/palace` 否则写入会落到 `~/.mempalace/`,而 inspector 根本看不见。这是生产数据和开发痕迹分离的物理边界,不是 bug。

### 运行时特性

- **Inspector 是守护线程**：跑在 `threading.Thread(daemon=True)` 里，与 Telegram bot 共享进程。
- **LLM 调用在工作线程中**：`_run_tool_loop` 通过 `asyncio.to_thread()` 跑在线程池。
- **MCP Server 是独立进程**：与 Telegram bot 互不依赖，各自独立重启。
- **共享存储**：两个进程通过磁盘上的同一组文件交互（ChromaDB、SQLite KG），不通过 IPC 或网络。单用户场景下并发写入概率极低，文件锁足以处理。

---

## MCP Server 详细设计

### 目标

让 claude.ai 官端通过 Custom Connector 连接到 VPS 上的 MCP Server，直接调用 MemPalace 工具读写记忆。Telegram 端和官端共享同一座记忆宫殿。

### 技术选型

- **SDK**：Python `mcp` 官方包中的 `FastMCP`（`from mcp.server.fastmcp import FastMCP`）
- **Transport**：Streamable HTTP（当前 MCP 协议推荐的生产模式，替代旧的 SSE transport）
- **模式**：`stateless_http=True, json_response=True`（无状态，每个请求独立，适合生产部署）
- **端口**：8766（localhost only），通过 nginx 反代暴露

### 核心实现：`app/mcp/server.py`

职责：

1. **加载环境变量**：从项目 `.env` 文件读取配置，确保 `MEMPALACE_PALACE_PATH` 等环境变量与 Telegram bot 一致
2. **导入工具字典**：`from mempalace.mcp_server import TOOLS`
3. **创建 FastMCP 实例**：`FastMCP("MemPalace", stateless_http=True, json_response=True)`
4. **动态注册所有工具**：遍历 `TOOLS` 字典，将每个工具的 `handler`、`name`、`description`、`input_schema` 注册到 FastMCP
5. **启动服务**：`mcp.run(transport="streamable-http", host="127.0.0.1", port=8766)`

#### 关于 TOOLS 字典的结构

`mempalace.mcp_server.TOOLS` 是一个 `dict[str, dict]`，每个条目形如：

```python
{
    "mempalace_search": {
        "description": "Search the memory palace...",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", ...},
                "wing": {"type": "string", ...},
                "top_k": {"type": "integer", ...},
            },
            ...
        },
        "handler": <callable>,  # 同步函数，接受关键字参数，返回 str 或 dict
    },
    ...
}
```

可参考 `app/memory/tools.py` 中的 `build_openai_tools()` 和 `execute_tool()` 了解这个字典的使用方式。

#### 动态注册工具的实现

FastMCP 注册工具有两条路径：

**路径 A（优先尝试）：用 `mcp.add_tool()` 或底层 `_tool_manager` API**

如果 FastMCP 提供了直接注册已有 handler 的方法（不通过装饰器），优先使用。需要先查看 SDK 源码确认 API 是否存在及其签名。

**路径 B（兜底）：动态生成包装函数**

如果路径 A 不可行，为每个工具创建包装函数：

```python
for name, spec in TOOLS.items():
    handler = spec["handler"]
    description = spec["description"]

    # 闭包捕获 handler 引用
    def make_wrapper(h):
        def wrapper(**kwargs):
            result = h(**kwargs)
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False)
        return wrapper

    # 用 FastMCP 装饰器或 add_tool 注册
    tool_fn = make_wrapper(handler)
    tool_fn.__name__ = name
    tool_fn.__doc__ = description
    mcp.tool(name=name, description=description)(tool_fn)
```

> **注意**：实现前必须先安装 `mcp` 包并查阅 FastMCP 的实际 API。不要假设 API 签名——用 `help()` 或读源码确认。

#### 暴露的工具清单

全量暴露 TOOLS 字典中的所有工具，不做裁剪。截至目前包括（但不限于）：

读取类：`mempalace_search`, `mempalace_kg_query`, `mempalace_kg_timeline`, `mempalace_kg_stats`, `mempalace_diary_read`, `mempalace_list_wings`, `mempalace_list_rooms`, `mempalace_get_taxonomy`, `mempalace_status`, `mempalace_get_aaak_spec`, `mempalace_graph_stats`

写入类：`mempalace_add_drawer`, `mempalace_delete_drawer`, `mempalace_check_duplicate`, `mempalace_kg_add`, `mempalace_kg_invalidate`, `mempalace_diary_write`

结构导航：`mempalace_traverse`, `mempalace_find_tunnels`

### systemd service：`systemd/kaguya-mcp.service`

模仿现有的 `systemd/kaguya-gateway.service` 风格：

- `Description=Kaguya MemPalace MCP Server`
- `WorkingDirectory=/home/ubuntu/apps/kaguya-mempalace`
- `ExecStart=/home/ubuntu/apps/kaguya-mempalace/.venv/bin/python -m app.mcp.server`
- `EnvironmentFile=/home/ubuntu/apps/kaguya-mempalace/.env`（与 gateway 共用同一个 .env）
- `Restart=on-failure`
- `User=ubuntu`

### nginx 配置：`nginx/api.onlykaguya.com.conf`

完整站点配置(miniapp / palace / mcp / exec / HTTPS 等全部路由)存放在 `nginx/api.onlykaguya.com.conf`，和线上 `/etc/nginx/sites-available/api.onlykaguya.com` 1:1 对齐。部署步骤、路由职责、证书管理等说明见 `deploy/README.md` 的「nginx 配置部署」一节。

此前这里嵌入的 `/mcp` 单路由片段已移除——为避免与实际站点配置漂移,样板代码不再在此重复,请直接查阅上述 conf 文件。

### 本地测试脚本：`scripts/test_mcp.py`

用 `mcp` 包的 client API 连接本地 MCP server 并验证：

1. 连接 `http://127.0.0.1:8766/mcp/`（或 FastMCP 的默认 endpoint）
2. 调用 `list_tools`，打印工具列表，验证数量与 TOOLS 字典一致
3. 调用 `mempalace_kg_stats()`，验证返回有效 JSON
4. 调用 `mempalace_search(query="test", top_k=3)`，验证不报错
5. 打印所有结果供人工检查

### MCP Server 不需要做的事

- **不做 autosave / checkpoint**：Telegram 端有自己的自动存档机制，MCP Server 不复制
- **不做 wakeup 刷新**：wakeup.txt 由 Telegram 端的 autosave 流程维护
- **不做 mine_conversations**：对话挖掘是 Telegram 端的职责
- **不做任何 LLM 调用**：MCP Server 只是工具通道，不自己调模型
- **不改现有的任何文件**：MCP Server 是纯增量新建

---

## Environment Variables (.env)

Gateway 和 MCP Server 共用同一个 `.env`。完整模板见 `.env.example`。

**按功能分组**：

| 分组 | 变量 | 说明 |
|------|------|------|
| LLM 主对话 | `OPENROUTER_API_KEY` / `OPENROUTER_BASE_URL` / `OPENROUTER_MODEL` | 主 LLM 模型配置（当前实际指向 bigmodel.cn / GLM-5.1） |
| Telegram | `TELEGRAM_BOT_TOKEN` / `TELEGRAM_ALLOWED_CHAT_IDS` | bot token + 白名单 chat_id |
| 系统目录 | `BASE_DIR` / `PALACE_PATH` / `CHATS_DIR` / `LOGS_DIR` / `STATE_DIR` / `WAKEUP_FILE` | 运行时数据存放位置 |
| 系统行为 | `SYSTEM_NAME` / `AUTOSAVE_USER_MESSAGE_INTERVAL` / `SEARCH_TOP_K` / `RECENT_TURNS` | 常规参数。`SYSTEM_NAME` 值带空格必须加双引号，否则 `source .env` 会报错 |
| Inspector | `INSPECTOR_PORT` / `INSPECTOR_TOKEN` | Inspector API 端口 + bearer token |
| Media 共享 | `KAGUYA_MEDIA_URL` / `KAGUYA_MEDIA_SERVICE_KEY` / `MEDIA_UPLOADS_DIR` | Supabase 元数据 + 本地文件落盘目录 |
| Vision | `SILICONFLOW_API_KEY` / `SILICONFLOW_BASE_URL` / `VL_MODEL` | 硅基流动 API + VL 模型名（推荐 `Qwen/Qwen3-VL-30B-A3B-Instruct`） |
| Web Search | `TAVILY_API_KEY` | Tavily 搜索 API key |
| TTS / Voice | `MINIMAX_API_KEY` / `MINIMAX_GROUP_ID` / `MINIMAX_VOICE_ID_JA` / `MINIMAX_VOICE_ID_ZH` | MiniMax 凭证 + 克隆得到的 voice_id |

**MCP Server 只需要 `PALACE_PATH`**。如果 `mempalace` 包内部通过 `MEMPALACE_PALACE_PATH` 定位数据库，MCP Server 启动时需要设置这个变量。参考 `app/inspector/api.py::_get_chroma_client()` 的做法：

```python
os.environ["MEMPALACE_PALACE_PATH"] = palace_path
```

---

## Coding Conventions

- 所有 Python 文件开头加 `from __future__ import annotations`
- logging 用 stdlib：`logging.getLogger(__name__)`
- 新模块放 `app/` 目录下
- Commit message：Conventional Commits 格式，中文 body
- 新建文件时参考同目录下已有文件的风格

---

## Dependency Note

MCP Server 需要安装 `mcp` Python 包。在实现前：

```bash
cd /home/ubuntu/apps/kaguya-mempalace
.venv/bin/pip install mcp
```

确认安装后可以执行：

```python
from mcp.server.fastmcp import FastMCP
```

如果 `mcp` 包的 FastMCP 不满足需求（比如不支持动态注册工具），备选方案是使用 `fastmcp` 独立包（`pip install fastmcp`，`from fastmcp import FastMCP`）。两者 API 可能略有差异，以实际安装后的 API 为准。
