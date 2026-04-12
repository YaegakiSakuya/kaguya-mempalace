# Phase 1：后端 SSE 管线 + Mini App 路由

## 目标

在现有 Inspector FastAPI app 上扩展 Mini App 路由，实现 SSE 实时推送和宫殿查询 API。

## 前置理解

**必读文件**（先读完再动手）：
- `app/main.py` — 入口，理解 Inspector 如何在守护线程中启动
- `app/llm/client.py` — 理解 `_run_tool_loop()` 的工具循环结构
- `app/inspector/api.py` — 理解 `create_inspector_app()` 工厂函数结构

**关键事实**：
- Inspector FastAPI app 在守护线程中运行（`threading.Thread(daemon=True)`），端口 8765
- `_run_tool_loop()` 是同步函数，通过 `asyncio.to_thread()` 在工作线程中执行
- SSE push 会从工作线程调用，`queue.put_nowait()` 本身是线程安全的
- Mini App 路由直接加到 `create_inspector_app()` 返回的同一个 FastAPI app 上

---

## 任务 A：创建 `app/miniapp/` 模块

### A1：`app/miniapp/__init__.py`

空文件。

### A2：`app/miniapp/sse.py` — 线程安全的 SSE 管理器

```python
"""线程安全的单用户 SSE 通道管理器。

_run_tool_loop() 在工作线程中运行，push() 从工作线程调用。
asyncio.Queue.put_nowait() 本身是线程安全的。
"""
from __future__ import annotations

import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class SSEManager:
    def __init__(self) -> None:
        self._queue: asyncio.Queue | None = None

    def has_active_connection(self) -> bool:
        return self._queue is not None

    async def connect(self) -> asyncio.Queue:
        if self._queue is not None:
            try:
                self._queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
        self._queue = asyncio.Queue(maxsize=256)
        logger.info("sse_connected")
        return self._queue

    def push(self, event: str, data: dict) -> None:
        """非阻塞推送。从任意线程调用安全。"""
        if self._queue is None:
            return
        try:
            payload = json.dumps(data, ensure_ascii=False)
            self._queue.put_nowait({"event": event, "data": payload})
        except asyncio.QueueFull:
            logger.warning("sse_queue_full event=%s", event)
        except Exception:
            pass

    async def disconnect(self) -> None:
        if self._queue is not None:
            try:
                self._queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            self._queue = None
            logger.info("sse_disconnected")


# 全局单例
sse_manager = SSEManager()
```

### A3：`app/miniapp/auth.py` — Telegram initData 鉴权

```python
"""Telegram Mini App initData HMAC-SHA256 验证。"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse

from fastapi import HTTPException, Request

AUTH_MAX_AGE = 86400  # 24小时


async def verify_telegram_init_data(request: Request) -> dict:
    init_data = (
        request.headers.get("X-Telegram-Init-Data")
        or request.query_params.get("initData")
    )
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData")

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    if not bot_token:
        raise HTTPException(status_code=500, detail="Bot token not configured")

    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", "")
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing hash")

    auth_date_str = parsed.get("auth_date", "0")
    try:
        auth_date = int(auth_date_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid auth_date")

    if time.time() - auth_date > AUTH_MAX_AGE:
        raise HTTPException(status_code=401, detail="initData expired")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid signature")

    user_data = {}
    if "user" in parsed:
        try:
            user_data = json.loads(parsed["user"])
        except json.JSONDecodeError:
            pass
    return user_data
```

---

## 任务 B：在 Inspector app 中注册 miniapp 路由

**文件**：`app/inspector/api.py`

在 `create_inspector_app()` 函数中，在 `return app` 之前，添加 miniapp 路由注册。

### B1：在文件顶部添加 import

```python
import asyncio
from fastapi.responses import StreamingResponse
from app.miniapp.sse import sse_manager
from app.miniapp.auth import verify_telegram_init_data
```

### B2：在 `return app` 之前添加以下路由块

```python
    # ===== Mini App 路由 =====

    # SSE 流（initData 通过 query param 传入，EventSource 不支持自定义 header）
    @app.get("/miniapp/stream")
    async def miniapp_sse_stream(request: Request, initData: str = Query(default="")):
        queue = await sse_manager.connect()

        async def event_generator():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=30.0)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    if item is None:
                        break
                    yield f"event: {item['event']}\ndata: {item['data']}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                await sse_manager.disconnect()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 以下路由走 Telegram initData 鉴权
    miniapp_auth = [Depends(verify_telegram_init_data)]

    @app.get("/miniapp/history", dependencies=miniapp_auth)
    async def miniapp_history(limit: int = Query(default=20, le=100)):
        items = read_jsonl_tail(settings.logs_dir / "turn_summaries.jsonl", limit)
        items.reverse()
        return {"items": items}

    @app.get("/miniapp/history/tools", dependencies=miniapp_auth)
    async def miniapp_tool_history(limit: int = Query(default=50, le=200)):
        items = read_jsonl_tail(settings.logs_dir / "tool_calls.jsonl", limit)
        items.reverse()
        return {"items": items}

    @app.get("/miniapp/palace/overview", dependencies=miniapp_auth)
    async def miniapp_palace_overview():
        """复用 overview 的查询逻辑，返回宫殿统计。"""
        # 直接调用已有的 overview 端点逻辑
        return await overview()

    @app.get("/miniapp/palace/wings", dependencies=miniapp_auth)
    async def miniapp_palace_wings():
        return await list_wings()

    @app.get("/miniapp/palace/rooms", dependencies=miniapp_auth)
    async def miniapp_palace_rooms(wing: str = Query(...)):
        return await list_rooms(wing=wing)

    @app.get("/miniapp/palace/drawers", dependencies=miniapp_auth)
    async def miniapp_palace_drawers(
        wing: str = Query(default=""),
        room: str = Query(default=""),
        limit: int = Query(default=20, le=100),
        offset: int = Query(default=0, ge=0),
    ):
        return await list_drawers(wing=wing, room=room, limit=limit, offset=offset)

    @app.get("/miniapp/palace/diary", dependencies=miniapp_auth)
    async def miniapp_palace_diary(limit: int = Query(default=10, le=50)):
        return await diary(agent="kaguya", limit=limit)

    @app.get("/miniapp/palace/kg", dependencies=miniapp_auth)
    async def miniapp_palace_kg():
        return await kg_stats()
```

**要点**：miniapp 路由直接调用同文件中已定义的 `overview()`、`list_wings()` 等 async 函数，避免重复代码。这些函数本身不带鉴权（鉴权在 route decorator 上），所以内部调用安全。

---

## 任务 C：在 LLM 工具循环中注入 SSE 推送

**文件**：`app/llm/client.py`

### C1：在文件顶部添加 import

在现有 import 块末尾添加：

```python
from app.miniapp.sse import sse_manager
```

### C2：修改 `_run_tool_loop()` 函数

找到 `_run_tool_loop` 函数。需要在以下 4 个位置插入 SSE push：

**位置 1**：函数开头，`result = ToolLoopResult(reply_text="")` 之后，`for round_index` 之前：

```python
    loop_start = time.monotonic()

    if sse_manager.has_active_connection():
        sse_manager.push("processing", {
            "step": "start",
            "message": "正在处理消息...",
        })
```

**位置 2**：在 `for tool_call in tool_calls:` 循环内部，`t0 = time.monotonic()` 之前：

```python
                if sse_manager.has_active_connection():
                    sse_manager.push("tool_call", {
                        "tool": tool_name,
                        "round": round_index + 1,
                        "args_summary": summarize_arguments(tool_name, args_dict),
                    })
```

**位置 3**：在同一循环内部，工具执行完成后（`append_jsonl(...)` 调用之后）：

```python
                if sse_manager.has_active_connection():
                    sse_manager.push("tool_done", {
                        "tool": tool_name,
                        "round": round_index + 1,
                        "success": success,
                        "duration_ms": elapsed_ms,
                    })
```

**位置 4**：在函数末尾，`result.reply_text = reply` 之后，`return result` 之前：

```python
        total_elapsed = int((time.monotonic() - loop_start) * 1000)
        if sse_manager.has_active_connection():
            sse_manager.push("done", {
                "input_tokens": result.total_prompt_tokens,
                "output_tokens": result.total_completion_tokens,
                "rounds": result.total_rounds,
                "tools": result.tools_called,
                "tools_succeeded": result.tools_succeeded,
                "tools_failed": result.tools_failed,
                "palace_writes": result.palace_writes,
                "elapsed_ms": total_elapsed,
                "response_preview": reply[:200] if reply else "",
            })
```

### 关键约束

- `sse_manager.push()` 是 `put_nowait()`，不阻塞，从工作线程调用安全
- `has_active_connection()` 为 False 时直接跳过，零开销
- `summarize_arguments` 已在 `app/inspector/logger.py` 中定义，已经 import 了
- **不改变任何现有逻辑流程**

---

## 验收标准

1. `python -m app.main` 启动无报错，Inspector 在 8765 端口正常服务
2. 现有 Inspector 端点（`/api/overview` 等）功能不受影响
3. `curl -N "http://localhost:8765/miniapp/stream"` 建立 SSE 连接，收到 keepalive
4. `curl -H "X-Telegram-Init-Data: test" http://localhost:8765/miniapp/palace/overview` 返回宫殿统计
5. `curl -H "X-Telegram-Init-Data: test" http://localhost:8765/miniapp/history` 返回对话历史
6. 在 Telegram 发消息后，SSE 流收到 `processing` → `tool_call`/`tool_done` → `done` 事件
7. SSE 连接断开后消息处理不受影响

## Commit

```
feat(miniapp): Phase 1 — SSE 管线 + Mini App REST 路由

- 新增 app/miniapp/ (auth + sse)
- 在 Inspector app 中注册 /miniapp/* 路由
- 在 _run_tool_loop 中注入 SSE 旁路推送
- miniapp 路由复用 Inspector 已有查询逻辑
```
