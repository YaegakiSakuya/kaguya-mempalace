from __future__ import annotations

import json
from typing import Any

from mempalace.mcp_server import TOOLS as MEMPALACE_TOOLS


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

    result = handler(**payload)

    if isinstance(result, str):
        return result

    return json.dumps(result, ensure_ascii=False, indent=2)
