# CLAUDE.md

## Project Overview

辉夜记忆宫殿（Kaguya MemPalace）：Telegram Bot + MemPalace 记忆系统 + Inspector 监控面板。单用户 AI 伴侣系统，部署在 Ubuntu VPS。

## Stack

- **Runtime**: Python 3.11, python-telegram-bot (polling 模式)
- **LLM**: OpenAI SDK 走 OpenRouter，非流式工具循环
- **Memory**: MemPalace CLI + ChromaDB (drawers) + SQLite KG + JSONL 日志
- **Inspector**: FastAPI + uvicorn，后台守护线程，端口 8765，bearer token 鉴权
- **Mini App**: React 18 + Vite + Tailwind（即将新建），挂在 Inspector 同一个 FastAPI app 上
- **部署**: systemd (`kaguya-gateway.service`) + nginx 反代

## Commands

```bash
cd /home/ubuntu/apps/kaguya-gateway

# 启动（前台）
.venv/bin/python -m app.main

# systemd
sudo systemctl restart kaguya-gateway
sudo journalctl -u kaguya-gateway -f

# 前端 miniapp（新建后）
cd miniapp && npm install && npm run build
```

## Architecture

```
app/main.py                          # 入口：启动 Telegram bot (polling) + Inspector (守护线程)
├── python-telegram-bot polling      # 消息入口：text_message() → generate_reply()
├── Inspector FastAPI (port 8765)    # 后台守护线程，bearer token 鉴权
│   └── 即将扩展：/miniapp/* 路由    # Telegram initData 鉴权，SSE 流
└── autosave/checkpoint              # 定期存档到 MemPalace
```

消息处理链路（全部在 app/main.py::text_message 中）：
```
用户消息 → text_message()
  → asyncio.to_thread(generate_reply, ...)     # 跳到线程池
    → app/llm/client.py::_run_tool_loop()       # 同步工具循环（在工作线程中）
      → OpenAI API call (非流式)
      → tool_calls? → execute_tool() → 下一轮
      → 无 tool_calls → 返回 reply_text
  → update.message.reply_text(reply)            # 发回 Telegram
  → append_turn() + write_turn_summary()        # 存日志
```

## Key Files

| 文件 | 职责 |
|------|------|
| `app/main.py` | 入口。Telegram bot + Inspector 启动 + 消息处理 + autosave |
| `app/llm/client.py` | LLM 调用 + 工具循环 (`_run_tool_loop`)。**SSE 注入点在这里** |
| `app/core/config.py` | Settings dataclass，从 .env 加载 |
| `app/memory/tools.py` | MemPalace 工具定义 + `execute_tool()` |
| `app/memory/palace.py` | MemPalace CLI 封装（wakeup / status / mine） |
| `app/memory/transcript.py` | 对话记录读写（markdown 格式） |
| `app/memory/state.py` | 消息计数状态 |
| `app/inspector/api.py` | Inspector REST API（FastAPI app 工厂）。**miniapp 路由扩展在这里** |
| `app/inspector/logger.py` | JSONL 日志读写 + `summarize_arguments()` |
| `ops/prompts/` | 外置 prompt（core_identity / writing_constitution / system）**不要动** |
| `ops/profiles/` | 外置 profile（sakuya / kaguya）**不要动** |

## Directory Structure

```
kaguya-mempalace/
├── app/
│   ├── main.py
│   ├── core/config.py
│   ├── llm/client.py
│   ├── memory/{tools,palace,transcript,state}.py
│   ├── inspector/{api,logger}.py
│   ├── inspector/static/index.html
│   ├── bot/                           # 目前为空
│   └── miniapp/                       # ★ 即将新建
│       ├── __init__.py
│       ├── auth.py                    # Telegram initData 鉴权
│       └── sse.py                     # SSE 管理器（线程安全）
├── ops/
│   ├── prompts/{core_identity,writing_constitution,system}.md
│   └── profiles/{sakuya,kaguya}.md
├── runtime/                           # gitignored，运行时数据
│   ├── palace/                        # ChromaDB
│   ├── chats/                         # 对话 markdown
│   ├── logs/                          # JSONL 日志
│   ├── state/                         # 消息计数
│   └── wakeup.txt
├── miniapp/                           # ★ 即将新建 — React 前端
├── systemd/kaguya-gateway.service
└── .env
```

## Critical Gotchas

- **不要动 `ops/`**：prompts 和 profiles 由朔夜手工维护
- **不要改 Inspector 现有端点的鉴权**：bearer token 验证保持不变
- **不要改 `_run_tool_loop` 的逻辑流程**：只在循环中插入 SSE push 旁路调用
- **不要改 `app/memory/tools.py`**：MemPalace 工具定义不动
- **Inspector 是守护线程**：跑在 `threading.Thread(daemon=True)` 里，与 Telegram bot 共享进程
- **LLM 调用在工作线程中**：`_run_tool_loop` 通过 `asyncio.to_thread()` 跑在线程池。SSE push 从工作线程调用，需要线程安全
- **Vite base 路径**：`vite.config.js` 中 `base: '/miniapp/'`

## Coding Conventions

- `from __future__ import annotations`
- logging 用 stdlib `logging.getLogger(__name__)`
- 新模块放 `app/` 下
- Commit：Conventional Commits，中文 body
