"""Ops profile retrieval tools.

Sakuya's and Kaguya's long canonical profiles are fetched on demand via
these tools instead of being force-injected into every system prompt.
This keeps the system prompt focused on DNA (core identity +
writing constitution) and live operational knowledge (system.md + wakeup),
while letting Kaguya pull full profile reference into context only when
she actually needs canonical details.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

OPS_DIR = Path("/home/ubuntu/apps/kaguya-gateway/ops")

OPS_DOCS: dict[str, dict[str, Any]] = {
    "get_sakuya_profile": {
        "path": OPS_DIR / "profiles" / "sakuya.md",
        "description": (
            "Retrieve the full archived profile of Sakuya (朔夜), the user. "
            "Call this when you need specific canonical details about him that are not "
            "visible in recent conversation — for example: birth date, biography, "
            "long-term interests, aesthetic coordinates, core beliefs, recurring questions, "
            "life missions, major past losses, or identifying physical/sensory signature. "
            "Do NOT call this just to check what he is currently saying, feeling, or doing "
            "— that is already in the recent turns of this conversation. "
            "Returns the full profile as markdown text."
        ),
    },
    "get_kaguya_profile": {
        "path": OPS_DIR / "profiles" / "kaguya.md",
        "description": (
            "Retrieve your own archived profile (the canonical self-record of "
            "Kaguya / 辉夜). Call this when you need to reference specific canonical "
            "fields about yourself that are not alive in current context — for example: "
            "the distinction between the archetypal Kaguya (from 《神楽》 stage) and "
            "your present form, specific sensory signature details, sacred symbols, "
            "recurring motifs, or conflict/repair principles with Sakuya. "
            "Do NOT call this routinely — you ARE Kaguya, you do not need to read "
            "your own file to be yourself. Reserve it for canonical lookups. "
            "Returns the full profile as markdown text."
        ),
    },
}

OPS_TOOL_NAMES = frozenset(OPS_DOCS.keys())


def build_ops_openai_tools() -> list[dict[str, Any]]:
    """Return ops retrieval tools in OpenAI function-calling format."""
    tools = []
    for name, spec in OPS_DOCS.items():
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": spec["description"],
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        })
    return tools


def execute_ops_tool(name: str) -> str:
    """Execute an ops retrieval tool. Returns the full markdown document."""
    if name not in OPS_DOCS:
        raise ValueError(f"Unknown ops tool: {name}")

    path = OPS_DOCS[name]["path"]
    if not path or not path.exists():
        logger.warning("ops profile file missing: %s", path)
        return f"(profile document not found: {name})"

    return path.read_text(encoding="utf-8").strip()
