from __future__ import annotations

import inspect
import json
import logging
from typing import Any

from mempalace.mcp_server import TOOLS as MEMPALACE_TOOLS

logger = logging.getLogger(__name__)


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


def _filter_handler_kwargs(
    tool_name: str,
    handler: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not payload:
        return payload

    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):
        # If we cannot introspect, preserve existing behavior.
        return payload

    params = signature.parameters.values()
    accepts_var_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params)
    if accepts_var_kwargs:
        return payload

    accepted = {
        param.name
        for param in params
        if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    filtered_payload = {key: value for key, value in payload.items() if key in accepted}
    dropped_keys = sorted(set(payload) - set(filtered_payload))
    if dropped_keys:
        logger.info("dropped unsupported tool kwargs tool=%s keys=%s", tool_name, dropped_keys)
    return filtered_payload


def execute_tool(tool_name: str, arguments: str | None) -> str:
    if tool_name not in MEMPALACE_TOOLS:
        raise ValueError(f"Unknown MemPalace tool: {tool_name}")

    handler = MEMPALACE_TOOLS[tool_name]["handler"]
    payload = _parse_arguments(arguments)
    payload = _filter_handler_kwargs(tool_name=tool_name, handler=handler, payload=payload)

    result = handler(**payload)

    if isinstance(result, str):
        return result

    return json.dumps(result, ensure_ascii=False, indent=2)
