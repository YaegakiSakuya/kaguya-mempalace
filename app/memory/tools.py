from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mempalace.mcp_server import TOOLS as MEMPALACE_TOOLS

logger = logging.getLogger(__name__)

_BASE_DIR = Path(
    os.getenv("BASE_DIR", "/home/ubuntu/apps/kaguya-mempalace")
).resolve()
_WING_REJECT_LOG = _BASE_DIR / "runtime" / "logs" / "wing_prefix_rejections.jsonl"


def _log_wing_rejection(tool_name: str, wing: str, source: str) -> None:
    """Append a JSONL record when a bare-wing write is rejected."""
    try:
        _WING_REJECT_LOG.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tool": tool_name,
            "wing": wing,
            "source": source,
        }
        with _WING_REJECT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("Failed to log wing prefix rejection")


def build_openai_tools() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []

    for name, spec in MEMPALACE_TOOLS.items():
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": spec["description"],
                    "parameters": spec["input_schema"],
                },
            }
        )

    return tools


OPENAI_TOOLS = build_openai_tools()


def _parse_arguments(arguments: str | None) -> dict[str, Any]:
    if not arguments:
        return {}
    arguments = arguments.strip()
    if not arguments:
        return {}
    return json.loads(arguments)


def execute_tool(tool_name: str, arguments: str | None) -> str:
    if tool_name not in MEMPALACE_TOOLS:
        raise ValueError(f"Unknown MemPalace tool: {tool_name}")

    handler = MEMPALACE_TOOLS[tool_name]["handler"]
    payload = _parse_arguments(arguments)

    # Wing prefix enforcement — only applies to mempalace_add_drawer.
    # Reject bare wings (without 'wing_' prefix) before touching the handler,
    # to stop duplicate naked wings from being created. Empty/missing wing
    # is also rejected here.
    if tool_name == "mempalace_add_drawer":
        wing = str(payload.get("wing", "") or "")
        if not wing.startswith("wing_"):
            _log_wing_rejection(tool_name, wing, "telegram")
            return (
                f"ERROR: wing 参数必须以 'wing_' 前缀开头。"
                f"你尝试写入 wing='{wing}'，这会在宫殿里创建一个裸 wing，"
                f"破坏命名规范。请改用 wing='wing_{wing}' 重试。"
            )

    result = handler(**payload)

    if isinstance(result, str):
        return result

    return json.dumps(result, ensure_ascii=False, indent=2)
