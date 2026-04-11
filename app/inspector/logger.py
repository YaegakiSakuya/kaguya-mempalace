from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def read_jsonl_tail(path: Path, limit: int = 50) -> list[dict]:
    if limit <= 0 or not path.exists():
        return []
    lines = _read_tail_large(path, limit)
    rows: list[dict] = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _read_tail_large(path: Path, limit: int) -> list[str]:
    """Read the last N full lines from a potentially large file.

    Guarantees that when the read begins from the middle of file, the first
    partial line fragment is discarded.
    """
    if limit <= 0:
        return []

    file_size = path.stat().st_size
    if file_size <= 0:
        return []

    block_size = 8192
    lines: list[str] = []
    buffer = b""
    position = file_size

    with path.open("rb") as handle:
        while position > 0 and len(lines) <= limit:
            read_size = min(block_size, position)
            position -= read_size
            handle.seek(position, os.SEEK_SET)
            chunk = handle.read(read_size)
            buffer = chunk + buffer
            parts = buffer.split(b"\n")

            if position > 0:
                # We started from middle of a line: drop partial prefix safely.
                buffer = parts[0]
                completed = parts[1:]
            else:
                buffer = b""
                completed = parts

            decoded = [p.decode("utf-8", errors="replace").strip() for p in completed if p.strip()]
            if decoded:
                lines = decoded + lines

    return lines[-limit:]
