from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from app.core.config import Settings, load_settings
from app.inspector.logger import append_jsonl, _now_iso
from app.llm.client import ToolLoopResult, generate_reply, run_memory_checkpoint
from app.memory.palace import mine_conversations, read_wakeup, refresh_wakeup
from app.memory.state import increment_message_count, reset_message_count
from app.memory.transcript import append_turn, load_recent_turns


logger = logging.getLogger(__name__)


def _write_turn_summary(logs_dir: Path, loop_result: ToolLoopResult, turn_type: str, chat_id: str) -> None:
    """Write a turn summary JSONL record after a reply or checkpoint completes."""
    ts = _now_iso()
    turn_id = f"turn_{uuid.uuid4().hex[:12]}"
    thinking_text = loop_result.thinking_preview or ""
    append_jsonl(logs_dir / "turn_summaries.jsonl", {
        "ts": ts,
        "turn_type": turn_type,
        "chat_id": chat_id,
        "turn_id": turn_id,
        "total_prompt_tokens": loop_result.total_prompt_tokens,
        "total_completion_tokens": loop_result.total_completion_tokens,
        "total_rounds": loop_result.total_rounds,
        "tools_called": loop_result.tools_called,
        "tools_succeeded": loop_result.tools_succeeded,
        "tools_failed": loop_result.tools_failed,
        "palace_writes": loop_result.palace_writes,
        "response_preview": loop_result.reply_text,
        "thinking_text": thinking_text,
        "thinking_preview": thinking_text,
    })


def configure_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler(logs_dir / "gateway.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def is_allowed_chat(settings: Settings, chat_id: str) -> bool:
    allowed = settings.telegram_allowed_chat_ids
    if not allowed:
        return True
    return str(chat_id) in allowed


def has_any_transcripts(settings: Settings) -> bool:
    return any(settings.chats_dir.glob("*.md"))


def checkpoint_turn_limit(settings: Settings) -> int:
    return max(settings.recent_turns, settings.autosave_user_message_interval)


async def run_autosave(application: Application, settings: Settings, chat_id: str) -> None:
    lock: asyncio.Lock = application.bot_data["autosave_lock"]

    async with lock:
        if not has_any_transcripts(settings):
            return

        try:
            logger.info("autosave started for chat_id=%s", chat_id)

            recent_turns = await asyncio.to_thread(
                load_recent_turns,
                settings.chats_dir,
                chat_id,
                checkpoint_turn_limit(settings),
            )
            wakeup_text = await asyncio.to_thread(read_wakeup, settings)

            if recent_turns:
                checkpoint_result = await asyncio.to_thread(
                    run_memory_checkpoint,
                    settings,
                    wakeup_text,
                    recent_turns,
                    8,
                    chat_id,
                )
                logger.info(
                    "autosave checkpoint finished for chat_id=%s result=%s",
                    chat_id,
                    checkpoint_result.reply_text,
                )
                _write_turn_summary(settings.logs_dir, checkpoint_result, "checkpoint", chat_id)

            await asyncio.to_thread(mine_conversations, settings)
            await asyncio.to_thread(refresh_wakeup, settings)
            await asyncio.to_thread(reset_message_count, settings.state_dir, chat_id)

            logger.info("autosave finished for chat_id=%s", chat_id)
        except Exception:
            logger.exception("autosave failed for chat_id=%s", chat_id)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]

    if not update.effective_chat or not update.message:
        return

    chat_id = str(update.effective_chat.id)
    if not is_allowed_chat(settings, chat_id):
        await update.message.reply_text("This chat is not allowed.")
        return

    await update.message.reply_text("Gateway is online.")


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    bootstrapped_chats: set[str] = context.application.bot_data["bootstrapped_chats"]

    if not update.effective_chat or not update.message or not update.message.text:
        return

    chat_id = str(update.effective_chat.id)
    if not is_allowed_chat(settings, chat_id):
        await update.message.reply_text("This chat is not allowed.")
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    force_status_bootstrap = chat_id not in bootstrapped_chats

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

        recent_turns = await asyncio.to_thread(
            load_recent_turns,
            settings.chats_dir,
            chat_id,
            settings.recent_turns,
        )
        wakeup_text = await asyncio.to_thread(read_wakeup, settings)

        loop_result = await asyncio.to_thread(
            generate_reply,
            settings,
            wakeup_text,
            "",
            recent_turns,
            user_text,
            6,
            force_status_bootstrap,
            chat_id,
        )
        assistant_text = loop_result.reply_text

        segments = loop_result.reply_segments or [assistant_text]
        for idx, segment in enumerate(segments):
            if not segment or not segment.strip():
                continue
            if idx > 0:
                await context.bot.send_chat_action(
                    chat_id=update.effective_chat.id,
                    action=ChatAction.TYPING,
                )
                await asyncio.sleep(0.4)
            await update.message.reply_text(segment)

        await asyncio.to_thread(
            append_turn,
            settings.chats_dir,
            chat_id,
            user_text,
            assistant_text,
        )

        _write_turn_summary(settings.logs_dir, loop_result, "reply", chat_id)

        bootstrapped_chats.add(chat_id)

        count = await asyncio.to_thread(
            increment_message_count,
            settings.state_dir,
            chat_id,
        )

        logger.info(
            "handled message chat_id=%s count=%s bootstrap=%s",
            chat_id,
            count,
            force_status_bootstrap,
        )

        if count >= settings.autosave_user_message_interval:
            context.application.create_task(run_autosave(context.application, settings, chat_id))

    except Exception:
        logger.exception("message handling failed for chat_id=%s", chat_id)
        await update.message.reply_text("Something went wrong while handling your message.")


async def post_init(application: Application) -> None:
    settings: Settings = application.bot_data["settings"]
    application.bot_data["autosave_lock"] = asyncio.Lock()
    application.bot_data["bootstrapped_chats"] = set()

    try:
        await asyncio.to_thread(refresh_wakeup, settings)
        logger.info("startup wake-up refreshed")
    except Exception:
        logger.exception("startup wake-up refresh failed")


async def post_shutdown(application: Application) -> None:
    settings: Settings = application.bot_data["settings"]

    try:
        if has_any_transcripts(settings):
            await asyncio.to_thread(mine_conversations, settings)
            await asyncio.to_thread(refresh_wakeup, settings)
        logger.info("shutdown autosave completed")
    except Exception:
        logger.exception("shutdown autosave failed")


def build_application(settings: Settings) -> Application:
    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.bot_data["settings"] = settings

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

    return app


def main() -> None:
    settings = load_settings()
    configure_logging(settings.logs_dir)

    # Start Inspector API in background thread (only if token is configured)
    if settings.inspector_token:
        try:
            import uvicorn
            from app.inspector.api import create_inspector_app

            inspector_app = create_inspector_app(settings)
            inspector_thread = threading.Thread(
                target=uvicorn.run,
                kwargs={
                    "app": inspector_app,
                    "host": "0.0.0.0",
                    "port": settings.inspector_port,
                    "log_level": "warning",
                },
                daemon=True,
            )
            inspector_thread.start()
            logger.info("inspector API started on port %s", settings.inspector_port)
        except Exception:
            logger.exception("failed to start inspector API")
    else:
        logger.info("inspector API disabled (INSPECTOR_TOKEN not set)")

    application = build_application(settings)
    application.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
