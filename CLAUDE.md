# CLAUDE.md

## Project Overview

辉夜记忆宫殿（Kaguya MemPalace）：一个 Telegram Bot + MemPalace 记忆系统 + Inspector 监控面板的单用户 AI 伴侣系统。部署在 Ubuntu 24 VPS 上。

## Stack

- **Runtime**: Python 3.11, FastAPI, uvicorn
- **LLM**: OpenAI SDK（走 OpenRouter），非流式工具循环
- **Memory**: MemPalace CLI + ChromaDB（drawers）+ SQLite KG + JSONL 日志
- **Telegram**: python-telegram-bot webhook 模式
- **前端 Mini App**: React 18 + Vite + Tailwind CSS（即将新建）
- **部署**: systemd + nginx 反代

## Commands

```bash
# 后端
cd /home/ubuntu/apps/kaguya-gateway
python main.py                              # 启动
sudo systemctl restart kaguya-gateway       # 重启服务
sudo journalctl -u kaguya-gateway -f        # 实时日志

# 前端 miniapp（新建后）
cd miniapp && npm install
cd miniapp && npm run dev                   # 本地开发
cd miniapp && npm run build                 # 生产构建 → miniapp/dist/
```

## Key Directories

```
/home/ubuntu/apps/kaguya-gateway/
├── main.py                    # 入口
├── gateway/
│   ├── server.py              # FastAPI 主应用，webhook + 路由注册
│   ├── message_handler.py     # 消息处理核心（调 LLM + 工具循环）
│   └── telegram_buffer.py     # Telegram 短消息缓冲 + 拆条发送
├── app/
│   ├── core/config.py         # Settings dataclass
│   ├── llm/client.py          # LLM 调用 + 工具循环（ToolLoopResult）
│   ├── memory/
│   │   ├── palace.py          # MemPalace CLI 封装
│   │   └── tools.py           # OPENAI_TOOLS 定义 + execute_tool
│   ├── inspector/
│   │   ├── api.py             # Inspector REST API（bearer token 鉴权）
│   │   ├── logger.py          # JSONL 日志读写
│   │   └── static/            # Inspector 前端
│   └── miniapp/               # ★ 即将新建 — Mini App 后端模块
│       ├── __init__.py
│       ├── auth.py            # Telegram initData 鉴权
│       ├── sse_manager.py     # SSE 通道管理
│       └── routes.py          # /miniapp/* 路由
├── miniapp/                   # ★ 即将新建 — Mini App 前端
│   ├── src/
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── ops/prompts/               # 外置 prompt 文件（core_identity, writing_constitution, system）
├── ops/profiles/              # 外置 profile 文件（sakuya, kaguya）
└── logs/                      # JSONL 日志目录
    ├── token_usage.jsonl
    ├── tool_calls.jsonl
    └── turn_summaries.jsonl
```

## Architecture Decisions

- **单用户系统**：不做多用户鉴权。Telegram initData 验证 = 足够。
- **SSE 旁路推送**：SSE push 用 `put_nowait`，不阻塞 LLM 主链路。没有 SSE 连接时零开销。
- **Inspector vs Mini App 鉴权分离**：Inspector 用 bearer token（SSH/浏览器访问），Mini App 用 Telegram initData（Telegram 内访问）。两者共享底层查询逻辑，不共享鉴权。
- **数据源**：Mini App 读 JSONL 日志 + MemPalace 工具调用。不依赖 Supabase。
- **非流式 LLM**：当前用 `openai.chat.completions.create()` 无 `stream=True`。SSE 推送的是工具调用过程，不是逐字 thinking/replying。

## Coding Conventions

- Python：类型注解，`from __future__ import annotations`，logging 用 stdlib logger
- 新模块放 `app/` 下，用 `app.xxx.yyy` 的 import 路径
- FastAPI router 用 `APIRouter(prefix=..., tags=[...])`
- 前端：React 函数组件 + hooks，Tailwind utility classes，JSX 扩展名
- Commit：Conventional Commits，中文 body 可以

## Critical Gotchas

- **不要动 `ops/prompts/` 和 `ops/profiles/`**：这些是人格和写作宪法文件，由朔夜手工维护
- **不要改 `app/inspector/api.py` 的鉴权逻辑**：Inspector 的 bearer token 验证保持不变
- **不要改 `app/llm/client.py` 的 LLM 调用逻辑**：只在工具循环中插入 SSE push 旁路
- **不要改 `app/memory/tools.py`**：MemPalace 工具定义不动
- **Vite base 路径**：`vite.config.js` 中 `base: '/miniapp/'` 永远不改
- **Nginx SSE**：SSE 端点需要 `X-Accel-Buffering: no` + `proxy_buffering off`

## Detailed Documentation

当处理 Mini App 相关任务时，先读对应的任务文档：

- `docs/miniapp_spec.md` — Mini App 完整设计规格书
- `docs/tasks/` — 分阶段任务文档
