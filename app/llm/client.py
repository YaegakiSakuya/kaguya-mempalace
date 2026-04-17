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
from app.memory.tools import OPENAI_TOOLS, execute_tool
from app.miniapp.sse import sse_manager

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
    reply_segments: list[str] = field(default_factory=list)
    thinking_preview: str = ""
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


def _delta_reasoning_text(delta) -> str:
    value = getattr(delta, "reasoning_content", None)
    if isinstance(value, str):
        return value
    return ""


def _delta_content_text(delta) -> str:
    value = getattr(delta, "content", None)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            text = getattr(item, "text", None)
            if text:
                parts.append(text)
        return "".join(parts)
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


def _merge_tool_call_delta(acc: list[dict], delta_tool_calls) -> None:
    for delta in (delta_tool_calls or []):
        index = getattr(delta, "index", 0) or 0
        while len(acc) <= index:
            acc.append({
                "id": "",
                "type": "function",
                "function": {"name": "", "arguments": ""},
            })

        target = acc[index]
        delta_id = getattr(delta, "id", None)
        if delta_id:
            target["id"] = delta_id

        delta_function = getattr(delta, "function", None)
        if delta_function:
            delta_name = getattr(delta_function, "name", None)
            if delta_name:
                target["function"]["name"] += delta_name

            delta_args = getattr(delta_function, "arguments", None)
            if delta_args:
                target["function"]["arguments"] += delta_args


def _normalize_tool_calls(tool_calls: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for idx, item in enumerate(tool_calls):
        fn = item.get("function", {}) if isinstance(item, dict) else {}
        normalized.append({
            "id": item.get("id") or f"stream_tool_call_{idx}",
            "type": "function",
            "function": {
                "name": fn.get("name", ""),
                "arguments": fn.get("arguments", "") or "{}",
            },
        })
    return normalized


def _stream_chat_completion_round(
    client: OpenAI,
    settings: Settings,
    messages: list[dict],
    *,
    on_thinking_chunk=None,
    on_reply_chunk=None,
):
    response_stream = client.chat.completions.create(
        model=settings.openrouter_model,
        messages=messages,
        tools=OPENAI_TOOLS,
        tool_choice="auto",
        stream=True,
        stream_options={"include_usage": True},
        extra_body={
            "thinking": {"type": "enabled", "clear_thinking": False}
        },
    )

    reasoning_chunks: list[str] = []
    reply_chunks: list[str] = []
    streamed_tool_calls: list[dict] = []
    usage = None

    for chunk in response_stream:
        if getattr(chunk, "usage", None):
            usage = chunk.usage

        for choice in (getattr(chunk, "choices", None) or []):
            delta = getattr(choice, "delta", None)
            if not delta:
                continue

            reasoning_piece = _delta_reasoning_text(delta)
            if reasoning_piece:
                reasoning_chunks.append(reasoning_piece)
                if on_thinking_chunk is not None:
                    on_thinking_chunk(reasoning_piece)

            content_piece = _delta_content_text(delta)
            if content_piece:
                reply_chunks.append(content_piece)
                if on_reply_chunk is not None:
                    on_reply_chunk(content_piece)

            delta_tool_calls = getattr(delta, "tool_calls", None) or []
            if delta_tool_calls:
                _merge_tool_call_delta(streamed_tool_calls, delta_tool_calls)

    tool_calls = [
        item for item in streamed_tool_calls
        if item.get("function", {}).get("name")
    ]

    return (
        "".join(reasoning_chunks),
        "".join(reply_chunks).strip(),
        _normalize_tool_calls(tool_calls),
        usage,
    )


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

    result = ToolLoopResult(reply_text="")

    loop_start = time.monotonic()

    if sse_manager.has_active_connection():
        sse_manager.push("processing", {
            "step": "start",
            "message": "正在处理消息...",
        })

    for round_index in range(max_tool_rounds):
        if sse_manager.has_active_connection():
            sse_manager.push("processing", {
                "step": "thinking",
                "message": f"第 {round_index + 1} 轮思考中...",
            })

        reasoning_text, streamed_reply, tool_calls, usage = _stream_chat_completion_round(
            client=client,
            settings=settings,
            messages=messages,
            on_thinking_chunk=(
                (lambda chunk: sse_manager.push("thinking", {"chunk": chunk}))
                if sse_manager.has_active_connection() else None
            ),
            on_reply_chunk=(
                (lambda chunk: sse_manager.push("replying", {"chunk": chunk}))
                if sse_manager.has_active_connection() else None
            ),
        )

        if reasoning_text:
            result.thinking_preview = (result.thinking_preview or "") + reasoning_text

        # --- Token usage logging ---
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

        if tool_calls:
            result.total_rounds = round_index + 1
            tool_names = [tool_call.get("function", {}).get("name", "unknown") for tool_call in tool_calls]
            logger.info("llm tool round=%s tool_calls=%s", round_index + 1, tool_names)

            if streamed_reply and streamed_reply.strip():
                result.reply_segments.append(streamed_reply)

            messages.append(
                {
                    "role": "assistant",
                    "content": streamed_reply,
                    "tool_calls": tool_calls,
                }
            )

            for tool_call in tool_calls:
                tool_name = tool_call.get("function", {}).get("name", "")
                raw_args = tool_call.get("function", {}).get("arguments", "{}")
                try:
                    args_dict = json.loads(raw_args) if raw_args else {}
                except json.JSONDecodeError:
                    args_dict = {}

                if sse_manager.has_active_connection():
                    sse_manager.push("tool_call", {
                        "tool": tool_name,
                        "round": round_index + 1,
                        "args_summary": summarize_arguments(tool_name, args_dict),
                    })

                t0 = time.monotonic()
                error_msg = None
                success = True
                tool_result = ""

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

                if sse_manager.has_active_connection():
                    sse_manager.push("tool_done", {
                        "tool": tool_name,
                        "round": round_index + 1,
                        "success": success,
                        "duration_ms": elapsed_ms,
                    })

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", ""),
                        "content": tool_result or "",
                    }
                )

            continue

        result.total_rounds = round_index + 1

        if streamed_reply and streamed_reply.strip():
            result.reply_segments.append(streamed_reply)

        if not result.reply_segments:
            raise RuntimeError("LLM returned empty content across all rounds")

        result.reply_text = "\n\n".join(result.reply_segments)

        total_elapsed = int((time.monotonic() - loop_start) * 1000)
        if sse_manager.has_active_connection():
            sse_manager.push("done", {
                "input_tokens": result.total_prompt_tokens,
                "output_tokens": result.total_completion_tokens,
                "rounds": result.total_rounds,
                "tools": result.tools_called,
                "tools_succeeded": result.tools_succeeded,
                "tools_failed": result.tools_failed,
                "palace_writes": result.palace_writes,
                "elapsed_ms": total_elapsed,
                "response_preview": result.reply_text[:200] if result.reply_text else "",
                "segments_count": len(result.reply_segments),
            })

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
        log_context={"turn_type": "reply", "chat_id": chat_id},
    )


def run_memory_checkpoint(
    settings: Settings,
    wakeup_text: str,
    recent_turns: list[Turn],
    max_tool_rounds: int = 8,
    chat_id: str = "",
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
        log_context={"turn_type": "checkpoint", "chat_id": chat_id},
    )
