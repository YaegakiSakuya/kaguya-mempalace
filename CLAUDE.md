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
| LLM | OpenAI SDK → OpenRouter | 非流式工具循环 |
| Memory | MemPalace CLI + ChromaDB + SQLite KG | drawers 存向量，KG 存实体关系 |
| Inspector | FastAPI + uvicorn | 守护线程，端口 8765，bearer token 鉴权 |
| Mini App | React 18 + Vite + Tailwind | 挂在 Inspector 的 FastAPI 上 |
| MCP Server | Python `mcp` 包 (FastMCP) | 独立进程，端口 8766，Streamable HTTP |
| 部署 | systemd + nginx 反代 | HTTPS，域名已配好 |

---

## Commands

```bash
cd /home/ubuntu/apps/kaguya-gateway

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

```
用户消息 → app/main.py::text_message()
  → asyncio.to_thread(generate_reply, ...)
    → app/llm/client.py::_run_tool_loop()       # 同步工具循环（工作线程中）
      → OpenAI API call (非流式)
      → 有 tool_calls? → execute_tool() → 下一轮
      → 无 tool_calls → 返回 reply_text
  → update.message.reply_text(reply)
  → append_turn() + write_turn_summary()        # 存日志
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
| `app/main.py` | 入口。Telegram bot + Inspector 启动 + 消息处理 + autosave | ⚠️ 谨慎 |
| `app/llm/client.py` | LLM 调用 + 工具循环 (`_run_tool_loop`)，SSE 注入点 | ⚠️ 谨慎 |
| `app/core/config.py` | Settings dataclass，从 .env 加载 | ⚠️ 谨慎 |
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
| `nginx/mcp.conf` | nginx 反代配置参考 | ⚠️ 谨慎 |
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
│   │   └── client.py                  # LLM 调用 + 工具循环
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
│   └── wakeup.txt                     # 启动锚点
├── miniapp/                           # React 前端源码
│   ├── src/
│   ├── package.json
│   └── vite.config.js                 # base: '/miniapp/'
├── nginx/                             # nginx 配置参考
│   └── mcp.conf
├── scripts/                           # 实用脚本
│   └── test_mcp.py
├── systemd/
│   ├── kaguya-gateway.service         # Telegram Bot + Inspector
│   └── kaguya-mcp.service            # MCP Server
├── .env                               # 环境变量（gitignored）
├── .env.example                       # 环境变量模板
└── .gitignore
```

---

## Critical Gotchas

### 绝对不能动的东西

- **`ops/` 目录**：`prompts/` 和 `profiles/` 由项目所有者手工维护。这些是 AI 的身份核心文件，任何自动化修改都可能造成不可逆的身份损坏。**绝对不要读取后修改，绝对不要重新生成，绝对不要 "优化"。**
- **`app/memory/tools.py`**：MemPalace 工具定义，直接从 `mempalace` 包导入。不改。
- **`app/memory/palace.py`**：MemPalace CLI 封装。不改。
- **`app/memory/transcript.py`** 和 **`app/memory/state.py`**：对话记录和状态管理。不改。
- **`app/inspector/logger.py`**：日志格式已稳定。不改。
- **`app/miniapp/auth.py`** 和 **`app/miniapp/sse.py`**：鉴权和 SSE 已实现。不改。

### 谨慎修改的东西

- **`app/llm/client.py`** 的 `_run_tool_loop` 逻辑流程：这是 Telegram 端的核心消息处理，只在必要时在循环中插入旁路调用，不要改主流程。
- **`app/inspector/api.py`** 的现有端点：bearer token 验证保持不变，现有路由不改。可以新增路由。
- **`app/core/config.py`**：如果 MCP server 需要新的配置项，可以加，但不要改现有字段的含义。

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
- `WorkingDirectory=/home/ubuntu/apps/kaguya-gateway`
- `ExecStart=/home/ubuntu/apps/kaguya-gateway/.venv/bin/python -m app.mcp.server`
- `EnvironmentFile=/home/ubuntu/apps/kaguya-gateway/.env`（与 gateway 共用同一个 .env）
- `Restart=on-failure`
- `User=ubuntu`

### nginx 配置：`nginx/mcp.conf`

```nginx
# Kaguya MemPalace MCP Server — 放入 nginx server block 内

location /mcp {
    # IP 白名单：仅允许 Anthropic 出站 IP
    allow 160.79.104.0/21;
    deny all;

    # 反代到 MCP server
    # FastMCP 默认 endpoint 是 /mcp，所以用 proxy_pass 不带末尾 /
    # 以保留 /mcp 前缀原样传给 upstream
    proxy_pass http://127.0.0.1:8766;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Streamable HTTP 可能用 SSE streaming，禁用缓冲
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}
```

> **注意**：FastMCP 的 Streamable HTTP 默认 endpoint 是 `/mcp`。nginx `location /mcp`（无末尾 `/`）匹配 `/mcp` 和 `/mcp/...`，`proxy_pass http://127.0.0.1:8766;`（无末尾 `/`）保留请求 URI 原样传给 upstream。

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

MCP Server 与 Telegram Bot 共用同一个 `.env` 文件。MCP Server 只需要其中的：

```
PALACE_PATH=/home/ubuntu/apps/kaguya-gateway/runtime/palace
```

如果 `mempalace` 包内部通过环境变量 `MEMPALACE_PALACE_PATH` 定位数据库，MCP Server 启动时需要设置这个变量。参考 `app/inspector/api.py` 中 `_get_chroma_client()` 的做法：

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
cd /home/ubuntu/apps/kaguya-gateway
.venv/bin/pip install mcp
```

确认安装后可以执行：

```python
from mcp.server.fastmcp import FastMCP
```

如果 `mcp` 包的 FastMCP 不满足需求（比如不支持动态注册工具），备选方案是使用 `fastmcp` 独立包（`pip install fastmcp`，`from fastmcp import FastMCP`）。两者 API 可能略有差异，以实际安装后的 API 为准。
