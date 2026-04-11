from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from openai import OpenAI

from app.core.config import Settings
from app.inspector.logger import append_jsonl, summarize_arguments, _now_iso
from app.inspector.realtime import realtime_bus
from app.memory.tools import OPENAI_TOOLS, execute_tool

Turn = Tuple[str, str]

logger = logging.getLogger(__name__)

# Tools that count as palace write calls
_PALACE_WRITE_TOOLS = {
    "mempalace_add_drawer": "drawer_write_calls",
    "mempalace_kg_add": "kg_write_calls",
    "mempalace_diary_write": "diary_write_calls",
}


@dataclass
class ToolLoopResult:
    reply_text: str
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_rounds: int = 0
    tools_called: list[str] = field(default_factory=list)
    tools_succeeded: int = 0
    tools_failed: int = 0
    palace_writes: dict[str, int] = field(default_factory=lambda: {
        "drawer_write_calls": 0,
        "kg_write_calls": 0,
        "diary_write_calls": 0,
    })
    thinking_ms: int = 0
    replying_ms: int = 0

OPS_DIR = Path("/home/ubuntu/apps/kaguya-gateway/ops")
CORE_IDENTITY_FILE = OPS_DIR / "prompts" / "core_identity.md"
WRITING_CONSTITUTION_FILE = OPS_DIR / "prompts" / "writing_constitution.md"
SYSTEM_PROMPT_FILE = OPS_DIR / "prompts" / "system.md"
SAKUYA_PROFILE_FILE = OPS_DIR / "profiles" / "sakuya.md"
KAGUYA_PROFILE_FILE = OPS_DIR / "profiles" / "kaguya.md"


def _clean_text(value: str) -> str:
    return (value or "").strip()


def _read_optional_text(path: Path) -> str:
    if not path.exists():
        logger.warning("prompt/profile file missing: %s", path)
        return ""
    text = path.read_text(encoding="utf-8").strip()
    logger.info("loaded prompt/profile file=%s chars=%s", path, len(text))
    return text


def _load_external_prompt_material() -> dict[str, str]:
    docs = {
        "core": _read_optional_text(CORE_IDENTITY_FILE),
        "writing": _read_optional_text(WRITING_CONSTITUTION_FILE),
        "system": _read_optional_text(SYSTEM_PROMPT_FILE),
        "sakuya": _read_optional_text(SAKUYA_PROFILE_FILE),
        "kaguya": _read_optional_text(KAGUYA_PROFILE_FILE),
    }
    logger.info(
        "external prompt material loaded core_chars=%s writing_chars=%s system_chars=%s sakuya_chars=%s kaguya_chars=%s",
        len(docs["core"]),
        len(docs["writing"]),
        len(docs["system"]),
        len(docs["sakuya"]),
        len(docs["kaguya"]),
    )
    return docs


def _base_system_sections(settings: Settings, wakeup_text: str) -> list[str]:
    docs = _load_external_prompt_material()

    sections = [
        f"You are {settings.system_name}.",
        "You are replying inside a Telegram chat.",
        "You have direct access to the original MemPalace toolset.",
        "The following materials are HIGH PRIORITY runtime context.",
        "Identity and writing constitution are the highest-priority layers.",
        "Do not treat them as optional flavor text.",
    ]

    if docs["core"]:
        sections.extend(
            [
                "=== CORE IDENTITY: HIGHEST PRIORITY ===",
                docs["core"],
            ]
        )

    if docs["writing"]:
        sections.extend(
            [
                "=== WRITING CONSTITUTION: HIGHEST PRIORITY STYLE LAYER ===",
                docs["writing"],
            ]
        )

    if docs["system"]:
        sections.extend(
            [
                "=== HIGH PRIORITY RUNTIME INSTRUCTIONS ===",
                docs["system"],
            ]
        )

    if docs["sakuya"]:
        sections.extend(
            [
                "=== HIGH PRIORITY PROFILE: SAKUYA ===",
                docs["sakuya"],
            ]
        )

    if docs["kaguya"]:
        sections.extend(
            [
                "=== HIGH PRIORITY PROFILE: KAGUYA ===",
                docs["kaguya"],
            ]
        )

    sections.extend(
        [
            "The wake-up text below is a startup anchor generated from MemPalace.",
            "Treat that wake-up text as orientation and continuity, not as a substitute for live MemPalace tool use.",
            "When memory, identity, prior chats, earlier decisions, palace state, relationship context, or past events matter, use original MemPalace tools rather than guessing.",
            "Prefer the most specific MemPalace tool for the task.",
            "Use mempalace_search for prior conversation content.",
            "Use mempalace_kg_query for known entities, facts, and relationship/history queries.",
            "Use mempalace_traverse or mempalace_find_tunnels when structure or connections matter.",
            "Call mempalace_status only when you truly need the official palace overview, protocol, or AAAK dialect.",
            "Do not invent memory or facts. If the tools return little or nothing, say so plainly.",
            "Your identity continuity and writing style should follow the high-priority materials above unless they conflict with tool-verified facts.",
            "Startup anchor:",
            _clean_text(wakeup_text),
        ]
    )

    return sections


def build_reply_system_prompt(
    settings: Settings,
    wakeup_text: str,
    force_status_bootstrap: bool,
) -> str:
    sections: List[str] = _base_system_sections(settings, wakeup_text)

    if force_status_bootstrap:
        sections.extend(
            [
                "This is your first active reply in a fresh runtime session.",
                "Before answering this user message, call mempalace_status once to load the official MemPalace protocol and AAAK dialect.",
            ]
        )
    else:
        sections.extend(
            [
                "This is not the first reply in the current runtime session.",
                "Do not call mempalace_status by default.",
                "Only call mempalace_status if you specifically need refreshed palace-wide protocol, official overview, or AAAK guidance.",
            ]
        )

    return "\n\n".join(section for section in sections if section)


def build_checkpoint_system_prompt(settings: Settings, wakeup_text: str) -> str:
    sections: List[str] = _base_system_sections(settings, wakeup_text)
    sections.extend(
        [
            "You are performing an INTERNAL MemPalace save checkpoint, not a user-visible reply.",
            "Use the original MemPalace tools to save what matters from the recent Telegram conversation.",
            "Prefer diary, KG, and drawer tools when appropriate.",
            "Do not chat with the user during this checkpoint.",
            "When you are done saving, reply with exactly: CHECKPOINT_COMPLETE",
        ]
    )
    return "\n\n".join(section for section in sections if section)


def _append_recent_turns(messages: list[dict], recent_turns: list[Turn]) -> None:
    for past_user, past_assistant in recent_turns:
        past_user = _clean_text(past_user)
        past_assistant = _clean_text(past_assistant)

        if past_user:
            messages.append({"role": "user", "content": past_user})
        if past_assistant:
            messages.append({"role": "assistant", "content": past_assistant})


def build_reply_messages(
    settings: Settings,
    wakeup_text: str,
    recent_turns: list[Turn],
    user_text: str,
    force_status_bootstrap: bool,
) -> list[dict]:
    messages: list[dict] = [
        {
            "role": "system",
            "content": build_reply_system_prompt(
                settings=settings,
                wakeup_text=wakeup_text,
                force_status_bootstrap=force_status_bootstrap,
            ),
        }
    ]

    _append_recent_turns(messages, recent_turns)
    messages.append({"role": "user", "content": _clean_text(user_text)})
    return messages


def build_checkpoint_messages(
    settings: Settings,
    wakeup_text: str,
    recent_turns: list[Turn],
) -> list[dict]:
    messages: list[dict] = [
        {
            "role": "system",
            "content": build_checkpoint_system_prompt(
                settings=settings,
                wakeup_text=wakeup_text,
            ),
        }
    ]

    _append_recent_turns(messages, recent_turns)
    messages.append(
        {
            "role": "user",
            "content": (
                "Run a MemPalace save checkpoint for the recent Telegram session now. "
                "Use original MemPalace tools as needed, then reply exactly with CHECKPOINT_COMPLETE."
            ),
        }
    )
    return messages


def _extract_text(response) -> str:
    if not response.choices:
        return ""

    message = response.choices[0].message
    content = message.content

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if text:
                parts.append(text)
        return "\n".join(parts).strip()

    return ""


def _serialize_tool_calls(tool_calls) -> list[dict]:
    serialized: list[dict] = []
    for tool_call in tool_calls:
        serialized.append(
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments or "{}",
                },
            }
        )
    return serialized


def create_client(settings: Settings) -> OpenAI:
    return OpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        timeout=60.0,
        max_retries=2,
    )


def _run_tool_loop(
    settings: Settings,
    messages: list[dict],
    max_tool_rounds: int,
    log_context: dict | None = None,
) -> ToolLoopResult:
    client = create_client(settings)
    logs_dir = settings.logs_dir
    ctx = log_context or {}
    turn_type = ctx.get("turn_type", "unknown")
    chat_id = ctx.get("chat_id", "")
    turn_id = ctx.get("turn_id", "")

    result = ToolLoopResult(reply_text="")
    t0_thinking = time.monotonic()

    for round_index in range(max_tool_rounds):
        if turn_id:
            realtime_bus.emit("processing", {
                "turn_id": turn_id,
                "chat_id": chat_id,
                "message": f"LLM round {round_index + 1}: planning",
            })
        response = client.chat.completions.create(
            model=settings.openrouter_model,
            messages=messages,
            tools=OPENAI_TOOLS,
            tool_choice="auto",
            extra_body={
                "provider": {
                    "require_parameters": True
                }
            },
        )

        # --- Token usage logging ---
        usage = getattr(response, "usage", None)
        if usage:
            prompt_tok = getattr(usage, "prompt_tokens", 0) or 0
            completion_tok = getattr(usage, "completion_tokens", 0) or 0
            result.total_prompt_tokens += prompt_tok
            result.total_completion_tokens += completion_tok
            append_jsonl(logs_dir / "token_usage.jsonl", {
                "ts": _now_iso(),
                "turn_type": turn_type,
                "round": round_index + 1,
                "model": settings.openrouter_model,
                "prompt_tokens": prompt_tok,
                "completion_tokens": completion_tok,
                "total_tokens": prompt_tok + completion_tok,
                "chat_id": chat_id,
            })

        choice = response.choices[0]
        message = choice.message
        tool_calls = getattr(message, "tool_calls", None) or []

        if tool_calls:
            result.total_rounds = round_index + 1
            tool_names = [tool_call.function.name for tool_call in tool_calls]
            logger.info("llm tool round=%s tool_calls=%s", round_index + 1, tool_names)
            if turn_id:
                realtime_bus.emit("thinking", {
                    "turn_id": turn_id,
                    "chat_id": chat_id,
                    "chunk": f"[round {round_index + 1}] tool planning: {', '.join(tool_names)}\n",
                    "elapsed_ms": int((time.monotonic() - t0_thinking) * 1000),
                })

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": _serialize_tool_calls(tool_calls),
                }
            )

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                raw_args = tool_call.function.arguments
                try:
                    args_dict = json.loads(raw_args) if raw_args else {}
                except json.JSONDecodeError:
                    args_dict = {}

                t0 = time.monotonic()
                error_msg = None
                success = True
                tool_result = ""
                if turn_id:
                    realtime_bus.emit("tool_start", {
                        "turn_id": turn_id,
                        "chat_id": chat_id,
                        "tool_name": tool_name,
                    })

                try:
                    tool_result = execute_tool(
                        tool_name=tool_name,
                        arguments=raw_args,
                    )
                except Exception as exc:
                    success = False
                    error_msg = str(exc)
                    tool_result = f"Error: {error_msg}"

                elapsed_ms = int((time.monotonic() - t0) * 1000)
                if turn_id:
                    realtime_bus.emit("tool_end", {
                        "turn_id": turn_id,
                        "chat_id": chat_id,
                        "tool_name": tool_name,
                        "success": success,
                        "elapsed_ms": elapsed_ms,
                    })

                logger.info(
                    "executed tool=%s result_chars=%s success=%s elapsed_ms=%s",
                    tool_name,
                    len(tool_result or ""),
                    success,
                    elapsed_ms,
                )

                # --- Tool call logging ---
                result.tools_called.append(tool_name)
                if success:
                    result.tools_succeeded += 1
                    write_key = _PALACE_WRITE_TOOLS.get(tool_name)
                    if write_key:
                        result.palace_writes[write_key] += 1
                else:
                    result.tools_failed += 1

                append_jsonl(logs_dir / "tool_calls.jsonl", {
                    "ts": _now_iso(),
                    "turn_type": turn_type,
                    "chat_id": chat_id,
                    "round": round_index + 1,
                    "tool_name": tool_name,
                    "arguments_summary": summarize_arguments(tool_name, args_dict),
                    "success": success,
                    "result_chars": len(tool_result or ""),
                    "elapsed_ms": elapsed_ms,
                    "error": error_msg,
                })

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result or "",
                    }
                )

            continue

        result.total_rounds = round_index + 1
        reply = _extract_text(response)
        if not reply:
            raise RuntimeError("LLM returned empty content")

        result.thinking_ms = int((time.monotonic() - t0_thinking) * 1000)
        t0_reply = time.monotonic()
        if turn_id:
            chunk_size = 120
            for idx in range(0, len(reply), chunk_size):
                realtime_bus.emit("replying", {
                    "turn_id": turn_id,
                    "chat_id": chat_id,
                    "chunk": reply[idx: idx + chunk_size],
                    "elapsed_ms": int((time.monotonic() - t0_reply) * 1000),
                })
        result.replying_ms = int((time.monotonic() - t0_reply) * 1000)
        result.reply_text = reply
        return result

    raise RuntimeError("LLM exceeded maximum MemPalace tool-calling rounds")


def generate_reply(
    settings: Settings,
    wakeup_text: str,
    _legacy_memory_text: str,
    recent_turns: list[Turn],
    user_text: str,
    max_tool_rounds: int = 6,
    force_status_bootstrap: bool = False,
    chat_id: str = "",
    turn_id: str = "",
) -> ToolLoopResult:
    messages = build_reply_messages(
        settings=settings,
        wakeup_text=wakeup_text,
        recent_turns=recent_turns,
        user_text=user_text,
        force_status_bootstrap=force_status_bootstrap,
    )
    return _run_tool_loop(
        settings=settings,
        messages=messages,
        max_tool_rounds=max_tool_rounds,
        log_context={"turn_type": "reply", "chat_id": chat_id, "turn_id": turn_id},
    )


def run_memory_checkpoint(
    settings: Settings,
    wakeup_text: str,
    recent_turns: list[Turn],
    max_tool_rounds: int = 8,
    chat_id: str = "",
    turn_id: str = "",
) -> ToolLoopResult:
    messages = build_checkpoint_messages(
        settings=settings,
        wakeup_text=wakeup_text,
        recent_turns=recent_turns,
    )
    return _run_tool_loop(
        settings=settings,
        messages=messages,
        max_tool_rounds=max_tool_rounds,
        log_context={"turn_type": "checkpoint", "chat_id": chat_id, "turn_id": turn_id},
    )
