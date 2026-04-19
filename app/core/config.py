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
    kaguya_media_url: str
    kaguya_media_service_key: str
    media_uploads_dir: Path
    siliconflow_api_key: str
    siliconflow_base_url: str
    vl_model: str


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
        kaguya_media_url=os.getenv("KAGUYA_MEDIA_URL", "").strip(),
        kaguya_media_service_key=os.getenv("KAGUYA_MEDIA_SERVICE_KEY", "").strip(),
        media_uploads_dir=Path(os.getenv("MEDIA_UPLOADS_DIR", str(base_dir / "runtime" / "uploads"))).resolve(),
        siliconflow_api_key=os.getenv("SILICONFLOW_API_KEY", "").strip(),
        siliconflow_base_url=os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1").strip(),
        vl_model=os.getenv("VL_MODEL", "Qwen/Qwen3-VL-235B-A22B-Instruct").strip(),
    )

    required = {
        "OPENROUTER_API_KEY": settings.openrouter_api_key,
        "OPENROUTER_MODEL": settings.openrouter_model,
        "TELEGRAM_BOT_TOKEN": settings.telegram_bot_token,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    for path in [settings.chats_dir, settings.logs_dir, settings.state_dir, settings.palace_path, settings.media_uploads_dir]:
        path.mkdir(parents=True, exist_ok=True)

    settings.wakeup_file.parent.mkdir(parents=True, exist_ok=True)
    if not settings.wakeup_file.exists():
        settings.wakeup_file.write_text("", encoding="utf-8")

    return settings
