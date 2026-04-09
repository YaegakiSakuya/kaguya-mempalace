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