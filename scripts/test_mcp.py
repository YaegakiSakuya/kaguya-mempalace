#!/usr/bin/env python3
"""Smoke-test for the MemPalace MCP Server.

Usage
-----
1. Start the MCP server in one terminal:
       python -m app.mcp.server
2. Run this script in another terminal:
       python scripts/test_mcp.py

The script connects to the local MCP server, lists tools, and runs a
couple of read-only calls to verify everything works end-to-end.
"""
from __future__ import annotations

import asyncio
import sys

MCP_URL = "http://127.0.0.1:8766/mcp"


async def main() -> None:
    # Late imports so the script fails fast with a clear message if deps
    # are missing.
    try:
        from mcp.client.streamable_http import streamablehttp_client
        from mcp.client.session import ClientSession
    except ImportError:
        print("ERROR: 'mcp' package not installed. Run: pip install mcp")
        sys.exit(1)

    print(f"Connecting to {MCP_URL} ...")

    try:
        async with streamablehttp_client(MCP_URL) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                # ── 1. Initialize ─────────────────────────────────
                init = await session.initialize()
                print(f"Connected — server: {init.serverInfo.name}")

                # ── 2. List tools ─────────────────────────────────
                result = await session.list_tools()
                tools = result.tools
                print(f"\nTools registered: {len(tools)}")
                for t in sorted(tools, key=lambda t: t.name):
                    print(f"  - {t.name}")

                # ── 3. Call mempalace_kg_stats ─────────────────────
                print("\n--- mempalace_kg_stats ---")
                try:
                    resp = await session.call_tool("mempalace_kg_stats", {})
                    for block in resp.content:
                        print(block.text if hasattr(block, "text") else block)
                except Exception as exc:
                    print(f"  FAILED: {exc}")

                # ── 4. Call mempalace_search ───────────────────────
                print("\n--- mempalace_search(query='test', top_k=3) ---")
                try:
                    resp = await session.call_tool(
                        "mempalace_search",
                        {"query": "test", "top_k": 3},
                    )
                    for block in resp.content:
                        print(block.text if hasattr(block, "text") else block)
                except Exception as exc:
                    print(f"  FAILED: {exc}")

                print("\nAll checks done.")

    except Exception as exc:
        print(f"Connection error: {exc}")
        print("Is the MCP server running?  python -m app.mcp.server")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
