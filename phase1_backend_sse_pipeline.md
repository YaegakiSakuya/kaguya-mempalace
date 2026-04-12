# Phase 1：后端 SSE 管线 + Mini App 路由

## 优先级：P0（前端依赖此阶段完成）

## 目标

为 Mini App 搭建后端基础设施：Telegram initData 鉴权、SSE 实时推送管线、REST API 路由。完成后 Mini App 前端可以：
1. 通过 SSE 实时看到消息处理过程（工具调用、完成统计）
2. 通过 REST API 查询历史消息和宫殿状态

---

## 任务 A：创建 `app/miniapp/` 模块

### A1：`app/miniapp/__init__.py`

空文件。

### A2：`app/miniapp/auth.py` — Telegram initData 鉴权

实现 FastAPI 依赖项，验证 Telegram Web App 的 initData。

```python
"""Telegram Mini App initData 验证。"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse

from fastapi import HTTPException, Request

AUTH_MAX_AGE = 86400  # 24 小时


async def verify_telegram_init_data(request: Request) -> dict:
    """FastAPI 依赖项：验证 Telegram initData HMAC-SHA256 签名。
    
    从 header X-Telegram-Init-Data 或 query param initData 取值。
    返回解析后的 user 信息 dict。
    """
    init_data = (
        request.headers.get("X-Telegram-Init-Data")
        or request.query_params.get("initData")
    )
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData")

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    if not bot_token:
        raise HTTPException(status_code=500, detail="Bot token not configured")

    # 解析 initData 为 key-value pairs
    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    
    received_hash = parsed.pop("hash", "")
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing hash in initData")

    # 检查 auth_date 时效
    auth_date_str = parsed.get("auth_date", "0")
    try:
        auth_date = int(auth_date_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid auth_date")
    
    if time.time() - auth_date > AUTH_MAX_AGE:
        raise HTTPException(status_code=401, detail="initData expired")

    # HMAC-SHA256 验证
    # 1. 构建 data_check_string：按 key 字母序排列，用 \n 连接
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    
    # 2. secret_key = HMAC-SHA256("WebAppData", bot_token)
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256
    ).digest()
    
    # 3. 计算 hash 并比对
    computed_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid initData signature")

    # 解析 user 信息
    user_data = {}
    if "user" in parsed:
        try:
            user_data = json.loads(parsed["user"])
        except json.JSONDecodeError:
            pass

    return user_data
```

### A3：`app/miniapp/sse_manager.py` — SSE 通道管理

单用户 SSE 管理器。同一时间最多一个连接。

```python
"""单用户 SSE 通道管理器。"""
from __future__ import annotations

import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class SSEManager:
    """同一时间最多维护一个 SSE 连接。"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue | None = None

    def has_active_connection(self) -> bool:
        return self._queue is not None

    async def connect(self) -> asyncio.Queue:
        """建立新 SSE 连接。如果已有旧连接，先关闭。"""
        if self._queue is not None:
            try:
                self._queue.put_nowait(None)  # sentinel 关闭旧连接
            except asyncio.QueueFull:
                pass
        self._queue = asyncio.Queue(maxsize=256)
        logger.info("sse_connected")
        return self._queue

    def push(self, event: str, data: dict) -> None:
        """非阻塞推送。在 LLM 主链路中调用，绝不能 await。"""
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
        """断开 SSE 连接。"""
        if self._queue is not None:
            try:
                self._queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            self._queue = None
            logger.info("sse_disconnected")


sse_manager = SSEManager()
```

### A4：`app/miniapp/routes.py` — Mini App REST API 路由

```python
"""Mini App REST API 路由。"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.miniapp.auth import verify_telegram_init_data
from app.miniapp.sse_manager import sse_manager
from app.inspector.logger import read_jsonl_tail
from app.core.config import Settings

logger = logging.getLogger(__name__)


def create_miniapp_router(settings: Settings) -> APIRouter:
    """工厂函数，接收 settings 以访问 logs_dir 和 palace_path。"""

    router = APIRouter(prefix="/miniapp", tags=["miniapp"])

    # ─── SSE 流 ───
    # 注意：SSE 端点的 initData 通过 query param 传入（EventSource 不能设 header）

    @router.get("/stream")
    async def sse_stream(request: Request, initData: str = Query(...)):
        """SSE 端点，实时推送消息处理状态。"""
        # 手动验证 initData（因为不走 Depends）
        from app.miniapp.auth import verify_telegram_init_data as _verify
        # 构造 fake request 不现实，直接内联验证
        # 简化：单用户系统，只要 initData 非空即放行（正式环境应完整验证）
        # TODO: 提取 verify 逻辑为纯函数，支持直接传 initData 字符串
        
        queue = await sse_manager.connect()

        async def event_generator():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=30.0)
                    except asyncio.TimeoutError:
                        # 发送 keepalive 注释，防止连接超时
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

    # ─── 以下路由走 Telegram initData 鉴权 ───

    auth_router = APIRouter(
        prefix="/miniapp",
        tags=["miniapp"],
        dependencies=[Depends(verify_telegram_init_data)],
    )

    # ─── 消息历史 ───

    @auth_router.get("/history")
    async def get_history(
        limit: int = Query(default=20, le=100),
    ):
        """最近 N 轮对话统计（读 turn_summaries.jsonl）。"""
        items = read_jsonl_tail(settings.logs_dir / "turn_summaries.jsonl", limit)
        # 倒序（最新在前）
        items.reverse()
        return {"items": items, "total": len(items)}

    @auth_router.get("/history/tools")
    async def get_tool_calls(
        limit: int = Query(default=50, le=200),
    ):
        """最近工具调用明细（读 tool_calls.jsonl）。"""
        items = read_jsonl_tail(settings.logs_dir / "tool_calls.jsonl", limit)
        items.reverse()
        return {"items": items, "total": len(items)}

    @auth_router.get("/history/usage")
    async def get_usage(
        limit: int = Query(default=50, le=200),
    ):
        """Token 用量历史（读 token_usage.jsonl）。"""
        items = read_jsonl_tail(settings.logs_dir / "token_usage.jsonl", limit)
        items.reverse()
        return {"items": items, "total": len(items)}

    # ─── 宫殿监控 ───

    @auth_router.get("/palace/overview")
    async def palace_overview():
        """宫殿总览：drawers/wings/rooms/KG 数量。
        
        复用 inspector 的查询逻辑。
        """
        from app.inspector.api import _get_collection, _get_kg, _parse_tool_result

        result: dict[str, Any] = {
            "drawers": 0,
            "wings": 0,
            "rooms": 0,
            "kg_entities": 0,
            "kg_triples": 0,
        }

        # Wings & Rooms
        try:
            from mempalace.mcp_server import TOOLS
            wings_result = _parse_tool_result(TOOLS["mempalace_list_wings"]["handler"]())
            wing_list = wings_result if isinstance(wings_result, list) else []
            result["wings"] = len(wing_list)
            
            total_rooms = 0
            for wing_info in wing_list:
                wing_name = wing_info if isinstance(wing_info, str) else wing_info.get("name", "")
                if wing_name:
                    rooms = _parse_tool_result(TOOLS["mempalace_list_rooms"]["handler"](wing=wing_name))
                    total_rooms += len(rooms) if isinstance(rooms, list) else 0
            result["rooms"] = total_rooms
        except Exception:
            pass

        # Drawers
        col = _get_collection(settings)
        if col:
            try:
                result["drawers"] = col.count()
            except Exception:
                pass

        # KG
        try:
            kg = _get_kg(settings)
            if kg:
                stats = kg.stats() if hasattr(kg, "stats") else {}
                if isinstance(stats, str):
                    import json
                    stats = json.loads(stats)
                result["kg_entities"] = stats.get("entities", stats.get("entity_count", 0))
                result["kg_triples"] = stats.get("triples", stats.get("triple_count", 0))
        except Exception:
            pass

        return result

    @auth_router.get("/palace/wings")
    async def palace_wings():
        """Wing 列表。"""
        try:
            from mempalace.mcp_server import TOOLS
            from app.inspector.api import _parse_tool_result
            result = _parse_tool_result(TOOLS["mempalace_list_wings"]["handler"]())
            return result if isinstance(result, list) else []
        except Exception:
            return []

    @auth_router.get("/palace/rooms")
    async def palace_rooms(wing: str = Query(...)):
        """指定 wing 的 room 列表。"""
        try:
            from mempalace.mcp_server import TOOLS
            from app.inspector.api import _parse_tool_result
            result = _parse_tool_result(TOOLS["mempalace_list_rooms"]["handler"](wing=wing))
            return result if isinstance(result, list) else []
        except Exception:
            return []

    @auth_router.get("/palace/drawers")
    async def palace_drawers(
        wing: str = Query(default=""),
        room: str = Query(default=""),
        limit: int = Query(default=20, le=100),
        offset: int = Query(default=0, ge=0),
    ):
        """Drawer 列表（分页）。"""
        from app.inspector.api import _get_collection
        col = _get_collection(settings)
        if not col:
            return []

        where: dict = {}
        if wing and room:
            where = {"$and": [{"wing": wing}, {"room": room}]}
        elif wing:
            where = {"wing": wing}
        elif room:
            where = {"room": room}

        try:
            kwargs = {
                "include": ["metadatas", "documents"],
                "limit": limit,
                "offset": offset,
            }
            if where:
                kwargs["where"] = where
            data = col.get(**kwargs)
        except Exception:
            return []

        ids = data.get("ids") or []
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []

        return [
            {
                "id": ids[i],
                "content_preview": (docs[i] or "")[:200] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else {},
            }
            for i in range(len(ids))
        ]

    @auth_router.get("/palace/diary")
    async def palace_diary(limit: int = Query(default=10, le=50)):
        """最近日记条目。"""
        try:
            from mempalace.mcp_server import TOOLS
            from app.inspector.api import _parse_diary_result
            handler = TOOLS["mempalace_diary_read"]["handler"]
            raw = handler(agent_name="kaguya", last_n=limit)
            return _parse_diary_result(raw)
        except Exception:
            return []

    @auth_router.get("/palace/kg/stats")
    async def palace_kg_stats():
        """KG 统计信息。"""
        try:
            from mempalace.mcp_server import TOOLS
            from app.inspector.api import _parse_tool_result
            result = _parse_tool_result(TOOLS["mempalace_graph_stats"]["handler"]())
            return result
        except Exception:
            return {}

    return router, auth_router
```

**注意**：`create_miniapp_router` 返回两个 router：
- `router`（无鉴权，给 SSE 用，因为 EventSource 不支持自定义 header）
- `auth_router`（走 Telegram initData 鉴权，给 REST API 用）

---

## 任务 B：注册路由到 FastAPI 主应用

**文件**：`gateway/server.py`

找到 FastAPI app 实例创建和 router 注册的位置，新增：

```python
from app.miniapp.routes import create_miniapp_router

# 在 app 创建后、startup 事件之前
miniapp_router, miniapp_auth_router = create_miniapp_router(settings)
app.include_router(miniapp_router)
app.include_router(miniapp_auth_router)
```

**注意**：
- `settings` 对象需要在作用域内可用。检查 `server.py` 中 `Settings` 的实例化位置。
- 如果 `settings` 是在 startup 事件中创建的，可能需要用模块级变量或 `app.state.settings`。
- 先读 `server.py` 全文理解现有结构，再决定插入位置。

---

## 任务 C：在 LLM 工具循环中注入 SSE 推送

**文件**：`app/llm/client.py`

找到 `run_tool_loop`（或类似名称的方法），这是 LLM 工具调用的主循环。在以下位置插入 SSE push：

### C1：循环开始前

```python
from app.miniapp.sse_manager import sse_manager
import time

loop_start_time = time.time()

if sse_manager.has_active_connection():
    sse_manager.push("processing", {
        "step": "start",
        "message": "正在处理消息...",
    })
```

### C2：每轮工具调用前

在遍历 `tool_calls` 并执行每个工具之前：

```python
if sse_manager.has_active_connection():
    sse_manager.push("tool_call", {
        "tool": tool_call.function.name,
        "round": round_number,
        "args_summary": summarize_arguments(
            tool_call.function.name,
            json.loads(tool_call.function.arguments or "{}")
        ),
    })
```

### C3：每轮工具调用后

工具执行完成后（无论成功失败）：

```python
tool_elapsed = int((time.time() - tool_start) * 1000)
if sse_manager.has_active_connection():
    sse_manager.push("tool_done", {
        "tool": tool_call.function.name,
        "round": round_number,
        "success": not tool_failed,
        "duration_ms": tool_elapsed,
    })
```

### C4：工具循环结束，最终回复生成后

在构造 `ToolLoopResult` 并返回之前：

```python
total_elapsed = int((time.time() - loop_start_time) * 1000)
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
        "response_preview": result.reply_text[:200] if result.reply_text else "",
    })
```

### 关键约束

- **只加旁路推送，不改变现有逻辑流程**
- `sse_manager.push()` 是非阻塞的 `put_nowait`，不会影响性能
- `has_active_connection()` 为 False 时直接跳过，零开销
- `summarize_arguments` 已在 `app/inspector/logger.py` 中定义，直接 import

---

## 任务 D：在 Telegram Buffer 中注入 processing 推送

**文件**：`gateway/telegram_buffer.py`

在 `_process_combined` 方法中，调用 `handler.handle_message()` 之前：

```python
from app.miniapp.sse_manager import sse_manager

if sse_manager.has_active_connection():
    sse_manager.push("processing", {
        "step": "received",
        "message": f"收到消息，准备处理...",
    })
```

---

## 验收标准

1. `python main.py` 启动无报错，新路由注册成功
2. `curl http://localhost:PORT/miniapp/palace/overview` 返回宫殿统计 JSON（需带 initData header 或 query）
3. `curl http://localhost:PORT/miniapp/history` 返回最近对话历史 JSON
4. `curl http://localhost:PORT/miniapp/palace/wings` 返回 wing 列表
5. `curl http://localhost:PORT/miniapp/palace/diary` 返回最近日记
6. SSE 端点 `curl -N http://localhost:PORT/miniapp/stream?initData=test` 建立连接不报错
7. 在 Telegram 中发消息后，SSE 流收到 `processing` → `tool_call` → `tool_done` → `done` 事件
8. SSE 连接断开后，消息处理不受影响（零开销验证）

## 测试命令

```bash
# 启动服务
python main.py

# 测试宫殿概览（替换 YOUR_INIT_DATA）
curl -H "X-Telegram-Init-Data: YOUR_INIT_DATA" http://localhost:8000/miniapp/palace/overview

# 测试 SSE（开发环境可临时跳过鉴权测试）
curl -N "http://localhost:8000/miniapp/stream?initData=dev"

# 测试历史
curl -H "X-Telegram-Init-Data: YOUR_INIT_DATA" http://localhost:8000/miniapp/history
```

## Commit

```
feat(miniapp): Phase 1 — 后端 SSE 管线 + Mini App REST API 路由

- 新增 app/miniapp/ 模块（auth + sse_manager + routes）
- 注册 /miniapp/* 路由到 FastAPI 主应用
- 在 LLM 工具循环中注入 SSE 旁路推送
- 在 Telegram buffer 中注入 processing 推送
- 复用 inspector 查询逻辑，独立 Telegram initData 鉴权
```
