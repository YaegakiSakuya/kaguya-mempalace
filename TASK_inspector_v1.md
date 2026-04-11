# TASK: Kaguya MemPalace Inspector — 实施计划

> 本文档是给 Claude Code 的任务指令。请严格按照此计划实施，不要自行扩展范围。

## 目标

为 kaguya-gateway 添加一个只读 Inspector 系统：

1. **三份结构化日志**：在 gateway 运行时记录 token usage、tool calls、turn summary
2. **FastAPI Inspector API**：内嵌于 gateway 同进程，直接读现有数据源（ChromaDB、KG SQLite、日志文件）
3. **React 前端**：单个 HTML 文件，通过 API 展示宫殿状态

Inspector 的核心价值：证明宫殿真的在生长，并能指出断点。

---

## Phase 1: 结构化日志埋点

在 gateway 运行时补三份 append-only JSONL 日志。存储位置统一放在 `{LOGS_DIR}/`。

### 1.1 Token Usage 日志

文件：`{LOGS_DIR}/token_usage.jsonl`

**埋点位置**：`app/llm/client.py` → `_run_tool_loop()` 函数

每次 `client.chat.completions.create()` 返回后，提取 `response.usage`，追加一行：

```json
{
  "ts": "2026-04-10T18:02:31Z",
  "turn_type": "reply|checkpoint",
  "round": 1,
  "model": "gpt-5",
  "prompt_tokens": 3812,
  "completion_tokens": 924,
  "total_tokens": 4736,
  "chat_id": "123456"
}
```

**实现要点**：
- `_run_tool_loop` 当前签名没有 `turn_type` 和 `chat_id`。需要新增参数或通过一个 context dict 传入。推荐方案：给 `_run_tool_loop` 加一个可选的 `log_context: dict | None = None` 参数，包含 `turn_type` 和 `chat_id`。
- `generate_reply` 和 `run_memory_checkpoint` 调用时传入对应的 log_context。
- `main.py` 的 `text_message` 和 `run_autosave` 在调用时传入 chat_id。
- usage 可能为 None（某些 provider 不返回），做好防御。
- 写文件用追加模式，不需要加锁（单进程单线程写入）。

### 1.2 Tool Calls 日志

文件：`{LOGS_DIR}/tool_calls.jsonl`

**埋点位置**：`app/llm/client.py` → `_run_tool_loop()` 函数内，`execute_tool()` 调用前后

每次工具执行后追加一行：

```json
{
  "ts": "2026-04-10T18:02:15Z",
  "turn_type": "reply",
  "chat_id": "123456",
  "round": 1,
  "tool_name": "mempalace_add_drawer",
  "arguments_summary": {"wing": "wing_writing", "room": "神楽·设定集"},
  "success": true,
  "result_chars": 142,
  "elapsed_ms": 85,
  "error": null
}
```

**实现要点**：
- `arguments_summary` 不要记录完整的 content 字段（可能很长），只保留 wing/room/entity 等关键标识。写一个 `_summarize_arguments(tool_name, args_dict)` 函数，对每个 tool 提取关键字段。
- 用 `time.monotonic()` 计时。
- 失败时 `success=false`，`error` 记录异常消息。

### 1.3 Turn Summary 日志

文件：`{LOGS_DIR}/turn_summaries.jsonl`

**埋点位置**：`app/main.py` → `text_message()` 函数末尾（在 `append_turn` 之后），以及 `run_autosave()` 中 checkpoint 完成后

每轮对话结束后写一条聚合摘要：

```json
{
  "ts": "2026-04-10T18:02:35Z",
  "turn_type": "reply",
  "chat_id": "123456",
  "turn_id": "turn_20260410_180200_123456",
  "total_prompt_tokens": 5200,
  "total_completion_tokens": 1300,
  "total_rounds": 3,
  "tools_called": ["mempalace_status", "mempalace_search", "mempalace_add_drawer"],
  "tools_succeeded": 3,
  "tools_failed": 0,
  "palace_writes": {
    "drawers_added": 1,
    "kg_triples_added": 0,
    "diary_entries": 0
  }
}
```

**实现要点**：
- 需要 `_run_tool_loop` 返回不仅是 reply text，还要返回本轮的统计数据。推荐方案：让 `_run_tool_loop` 返回一个 `ToolLoopResult` dataclass，包含 `reply_text`、`usage_totals`、`tool_calls_summary`、`palace_writes`。
- `palace_writes` 的统计方式：在 tool call 执行时，根据 tool_name 分类计数。`mempalace_add_drawer` → drawers_added +1，`mempalace_kg_add` → kg_triples_added +1，`mempalace_diary_write` → diary_entries +1。
- `generate_reply` 和 `run_memory_checkpoint` 的返回类型也相应改为返回 `ToolLoopResult`（或者让它们内部处理日志写入后只返回 text，保持向后兼容）。推荐后者：在 `_run_tool_loop` 内部完成所有日志写入，外部接口不变。

### 1.4 日志写入工具函数

新建 `app/inspector/logger.py`：

```python
"""Structured JSONL logger for Inspector observability."""

import json
import time
from pathlib import Path
from datetime import datetime, timezone


def append_jsonl(path: Path, record: dict) -> None:
    """Append a single JSON record to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, default=str)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
```

---

## Phase 2: FastAPI Inspector API

### 2.1 架构

在 gateway 的 `main.py` 中，启动 Telegram polling 之前，用 `uvicorn` 在后台线程启动 FastAPI app。共享同一个 `Settings` 实例。

新建 `app/inspector/` 包：

```
app/inspector/
  __init__.py
  api.py          # FastAPI app 定义和路由
  logger.py       # Phase 1 的日志工具
```

### 2.2 启动方式

在 `app/main.py` 的 `main()` 函数中：

```python
import threading
import uvicorn
from app.inspector.api import create_inspector_app

def main() -> None:
    settings = load_settings()
    configure_logging(settings.logs_dir)

    # Start Inspector API in background thread
    inspector_app = create_inspector_app(settings)
    inspector_thread = threading.Thread(
        target=uvicorn.run,
        kwargs={
            "app": inspector_app,
            "host": "0.0.0.0",
            "port": int(os.getenv("INSPECTOR_PORT", "8765")),
            "log_level": "warning",
        },
        daemon=True,
    )
    inspector_thread.start()

    # Start Telegram bot (blocking)
    application = build_application(settings)
    application.run_polling(drop_pending_updates=False)
```

### 2.3 认证

从 `.env` 读 `INSPECTOR_TOKEN`。所有 API 请求需要 `Authorization: Bearer {token}` 或 query param `?token={token}`（方便手机浏览器书签）。

无 token 配置时 Inspector 不启动（安全默认）。

### 2.4 API 路由

以下所有路由都是 **只读** 的。

#### Palace 数据（直接读 ChromaDB）

```
GET /api/overview
```
返回：总 drawer 数、wing 数、room 数、KG entity/triple 数、最近10条 tool calls、最近5条 diary entries。

```
GET /api/taxonomy
```
调用 `mempalace.mcp_server` 的 `tool_get_taxonomy()` 函数。

```
GET /api/wings
```
调用 `tool_list_wings()`。

```
GET /api/rooms?wing={wing}
```
调用 `tool_list_rooms(wing)`。

```
GET /api/drawers?wing={wing}&room={room}&limit=50
```
从 ChromaDB 按 metadata 过滤读取 drawer 列表（id、content 前200字、metadata）。

```
GET /api/search?q={query}&limit=10&wing={wing}
```
调用 `mempalace.searcher.search_memories()` 或 `Layer3.search_raw()`。

#### KG 数据（直接读 SQLite）

```
GET /api/kg/stats
```
调用 `KnowledgeGraph.stats()`。

```
GET /api/kg/entities?limit=100
```
直接查 SQLite `SELECT * FROM entities ORDER BY created_at DESC LIMIT ?`。

```
GET /api/kg/triples?entity={entity}&limit=100
```
调用 `KnowledgeGraph.query_entity(entity, direction="both")`。

```
GET /api/kg/timeline?entity={entity}
```
调用 `KnowledgeGraph.timeline(entity)`。

#### Graph 数据（实时计算）

```
GET /api/graph/stats
```
调用 `palace_graph.graph_stats()`。

```
GET /api/graph/nodes
```
调用 `palace_graph.build_graph()`，返回 nodes dict。

```
GET /api/graph/tunnels?wing_a={}&wing_b={}
```
调用 `palace_graph.find_tunnels(wing_a, wing_b)`。

#### Diary

```
GET /api/diary?agent=kaguya&limit=20
```
调用 `tool_diary_read(agent_name, last_n)`。

#### 日志数据（读 JSONL 文件）

```
GET /api/usage?last_n=50
```
读 `token_usage.jsonl` 最后 N 行。

```
GET /api/tools/calls?last_n=50
```
读 `tool_calls.jsonl` 最后 N 行。

```
GET /api/turns?last_n=20
```
读 `turn_summaries.jsonl` 最后 N 行。

### 2.5 JSONL 读取工具

```python
def read_jsonl_tail(path: Path, last_n: int = 50) -> list[dict]:
    """Read the last N lines of a JSONL file."""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    lines = lines[-last_n:]
    results = []
    for line in lines:
        line = line.strip()
        if line:
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return results
```

对于大文件（>10MB），改用从文件尾部逐行读取的方式，不要一次性读入内存。

### 2.6 MemPalace 实例管理

Inspector API 需要读 ChromaDB 和 KG SQLite。

```python
from mempalace.config import MempalaceConfig
from mempalace.knowledge_graph import KnowledgeGraph
from mempalace.palace_graph import build_graph, graph_stats, find_tunnels
import chromadb
import os

def _get_collection(settings):
    os.environ["MEMPALACE_PALACE_PATH"] = str(settings.palace_path)
    client = chromadb.PersistentClient(path=str(settings.palace_path))
    try:
        return client.get_collection("mempalace_drawers")
    except Exception:
        return None

def _get_kg(settings):
    db_path = settings.palace_path / "knowledge_graph.sqlite3"
    return KnowledgeGraph(db_path=str(db_path))
```

**注意**：ChromaDB PersistentClient 实例不要在模块级创建，在每个请求中创建或者用一个带缓存的 getter。KG SQLite 使用 WAL 模式，并发读安全。

---

## Phase 3: React 前端

### 3.1 部署方式

单个 `index.html` 文件，由 FastAPI 通过 `StaticFiles` 或直接返回。存放位置：`app/inspector/static/index.html`。

FastAPI 路由：
```python
@app.get("/")
async def serve_frontend():
    return FileResponse("app/inspector/static/index.html")
```

### 3.2 技术选择

- React 18 via CDN (`<script src="https://cdn.jsdelivr.net/npm/react@18/umd/react.production.min.js">`)
- Babel standalone for JSX（或预编译）
- Recharts via CDN 用于图表
- 不用 build 工具，不用 npm，不用 Vite
- 纯 fetch 调用 API
- 移动端优先的响应式布局

### 3.3 页面结构（5个 tab）

#### Tab 1: Overview

一屏总览：
- Palace 状态卡片：总 drawers / wings / rooms / KG entities / KG triples
- 最近24h 新增统计（从 turn_summaries.jsonl 聚合）
- 最近10条 tool calls（简表：时间、工具名、成功/失败）
- 最近5条 diary entries（标题+时间）
- 最近3轮对话摘要

数据源：`GET /api/overview` + `GET /api/tools/calls?last_n=10` + `GET /api/turns?last_n=3`

#### Tab 2: Palace

左侧 wing 列表（可折叠），点击展开 rooms，点击 room 展示 drawer 列表。

移动端：逐层钻入（wing 列表 → room 列表 → drawer 列表 → drawer 详情）。

数据源：`GET /api/taxonomy` → `GET /api/drawers?wing=...&room=...`

#### Tab 3: KG

- 顶部：KG stats 卡片（entities / triples / current / expired / relationship types）
- Entity 列表（可搜索），点击展开关系
- 关系展示用简单的表格或列表，不做力导向图（第一版）

数据源：`GET /api/kg/stats` → `GET /api/kg/entities` → `GET /api/kg/triples?entity=...`

KG 图谱可视化留到第二版。第一版用列表 + 关系展开即可。

#### Tab 4: Usage

- Token 消耗折线图（按天聚合，prompt vs completion 分色）
- 每轮对话的 token 柱状图
- 工具调用频次统计

数据源：`GET /api/usage?last_n=200` + `GET /api/turns?last_n=50`

#### Tab 5: Trace

最近 N 轮对话的详细追踪：
- 调了哪些工具，参数摘要，成功/失败
- 本轮推动了什么生长（drawers_added / kg_triples_added / diary_entries）
- Token 消耗

数据源：`GET /api/turns?last_n=20` + `GET /api/tools/calls?last_n=100`

### 3.4 认证

页面首次加载时检查 URL 的 `?token=` 参数，存入 `localStorage`。后续所有 fetch 请求带 `Authorization: Bearer {token}` header。无 token 时显示输入框。

### 3.5 自动刷新

每个 tab 的数据每 30 秒自动轮询刷新。Overview 页面 15 秒刷新。

---

## 实施顺序

请严格按以下顺序实施：

1. **创建 `app/inspector/` 包**：`__init__.py` + `logger.py`
2. **修改 `app/llm/client.py`**：添加日志埋点（token usage + tool calls + turn summary 统计）
3. **修改 `app/main.py`**：添加 turn summary 日志写入 + Inspector API 启动
4. **创建 `app/inspector/api.py`**：FastAPI 路由实现
5. **创建 `app/inspector/static/index.html`**：React 前端
6. **更新 `.env.example`**：添加 `INSPECTOR_PORT` 和 `INSPECTOR_TOKEN`
7. **测试**：确保 gateway 正常启动，Inspector API 可访问，前端能加载数据

## 约束

- **不要修改 MemPalace 包本身**。所有改动限于 kaguya-gateway 仓库。
- **Inspector 是只读的**。不通过 Inspector 写入 palace、KG 或 diary。
- **不要引入新的 ORM 或数据库**。直接读现有数据源。
- **不要做事件源/投影/读模型复制**。直接读 ChromaDB 和 SQLite。
- **前端不使用 npm/build 工具**。单 HTML 文件 + CDN。
- **新增依赖限于**：`fastapi`、`uvicorn`（已在 venv 中随 mempalace 安装）。

## 新增文件清单

```
app/inspector/__init__.py
app/inspector/logger.py
app/inspector/api.py
app/inspector/static/index.html
```

## 修改文件清单

```
app/llm/client.py          # 添加日志埋点
app/main.py                 # 添加 turn summary + Inspector 启动
app/core/config.py          # 可选：添加 inspector_port / inspector_token 到 Settings
.env.example                # 添加 INSPECTOR_PORT / INSPECTOR_TOKEN
```
