"""Structured JSONL logger for Inspector observability."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_jsonl(path: Path, record: dict) -> None:
    """Append a single JSON record to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, default=str)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_jsonl_tail(path: Path, last_n: int = 50) -> list[dict]:
    """Read the last N lines of a JSONL file.

    For large files (>10 MB) reads from the tail to avoid loading
    everything into memory.
    """
    if not path.exists():
        return []

    file_size = path.stat().st_size
    if file_size == 0:
        return []

    if file_size > 10 * 1024 * 1024:
        return _read_tail_large(path, last_n)

    lines = path.read_text(encoding="utf-8").strip().split("\n")
    lines = lines[-last_n:]
    results: list[dict] = []
    for line in lines:
        line = line.strip()
        if line:
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return results


def _read_tail_large(path: Path, last_n: int) -> list[dict]:
    """Read the last N JSON lines from a large file without loading it all."""
    chunk_size = 8192
    lines: list[str] = []

    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        remaining = f.tell()
        buffer = b""

        while remaining > 0 and len(lines) < last_n + 1:
            read_size = min(chunk_size, remaining)
            remaining -= read_size
            f.seek(remaining)
            buffer = f.read(read_size) + buffer
            lines = buffer.split(b"\n")

    text_lines = [l.decode("utf-8", errors="replace").strip() for l in lines]
    text_lines = [l for l in text_lines if l]
    text_lines = text_lines[-last_n:]

    results: list[dict] = []
    for line in text_lines:
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return results


def summarize_arguments(tool_name: str, args_dict: dict) -> dict:
    """Extract key identifying fields from tool arguments for logging.

    Avoids logging large content fields.
    """
    key_fields = {
        "mempalace_add_drawer": ["wing", "room", "hall", "type", "importance"],
        "mempalace_delete_drawer": ["drawer_id"],
        "mempalace_search": ["query", "wing", "top_k"],
        "mempalace_check_duplicate": ["content_summary", "wing", "room"],
        "mempalace_kg_add": ["subject", "predicate", "object"],
        "mempalace_kg_query": ["entity", "direction"],
        "mempalace_kg_timeline": ["entity"],
        "mempalace_kg_stats": [],
        "mempalace_kg_invalidate": ["subject", "predicate", "object"],
        "mempalace_traverse": ["start_wing", "start_room"],
        "mempalace_find_tunnels": ["wing_a", "wing_b"],
        "mempalace_diary_write": ["agent_name"],
        "mempalace_diary_read": ["agent_name", "last_n"],
        "mempalace_list_wings": [],
        "mempalace_list_rooms": ["wing"],
        "mempalace_status": [],
        "mempalace_get_taxonomy": [],
        "mempalace_get_aaak_spec": [],
        "mempalace_graph_stats": [],
    }

    fields = key_fields.get(tool_name)
    if fields is None:
        # Unknown tool — keep all keys except very long values
        return {k: v for k, v in args_dict.items() if not isinstance(v, str) or len(v) < 200}

    return {k: args_dict[k] for k in fields if k in args_dict}
