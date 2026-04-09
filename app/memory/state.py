from __future__ import annotations

import json
from pathlib import Path


STATE_FILENAME = "message_counts.json"


def _state_file(state_dir: Path) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / STATE_FILENAME


def _read_state(state_dir: Path) -> dict[str, int]:
    path = _state_file(state_dir)
    if not path.exists():
        return {}

    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}

    data = json.loads(raw)
    cleaned: dict[str, int] = {}
    for key, value in data.items():
        try:
            cleaned[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return cleaned


def _write_state(state_dir: Path, data: dict[str, int]) -> None:
    path = _state_file(state_dir)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def get_message_count(state_dir: Path, chat_id: str) -> int:
    state = _read_state(state_dir)
    return int(state.get(str(chat_id), 0))


def increment_message_count(state_dir: Path, chat_id: str) -> int:
    state = _read_state(state_dir)
    key = str(chat_id)
    state[key] = int(state.get(key, 0)) + 1
    _write_state(state_dir, state)
    return state[key]


def reset_message_count(state_dir: Path, chat_id: str) -> None:
    state = _read_state(state_dir)
    key = str(chat_id)
    if key in state:
        state[key] = 0
    else:
        state[key] = 0
    _write_state(state_dir, state)
