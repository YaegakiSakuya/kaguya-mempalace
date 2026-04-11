"""SSE 连接管理器（单用户单连接）。"""
from __future__ import annotations

import asyncio
import json
from uuid import uuid4
from typing import Any, Dict, Optional


class SSEManager:
    """管理当前唯一 SSE 连接。"""

    def __init__(self) -> None:
        self._queue: Optional[asyncio.Queue] = None
        self._connection_id: Optional[str] = None

    async def connect(self) -> tuple[str, asyncio.Queue]:
        """建立新连接并替换旧连接。"""
        if self._queue is not None:
            try:
                self._queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

        self._connection_id = uuid4().hex
        self._queue = asyncio.Queue(maxsize=1000)
        return self._connection_id, self._queue

    async def disconnect(self, connection_id: str) -> None:
        """仅断开指定连接（避免旧连接误断开新连接）。"""
        if self._queue is not None and self._connection_id == connection_id:
            try:
                self._queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            self._queue = None
            self._connection_id = None

    def has_active_connection(self) -> bool:
        return self._queue is not None and self._connection_id is not None

    def push(self, event_type: str, payload: Dict[str, Any]) -> None:
        """非阻塞推送 SSE 事件，无连接时直接跳过。"""
        if self._queue is None or self._connection_id is None:
            return

        item = {
            "event": event_type,
            "data": json.dumps(payload, ensure_ascii=False),
        }
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            # 队列满时丢弃，不能阻塞主链路
            pass


sse_manager = SSEManager()
