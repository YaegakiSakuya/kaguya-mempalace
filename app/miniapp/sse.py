"""线程安全的单用户 SSE 通道管理器。

_run_tool_loop() 在工作线程中运行，push() 从工作线程调用。
push() 使用 call_soon_threadsafe 确保跨线程安全。
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
            item = {"event": event, "data": payload}
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self._queue.put_nowait, item)
            except RuntimeError:
                # 没有运行中的 event loop（已经在 event loop 线程里），直接 put
                self._queue.put_nowait(item)
        except asyncio.QueueFull:
            logger.warning("sse_queue_full event=%s", event)
        except Exception:
            pass

    async def disconnect(self, queue_ref: asyncio.Queue | None = None) -> None:
        if queue_ref is not None and queue_ref is not self._queue:
            return
        if self._queue is not None:
            try:
                self._queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            self._queue = None
            logger.info("sse_disconnected")


# 全局单例
sse_manager = SSEManager()
