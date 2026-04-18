#!/usr/bin/env python3
"""Smoke-test for the wing_ prefix hard-reject guard on mempalace_add_drawer.

Exercises the Telegram-side dispatch path (app.memory.tools.execute_tool),
which is the in-process wrapper used by the LLM tool loop. The MCP-side
guard lives in app.mcp.server._make_wrapper and is best exercised via
scripts/test_mcp.py with a live server.

Usage
-----
    python scripts/test_wing_prefix.py

The script does NOT talk to the network. It verifies:
  1. A bare wing (e.g. 'daily') is rejected with the Chinese error string
     and the underlying mempalace handler is NOT invoked.
  2. A prefixed wing (e.g. 'wing_daily') passes the guard — we stop short
     of the real write by stubbing the handler, so no ChromaDB mutation
     happens.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.memory import tools as memtools  # noqa: E402
from mempalace.mcp_server import TOOLS as MEMPALACE_TOOLS  # noqa: E402


def main() -> int:
    spec = MEMPALACE_TOOLS["mempalace_add_drawer"]
    original_handler = spec["handler"]

    calls: list[dict] = []

    def stub_handler(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "stub": True, "received": kwargs}

    spec["handler"] = stub_handler

    failures: list[str] = []

    try:
        # ── 1. Bare wing should be rejected ───────────────────────────
        print("--- case 1: wing='daily' (bare, should reject) ---")
        result = memtools.execute_tool(
            "mempalace_add_drawer",
            json.dumps(
                {
                    "wing": "daily",
                    "room": "whatever",
                    "title": "t",
                    "content": "c",
                }
            ),
        )
        print(f"returned: {result}")
        if not result.startswith("ERROR: wing 参数必须以 'wing_' 前缀开头"):
            failures.append("case 1: error prefix mismatch")
        if "wing='daily'" not in result:
            failures.append("case 1: original wing not echoed")
        if "wing='wing_daily'" not in result:
            failures.append("case 1: suggested fix not echoed")
        if calls:
            failures.append(
                f"case 1: handler was invoked despite rejection: {calls}"
            )

        # ── 2. Prefixed wing should pass the guard ────────────────────
        print("\n--- case 2: wing='wing_daily' (prefixed, should pass) ---")
        result = memtools.execute_tool(
            "mempalace_add_drawer",
            json.dumps(
                {
                    "wing": "wing_daily",
                    "room": "whatever",
                    "title": "t",
                    "content": "c",
                }
            ),
        )
        print(f"returned: {result}")
        if "ERROR" in result and "wing_ 前缀" in result:
            failures.append("case 2: prefixed wing was wrongly rejected")
        if not calls:
            failures.append("case 2: handler was not invoked")
        elif calls[-1].get("wing") != "wing_daily":
            failures.append(
                f"case 2: handler got wrong wing: {calls[-1]}"
            )

        # ── 3. Other tools are untouched ──────────────────────────────
        print("\n--- case 3: other tools not affected ---")
        # mempalace_search is a read tool — we only need to confirm the
        # guard isn't triggered. Stub its handler too.
        search_spec = MEMPALACE_TOOLS["mempalace_search"]
        search_orig = search_spec["handler"]
        search_calls: list[dict] = []

        def search_stub(**kwargs):
            search_calls.append(kwargs)
            return {"ok": True, "stub": True}

        search_spec["handler"] = search_stub
        try:
            memtools.execute_tool(
                "mempalace_search", json.dumps({"query": "x", "top_k": 1})
            )
            if not search_calls:
                failures.append("case 3: search handler was not invoked")
        finally:
            search_spec["handler"] = search_orig

    finally:
        spec["handler"] = original_handler

    print("\n=========================================")
    if failures:
        print("FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All wing-prefix guard cases passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
