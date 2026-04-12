from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    system_name: str
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_model: str
    telegram_bot_token: str
    telegram_allowed_chat_ids: list[str]
    base_dir: Path
    palace_path: Path
    chats_dir: Path
    logs_dir: Path
    state_dir: Path
    wakeup_file: Path
    autosave_user_message_interval: int
    search_top_k: int
    recent_turns: int
    inspector_port: int
    inspector_token: str
    miniapp_session_secret: str
    miniapp_session_ttl_seconds: int
    miniapp_initdata_max_age_seconds: int
    miniapp_url: str


def load_settings() -> Settings:
    base_dir = Path(os.getenv("BASE_DIR", "/home/ubuntu/apps/kaguya-gateway")).resolve()

    settings = Settings(
        system_name=os.getenv("SYSTEM_NAME", "Kaguya Telegram Gateway"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip(),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "").strip(),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_allowed_chat_ids=_split_csv(os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")),
        base_dir=base_dir,
        palace_path=Path(os.getenv("PALACE_PATH", str(base_dir / "runtime" / "palace"))).resolve(),
        chats_dir=Path(os.getenv("CHATS_DIR", str(base_dir / "runtime" / "chats"))).resolve(),
        logs_dir=Path(os.getenv("LOGS_DIR", str(base_dir / "runtime" / "logs"))).resolve(),
        state_dir=Path(os.getenv("STATE_DIR", str(base_dir / "runtime" / "state"))).resolve(),
        wakeup_file=Path(os.getenv("WAKEUP_FILE", str(base_dir / "runtime" / "wakeup.txt"))).resolve(),
        autosave_user_message_interval=int(os.getenv("AUTOSAVE_USER_MESSAGE_INTERVAL", "15")),
        search_top_k=int(os.getenv("SEARCH_TOP_K", "8")),
        recent_turns=int(os.getenv("RECENT_TURNS", "8")),
        inspector_port=int(os.getenv("INSPECTOR_PORT", "8765")),
        inspector_token=os.getenv("INSPECTOR_TOKEN", "").strip(),
        miniapp_session_secret=os.getenv("MINIAPP_SESSION_SECRET", "").strip() or os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        miniapp_session_ttl_seconds=int(os.getenv("MINIAPP_SESSION_TTL_SECONDS", "900")),
        miniapp_initdata_max_age_seconds=int(os.getenv("MINIAPP_INITDATA_MAX_AGE_SECONDS", "300")),
        miniapp_url=os.getenv("MINIAPP_URL", "").strip(),
    )

    required = {
        "OPENROUTER_API_KEY": settings.openrouter_api_key,
        "OPENROUTER_MODEL": settings.openrouter_model,
        "TELEGRAM_BOT_TOKEN": settings.telegram_bot_token,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    for path in [settings.chats_dir, settings.logs_dir, settings.state_dir, settings.palace_path]:
        path.mkdir(parents=True, exist_ok=True)

    settings.wakeup_file.parent.mkdir(parents=True, exist_ok=True)
    if not settings.wakeup_file.exists():
        settings.wakeup_file.write_text("", encoding="utf-8")

    return settings
