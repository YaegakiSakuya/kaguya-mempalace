from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from app.core.config import Settings


def _resolve_mempalace_executable() -> str:
    venv_bin = Path(sys.executable).parent / "mempalace"
    if venv_bin.exists():
        return str(venv_bin)

    found = shutil.which("mempalace")
    if found:
        return found

    raise FileNotFoundError("Could not find 'mempalace' executable")


def _run_mempalace(settings: Settings, *args: str, timeout: int = 30) -> str:
    mempalace_bin = _resolve_mempalace_executable()

    cmd = [
        mempalace_bin,
        "--palace",
        str(settings.palace_path),
        *args,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=timeout,
    )
    return result.stdout.strip()


def refresh_wakeup(settings: Settings) -> str:
    settings.wakeup_file.parent.mkdir(parents=True, exist_ok=True)
    if not settings.wakeup_file.exists():
        settings.wakeup_file.write_text("", encoding="utf-8")
    return settings.wakeup_file.read_text(encoding="utf-8").strip()


def read_wakeup(settings: Settings) -> str:
    return refresh_wakeup(settings)


def palace_status(settings: Settings) -> str:
    return _run_mempalace(settings, "status", timeout=20)


def mine_conversations(settings: Settings) -> str:
    return _run_mempalace(
        settings,
        "mine",
        str(settings.chats_dir),
        "--mode",
        "convos",
        "--extract",
        "general",
        "--agent",
        "kaguya",
        timeout=120,
    )


def load_recent_diary(n: int = 6) -> str:
    """Load the last N diary entries from mempalace for injection into the
    system prompt as the L2 (impression) memory layer.

    Uses mempalace's own diary_read tool handler. Failures are swallowed
    and return an empty string — diary loading must NEVER block the main
    reply pipeline.

    Note: the exact kwarg name for the diary_read handler depends on the
    installed mempalace version. Inspect the input_schema at runtime and
    pass the parameter named in it (commonly `last_n` or `n`). If the
    handler signature is unknown, try the most likely name; on TypeError
    fall through to the exception path and return empty.
    """
    import json
    import logging

    log = logging.getLogger(__name__)

    try:
        from mempalace.mcp_server import TOOLS
        spec = TOOLS.get("mempalace_diary_read")
        if not spec:
            log.warning("mempalace_diary_read not in TOOLS — returning empty horizon")
            return ""

        handler = spec["handler"]
        schema = spec.get("input_schema", {})
        props = schema.get("properties", {}) or {}

        # Detect the correct kwarg for entry count. Try common names.
        count_kwarg = None
        for candidate in ("last_n", "n", "count", "limit"):
            if candidate in props:
                count_kwarg = candidate
                break

        # diary_read is agent-scoped in this codebase — always pass
        # agent_name="kaguya" to match the convention used elsewhere
        # (see app/inspector/api.py). Omitting it risks TypeError or
        # loading the wrong agent's diary.
        call_kwargs: dict = {"agent_name": "kaguya"}
        if count_kwarg:
            call_kwargs[count_kwarg] = n
        result = handler(**call_kwargs)

        if isinstance(result, str):
            return result.strip()
        return json.dumps(result, ensure_ascii=False, indent=2).strip()

    except Exception:
        log.exception("load_recent_diary failed — returning empty horizon")
        return ""