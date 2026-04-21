"""Ops retrieval tools — retired as of 2026-04-21 system prompt refactor.

The profile-retrieval tools (get_syzygy_profile / get_kaguya_profile) were
removed because both profiles are now inlined into ops/prompts/system.md
and therefore always present in the reply-path system prompt. These stubs
remain only for import compatibility with app/llm/client.py; every call
short-circuits to an empty-result path. When client.py is later refactored
to drop these imports, this whole file can be deleted.
"""
from __future__ import annotations

from typing import Any

OPS_DOCS: dict[str, dict[str, Any]] = {}
OPS_TOOL_NAMES = frozenset(OPS_DOCS.keys())


def build_ops_openai_tools() -> list[dict[str, Any]]:
    """Return ops retrieval tools in OpenAI function-calling format. Always empty after retirement."""
    return []


def execute_ops_tool(name: str) -> str:
    """Stub — always raises since OPS_DOCS is empty. Present only for import compatibility."""
    raise ValueError(f"Unknown ops tool: {name}")
