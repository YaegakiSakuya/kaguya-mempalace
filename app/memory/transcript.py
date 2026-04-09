from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple


Turn = Tuple[str, str]


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return text


def _safe_chat_id(chat_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", str(chat_id)).strip("._") or "unknown"


def transcript_path(chats_dir: Path, chat_id: str) -> Path:
    chats_dir.mkdir(parents=True, exist_ok=True)
    return chats_dir / f"{_safe_chat_id(chat_id)}.md"


def _format_user_block(text: str) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        normalized = "[empty user message]"
    lines = normalized.split("\n")
    return "\n".join(f"> {line}" if line else ">" for line in lines)


def _format_assistant_block(text: str) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        normalized = "[empty assistant message]"
    return normalized


def append_turn(chats_dir: Path, chat_id: str, user_text: str, assistant_text: str) -> Path:
    path = transcript_path(chats_dir, chat_id)

    user_block = _format_user_block(user_text)
    assistant_block = _format_assistant_block(assistant_text)

    payload = f"{user_block}\n{assistant_block}\n\n"

    with path.open("a", encoding="utf-8") as f:
        f.write(payload)

    return path


def parse_transcript(content: str) -> List[Turn]:
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    turns: List[Turn] = []
    i = 0
    n = len(lines)

    while i < n:
        while i < n and not lines[i].startswith(">"):
            i += 1
        if i >= n:
            break

        user_lines: List[str] = []
        while i < n and lines[i].startswith(">"):
            line = lines[i]
            if line == ">":
                user_lines.append("")
            elif line.startswith("> "):
                user_lines.append(line[2:])
            else:
                user_lines.append(line[1:].lstrip())
            i += 1

        assistant_lines: List[str] = []
        while i < n and not lines[i].startswith(">"):
            assistant_lines.append(lines[i])
            i += 1

        user_text = "\n".join(user_lines).strip()
        assistant_text = "\n".join(assistant_lines).strip()

        if user_text or assistant_text:
            turns.append((user_text, assistant_text))

    return turns


def load_recent_turns(chats_dir: Path, chat_id: str, max_turns: int) -> List[Turn]:
    path = transcript_path(chats_dir, chat_id)
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8")
    turns = parse_transcript(content)
    if max_turns <= 0:
        return []
    return turns[-max_turns:]
