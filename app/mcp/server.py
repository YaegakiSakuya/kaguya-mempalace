"""MemPalace MCP Server — Streamable HTTP transport for claude.ai connector.

Exposes all mempalace tools via the MCP protocol so that claude.ai can
read/write the same memory palace shared with the Telegram bot.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment setup — must happen before any mempalace import
# ---------------------------------------------------------------------------

_project_root = Path(__file__).resolve().parent.parent.parent
_dotenv_path = _project_root / ".env"
load_dotenv(_dotenv_path)

_base_dir = Path(
    os.getenv("BASE_DIR", "/home/ubuntu/apps/kaguya-gateway")
).resolve()
_palace_path = Path(
    os.getenv("PALACE_PATH", str(_base_dir / "runtime" / "palace"))
).resolve()

os.environ["MEMPALACE_PALACE_PATH"] = str(_palace_path)

_logs_dir = _base_dir / "runtime" / "logs"
_wing_reject_log = _logs_dir / "wing_prefix_rejections.jsonl"

logger.info("Palace path: %s", _palace_path)

# ---------------------------------------------------------------------------
# Imports that depend on the environment being configured
# ---------------------------------------------------------------------------

from mempalace.mcp_server import TOOLS  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402
from mcp.server.fastmcp.tools import Tool  # noqa: E402
from mcp.server.fastmcp.utilities.func_metadata import (  # noqa: E402
    ArgModelBase,
    FuncMetadata,
)
from pydantic import create_model  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers for dynamic tool registration
# ---------------------------------------------------------------------------

_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _build_arg_model(tool_name: str, schema: dict[str, Any]) -> type[ArgModelBase]:
    """Build a Pydantic model from a JSON Schema so FastMCP can validate args."""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: dict[str, Any] = {}

    for prop_name, prop_spec in properties.items():
        py_type = _JSON_TYPE_MAP.get(prop_spec.get("type", "string"), Any)
        if prop_name in required and "default" not in prop_spec:
            fields[prop_name] = (py_type, ...)
        else:
            default = prop_spec.get("default", None)
            fields[prop_name] = (Optional[py_type], default)

    return create_model(
        f"{tool_name}Arguments", __base__=ArgModelBase, **fields
    )


def _log_wing_rejection(tool_name: str, wing: str, source: str) -> None:
    """Append a JSONL record when a bare-wing write is rejected."""
    try:
        _logs_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tool": tool_name,
            "wing": wing,
            "source": source,
        }
        with _wing_reject_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # pragma: no cover — logging must never break the call
        logger.exception("Failed to log wing prefix rejection")


def _make_wrapper(tool_name: str, handler: Any, required_fields: set[str]) -> Any:
    """Wrap a mempalace handler to strip None optional args and normalise output."""

    def wrapper(**kwargs: Any) -> str:
        # Wing prefix enforcement — only applies to mempalace_add_drawer.
        # Reject bare wings (without 'wing_' prefix) before touching the
        # underlying ChromaDB handler, to stop duplicate naked wings from
        # being created.
        if tool_name == "mempalace_add_drawer":
            wing = kwargs.get("wing", "")
            if wing and not str(wing).startswith("wing_"):
                _log_wing_rejection(tool_name, str(wing), "mcp")
                return (
                    f"ERROR: wing 参数必须以 'wing_' 前缀开头。"
                    f"你尝试写入 wing='{wing}'，这会在宫殿里创建一个裸 wing，"
                    f"破坏命名规范。请改用 wing='wing_{wing}' 重试。"
                )

        # Remove None values for optional params so handlers that use
        # **kwargs don't receive unexpected None arguments.
        cleaned = {
            k: v
            for k, v in kwargs.items()
            if v is not None or k in required_fields
        }
        result = handler(**cleaned)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)

    return wrapper


# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------

MCP_PORT = int(os.getenv("MCP_PORT", "8766"))

from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402

# DNS rebinding protection is disabled because this MCP server is accessed
# via nginx reverse proxy with a production Host header (not localhost).
# Access control is enforced at the nginx layer (IP allowlist + HTTPS).
mcp = FastMCP(
    "MemPalace",
    stateless_http=True,
    json_response=True,
    host="127.0.0.1",
    port=MCP_PORT,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)

# ---------------------------------------------------------------------------
# Register every tool from the mempalace package
# ---------------------------------------------------------------------------

_registered = 0

for _name, _spec in TOOLS.items():
    _handler = _spec["handler"]
    _description = _spec["description"]
    _input_schema = _spec.get("input_schema", {"type": "object", "properties": {}})
    _required = set(_input_schema.get("required", []))

    _wrapper = _make_wrapper(_name, _handler, _required)
    _wrapper.__name__ = _name
    _wrapper.__doc__ = _description

    _arg_model = _build_arg_model(_name, _input_schema)
    _fn_meta = FuncMetadata(arg_model=_arg_model)

    _tool = Tool(
        fn=_wrapper,
        name=_name,
        description=_description,
        parameters=_input_schema,
        fn_metadata=_fn_meta,
        is_async=False,
    )

    mcp._tool_manager._tools[_name] = _tool
    _registered += 1

logger.info("Registered %d mempalace tools", _registered)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )
    logger.info(
        "Starting MemPalace MCP Server on 127.0.0.1:%d (streamable-http)",
        MCP_PORT,
    )
    logger.info("Endpoint: http://127.0.0.1:%d/mcp", MCP_PORT)
    logger.info("Tools: %d registered", _registered)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
