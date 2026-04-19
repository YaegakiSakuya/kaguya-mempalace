"""Voice file storage utilities.

负责 voice 文件的本地落盘与路径构造。目录结构统一为:

    runtime/uploads/voice/{direction}/{chat_id}/{YYYY-MM-DD}/{uuid}.{ext}

direction: "outgoing" (辉夜发给朔夜的 TTS 合成) 或 "incoming"
(朔夜发给辉夜的、将来接 ASR 用的原语音)。
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path


logger = logging.getLogger(__name__)


def build_voice_relative_path(
    *,
    direction: str,
    chat_id: str,
    extension: str = "mp3",
) -> str:
    if direction not in ("outgoing", "incoming"):
        raise ValueError(f"invalid voice direction: {direction}")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    safe_chat = str(chat_id).strip() or "unknown"
    filename = f"{uuid.uuid4().hex}.{extension.lstrip('.')}"
    return f"voice/{direction}/{safe_chat}/{today}/{filename}"


def save_voice_to_uploads(
    uploads_root: Path,
    relative_path: str,
    data: bytes,
) -> Path:
    absolute = uploads_root / relative_path
    absolute.parent.mkdir(parents=True, exist_ok=True)
    absolute.write_bytes(data)
    return absolute
