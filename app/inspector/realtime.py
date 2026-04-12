from __future__ import annotations

import threading
from collections import deque
from copy import deepcopy
from typing import Any

from app.inspector.logger import _now_iso


class RealtimeEventBus:
    """In-memory realtime event/state manager for inspector SSE and history."""

    def __init__(self, max_events: int = 1000, max_history: int = 50) -> None:
        self._lock = threading.Lock()
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._history: deque[dict[str, Any]] = deque(maxlen=max_history)
        self._turn_state: dict[str, dict[str, Any]] = {}
        self._next_event_id = 1
        self._latest_turn_id = ""

    def emit(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            event = {
                "id": self._next_event_id,
                "ts": _now_iso(),
                "event": event_type,
                "data": payload,
            }
            self._next_event_id += 1
            self._events.append(event)
            self._apply_event(event_type, payload, event["ts"])
            return event

    def events_since(self, last_event_id: int, chat_id: str = "") -> list[dict[str, Any]]:
        with self._lock:
            items = [e for e in self._events if e["id"] > last_event_id]
            if chat_id:
                items = [e for e in items if str((e.get("data") or {}).get("chat_id") or "") == chat_id]
            return [deepcopy(e) for e in items]

    def current(self, chat_id: str = "") -> dict[str, Any]:
        with self._lock:
            if chat_id:
                for turn_id in reversed(list(self._turn_state.keys())):
                    state = self._turn_state.get(turn_id) or {}
                    if str(state.get("chat_id") or "") == chat_id:
                        return deepcopy(state)

                for item in reversed(self._history):
                    if str(item.get("chat_id") or "") == chat_id:
                        return deepcopy(item)
                return {}

            if not self._latest_turn_id:
                return {}
            state = self._turn_state.get(self._latest_turn_id) or {}
            return deepcopy(state)

    def history(self, limit: int = 20, chat_id: str = "") -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._history)
            if chat_id:
                items = [item for item in items if str(item.get("chat_id") or "") == chat_id]
            items = items[-limit:]
            return deepcopy(items[::-1])

    def _apply_event(self, event_type: str, payload: dict[str, Any], ts: str) -> None:
        turn_id = str(payload.get("turn_id") or "")
        if not turn_id:
            return

        state = self._turn_state.setdefault(turn_id, {
            "turn_id": turn_id,
            "chat_id": str(payload.get("chat_id") or ""),
            "created_at": ts,
            "status": "idle",
            "user_text": str(payload.get("user_text") or ""),
            "processing_messages": [],
            "thinking_text": "",
            "reply_text": "",
            "thinking_ms": 0,
            "replying_ms": 0,
            "tool_calls": [],
            "stats": {},
        })
        self._latest_turn_id = turn_id

        if payload.get("chat_id"):
            state["chat_id"] = str(payload["chat_id"])
        if payload.get("user_text"):
            state["user_text"] = str(payload["user_text"])

        if event_type == "processing":
            state["status"] = "processing"
            message = str(payload.get("message") or "")
            if message:
                state["processing_messages"].append(message)
                state["processing_messages"] = state["processing_messages"][-12:]

        elif event_type == "thinking":
            state["status"] = "thinking"
            state["thinking_text"] += str(payload.get("chunk") or "")
            state["thinking_ms"] = int(payload.get("elapsed_ms") or state["thinking_ms"])

        elif event_type == "replying":
            state["status"] = "replying"
            state["reply_text"] += str(payload.get("chunk") or "")
            state["replying_ms"] = int(payload.get("elapsed_ms") or state["replying_ms"])

        elif event_type == "tool_start":
            state["tool_calls"].append({
                "name": str(payload.get("tool_name") or "unknown"),
                "status": "running",
                "elapsed_ms": None,
                "success": None,
            })
            state["tool_calls"] = state["tool_calls"][-20:]

        elif event_type == "tool_end":
            target_name = str(payload.get("tool_name") or "unknown")
            for tool in reversed(state["tool_calls"]):
                if tool.get("name") == target_name and tool.get("status") == "running":
                    tool["status"] = "done"
                    tool["elapsed_ms"] = payload.get("elapsed_ms")
                    tool["success"] = bool(payload.get("success", False))
                    break

        elif event_type == "done":
            state["status"] = "done"
            state["stats"] = {
                "input_tokens": payload.get("input_tokens"),
                "output_tokens": payload.get("output_tokens"),
                "thinking_ms": payload.get("thinking_ms", state["thinking_ms"]),
                "replying_ms": payload.get("replying_ms", state["replying_ms"]),
                "total_rounds": payload.get("total_rounds"),
                "tools_called": payload.get("tools_called", []),
            }
            state["completed_at"] = ts
            self._history.append(deepcopy(state))


realtime_bus = RealtimeEventBus()
