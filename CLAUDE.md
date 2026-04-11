# CLAUDE.md — kaguya-gateway

## Project Overview

Telegram bot gateway for "Kaguya" (辉夜), a personalized AI companion. The gateway receives Telegram messages, calls an LLM via OpenRouter (OpenAI-compatible API), and uses MemPalace (a pip package `mempalace`) for persistent memory via function calling. Runs on a single Ubuntu VPS as a systemd service.

## Tech Stack

- Python 3.12, no framework besides `python-telegram-bot` and `openai` SDK
- MemPalace (`mempalace` pip package, v3.x) for memory: ChromaDB for drawers/search, SQLite for KG
- OpenRouter as LLM provider (OpenAI-compatible endpoint)
- Config via `.env` + `dotenv`
- Runs as `systemd/kaguya-gateway.service`

## Repository Structure

```
app/
  core/config.py        # Settings dataclass, loads from .env
  llm/client.py         # LLM calls, tool loop, system prompt construction
  memory/
    tools.py            # Wraps mempalace.mcp_server.TOOLS for OpenAI function calling
    palace.py           # CLI wrappers for mempalace binary (status, mine)
    transcript.py       # Markdown-based chat transcript read/write
    state.py            # Message counter (JSON file)
  main.py               # Telegram bot entry point, handlers, autosave logic
ops/
  prompts/              # System prompt files (core_identity.md, writing_constitution.md, system.md)
  profiles/             # Character profiles (sakuya.md, kaguya.md)
preseed_palace.py       # Seeds initial wings/rooms into a fresh palace
systemd/                # Service unit file
```

## Key Architecture Decisions

- **Single process**: Telegram polling + all logic in one asyncio event loop. No separate workers.
- **Tool calling**: `_run_tool_loop()` in `client.py` sends messages to OpenRouter with MemPalace tools, executes tool calls locally via `execute_tool()`, loops until LLM returns text.
- **Transcripts**: Stored as markdown files in `runtime/chats/{chat_id}.md`. User messages are blockquoted (`>`), assistant messages are plain text.
- **Autosave**: After N user messages, triggers `run_memory_checkpoint()` (LLM-driven save to palace) then `mine_conversations()` (CLI mining).
- **Wake-up**: `runtime/wakeup.txt` is read at startup and injected into system prompt as continuity anchor.

## MemPalace Internals (the `mempalace` pip package)

This is critical context. The gateway wraps MemPalace; you need to understand its storage.

### Storage Layout (all under `PALACE_PATH`, default `runtime/palace/`)

- **Drawers**: ChromaDB PersistentClient, collection `mempalace_drawers`. Each drawer has metadata: `wing`, `room`, `hall`, `date`, `source_file`, `importance`, `filed_at`, `type`.
- **KG**: SQLite at `{PALACE_PATH}/knowledge_graph.sqlite3`. Tables: `entities` (id, name, type, properties), `triples` (subject, predicate, object, valid_from, valid_to, confidence, source_closet).
- **Diary**: Special drawers in ChromaDB with `wing=agent_{name}`, `room=diary`, `hall=hall_diary`, `type=diary_entry`.
- **Graph**: No separate storage. `palace_graph.py` computes graph on-the-fly from ChromaDB metadata (rooms spanning multiple wings = tunnels).

### Available Tool Handlers (from `mempalace.mcp_server.TOOLS`)

Read tools: `mempalace_status`, `mempalace_list_wings`, `mempalace_list_rooms`, `mempalace_get_taxonomy`, `mempalace_get_aaak_spec`, `mempalace_search`, `mempalace_check_duplicate`, `mempalace_kg_query`, `mempalace_kg_timeline`, `mempalace_kg_stats`, `mempalace_kg_invalidate`, `mempalace_traverse`, `mempalace_find_tunnels`, `mempalace_graph_stats`, `mempalace_diary_read`

Write tools: `mempalace_add_drawer`, `mempalace_delete_drawer`, `mempalace_kg_add`, `mempalace_diary_write`

All handlers are plain Python functions. Import via `from mempalace.mcp_server import TOOLS` — each entry has `handler`, `description`, `input_schema`.

### Key Python Classes

- `mempalace.knowledge_graph.KnowledgeGraph` — SQLite-backed temporal KG. Instantiate with `KnowledgeGraph(db_path=...)`.
- `mempalace.palace_graph.build_graph(col)` — returns `(nodes, edges)` from ChromaDB metadata.
- `mempalace.palace_graph.graph_stats(col)` — summary stats.
- `mempalace.layers.MemoryStack` — 4-layer memory (L0 identity, L1 essential, L2 on-demand, L3 search).
- `mempalace.config.MempalaceConfig` — config with `palace_path`, `collection_name`.

## Commands

```bash
# Run gateway
cd /home/ubuntu/apps/kaguya-gateway
.venv/bin/python -m app.main

# Preseed a fresh palace
rm -rf runtime/palace && mkdir -p runtime/palace
.venv/bin/python preseed_palace.py

# Service management
sudo systemctl restart kaguya-gateway
sudo journalctl -u kaguya-gateway -f

# Install dependencies
pip install -r requirements.txt
```

## Code Style

- Python 3.12 features OK (type hints, `|` union, etc.)
- `from __future__ import annotations` at top of every module
- Dataclasses for config, plain dicts for message passing
- Logging via stdlib `logging`, not print
- File I/O always with `encoding="utf-8"`
- Atomic file writes via tmp+rename pattern (see `state.py`)

## Important Gotchas

- `OPS_DIR` in `client.py` is hardcoded to `/home/ubuntu/apps/kaguya-gateway/ops`. When adding new files that reference ops, use this path.
- MemPalace tools are synchronous. The gateway wraps them in `asyncio.to_thread()` for async compat.
- The `autosave_lock` prevents concurrent checkpoint/mine operations.
- ChromaDB's `PersistentClient` is not thread-safe for concurrent writes. Dashboard/inspector reads are fine but should not write to palace.
- KG SQLite uses WAL mode, so concurrent reads during writes are safe.
