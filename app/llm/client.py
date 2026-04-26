from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from openai import OpenAI

from app.core import runtime_config
from app.core.config import Settings
from app.inspector.logger import append_jsonl, summarize_arguments, _now_iso
from app.llm.ops_tools import (
    build_ops_openai_tools,
    execute_ops_tool,
    OPS_TOOL_NAMES,
)
from app.llm.web_tools import (
    build_web_openai_tools,
    execute_web_tool,
    WEB_TOOL_NAMES,
)
from app.llm.voice_tools import (
    build_voice_openai_tools,
    execute_voice_tool,
    VOICE_TOOL_NAMES,
)
from app.llm.yoru_tools import (
    build_yoru_openai_tools,
    execute_yoru_tool,
    summarize_yoru_args,
    YORU_TOOL_NAMES,
)
from app.memory.palace import load_recent_diary
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

OPS_DIR = Path("/home/ubuntu/apps/kaguya-mempalace/ops")
SYSTEM_PROMPT_FILE = OPS_DIR / "prompts" / "system.md"
CHECKPOINT_INSTRUCTION_FILE = OPS_DIR / "prompts" / "checkpoint_instruction.md"


def _clean_text(value: str) -> str:
    return (value or "").strip()


_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def _split_reply_into_bubbles(
    text: str,
    max_len: int = 3800,
    min_chunk_chars: int = 20,
) -> list[str]:
    """Split an LLM reply into multiple Telegram bubbles.

    Rules:
    1. Primary split on blank lines (\\n\\s*\\n).
    2. Merge chunks shorter than ``min_chunk_chars`` into the previous chunk.
    3. Further split chunks longer than ``max_len`` by single newlines, then
       by sentence terminators, and finally by hard slicing.
    4. Markdown fenced code blocks (```...```) stay intact.

    Each returned string is stripped and guaranteed non-empty.
    """
    text = (text or "").strip()
    if not text:
        return []

    placeholders: list[str] = []

    def _stash(match: re.Match[str]) -> str:
        placeholders.append(match.group(0))
        return f"\x00FENCE{len(placeholders) - 1}\x00"

    stashed = _FENCE_RE.sub(_stash, text)

    raw_chunks = re.split(r"\n\s*\n", stashed)
    raw_chunks = [c.strip() for c in raw_chunks if c.strip()]

    def _restore(value: str) -> str:
        def repl(match: re.Match[str]) -> str:
            idx = int(match.group(1))
            return placeholders[idx]

        return re.sub(r"\x00FENCE(\d+)\x00", repl, value)

    # Restore fences BEFORE measuring chunk length for the short-chunk merge,
    # otherwise a standalone fenced code block (represented as a ~10 char
    # placeholder) would always look shorter than ``min_chunk_chars`` and get
    # merged into the previous bubble, potentially producing oversized bubbles
    # whose later hard-split breaks fence boundaries across messages.
    restored_chunks = [_restore(c) for c in raw_chunks]

    merged: list[str] = []
    for chunk in restored_chunks:
        if merged and len(chunk) < min_chunk_chars:
            merged[-1] = merged[-1] + "\n\n" + chunk
        else:
            merged.append(chunk)

    restored = merged

    _SENTENCE_SPLIT_RE = re.compile(r"(?<=[。?!?!.])")

    final: list[str] = []
    for chunk in restored:
        if len(chunk) <= max_len:
            final.append(chunk)
            continue

        sub_parts = chunk.split("\n")
        buf = ""
        for part in sub_parts:
            candidate = (buf + "\n" + part) if buf else part
            if len(candidate) <= max_len:
                buf = candidate
                continue

            if buf:
                final.append(buf.strip())
                buf = ""

            if len(part) <= max_len:
                buf = part
                continue

            # Part itself is too long — try sentence-level split, then hard slice.
            sentence_buf = ""
            for sentence in _SENTENCE_SPLIT_RE.split(part):
                if not sentence:
                    continue
                cand2 = sentence_buf + sentence
                if len(cand2) <= max_len:
                    sentence_buf = cand2
                    continue
                if sentence_buf:
                    final.append(sentence_buf.strip())
                    sentence_buf = ""
                if len(sentence) <= max_len:
                    sentence_buf = sentence
                else:
                    for i in range(0, len(sentence), max_len):
                        final.append(sentence[i : i + max_len])
            if sentence_buf:
                buf = sentence_buf
        if buf:
            final.append(buf.strip())

    return [s for s in (p.strip() for p in final) if s]


def _read_optional_text(path: Path) -> str:
    if not path.exists():
        logger.warning("prompt/profile file missing: %s", path)
        return ""
    text = path.read_text(encoding="utf-8").strip()
    logger.info("loaded prompt/profile file=%s chars=%s", path, len(text))
    return text


def _load_external_prompt_material() -> dict[str, str]:
    docs = {
        "system": _read_optional_text(SYSTEM_PROMPT_FILE),
        "checkpoint": _read_optional_text(CHECKPOINT_INSTRUCTION_FILE),
    }
    logger.info(
        "external prompt material loaded system_chars=%s checkpoint_chars=%s",
        len(docs["system"]),
        len(docs["checkpoint"]),
    )
    return docs


def _base_system_sections(settings: Settings) -> list[str]:
    """Build the shared system prompt foundation.

    新架构 (2026-04-21 重构):
    - 读 ops/prompts/system.md (朔自己维护的单一 DNA 文档: identity + writing
      constitution + syzygy profile + kaguya profile + palace structure,
      末尾带 === RECENT MEMORY HORIZON === 占位)
    - 在 system.md 末尾追加最近 6 条 diary (mempalace_diary_read) 作为
      情绪印象连续性

    不再做任何代码侧的标题插入或英文脚手架拼接。system.md 文件自己管层级。
    """
    sections: list[str] = []

    system_text = _load_external_prompt_material()["system"]
    if system_text:
        sections.append(system_text)

    diary_horizon = load_recent_diary(n=6)
    if diary_horizon:
        sections.append(diary_horizon)

    return sections


def build_reply_system_prompt(settings: Settings) -> str:
    """Build the reply-path system prompt.

    Just _base_system_sections joined — no more force_status_bootstrap
    branching (AAAK 已废,mempalace_status 按需调即可,不需要首轮强制引导)。
    """
    sections: List[str] = _base_system_sections(settings)
    return "\n\n".join(section for section in sections if section)


def build_checkpoint_system_prompt(settings: Settings) -> str:
    """Build the autosave checkpoint system prompt.

    Layers DNA from _base_system_sections (system.md + diary horizon) then
    appends the checkpoint instruction from ops/prompts/checkpoint_instruction.md
    — which tells Kaguya how to write diary, identify topics, pick wing +
    room, and optionally build tunnels. Falls back to a minimal English
    instruction if the external file is missing.
    """
    sections: List[str] = _base_system_sections(settings)
    checkpoint_instruction = _load_external_prompt_material()["checkpoint"]
    if checkpoint_instruction:
        sections.extend(
            [
                "=== AUTOSAVE CHECKPOINT INSTRUCTION ===",
                checkpoint_instruction,
            ]
        )
    else:
        logger.warning(
            "checkpoint_instruction.md missing — falling back to minimal English"
        )
        sections.extend(
            [
                "You are performing an INTERNAL MemPalace save checkpoint, not a user-visible reply.",
                "Use MemPalace tools to save what matters from the recent conversation.",
                "When you are done saving, reply with exactly: CHECKPOINT_COMPLETE",
            ]
        )
    return "\n\n".join(section for section in sections if section)


def _append_recent_turns(messages: list[dict], recent_turns: list[Turn]) -> None:
    for past_user, past_assistant in recent_turns:
        past_user = _clean_text(past_user)
        past_assistant = _clean_text(past_assistant)

        if past_user:
            messages.append({"role": "user", "content": f"[朔夜] {past_user}"})
        if past_assistant:
            # assistant 侧不再加 [辉夜] 前缀：role=assistant 本身已是身份锚，
            # 对称前缀只会把 [辉夜] 变成 few-shot 模板，逼模型每次署名开头。
            messages.append({"role": "assistant", "content": past_assistant})


def build_reply_messages(
    settings: Settings,
    recent_turns: list[Turn],
    user_text: str,
) -> list[dict]:
    messages: list[dict] = [
        {
            "role": "system",
            "content": build_reply_system_prompt(settings=settings),
        }
    ]

    _append_recent_turns(messages, recent_turns)
    messages.append({"role": "user", "content": f"[朔夜] {_clean_text(user_text)}"})
    return messages


def build_checkpoint_messages(
    settings: Settings,
    recent_turns: list[Turn],
) -> list[dict]:
    messages: list[dict] = [
        {
            "role": "system",
            "content": build_checkpoint_system_prompt(settings=settings),
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
    tools: list[dict],
    *,
    model: str,
    on_thinking_chunk=None,
    on_reply_chunk=None,
):
    # 智谱 GLM 独家扩展参数，非智谱 provider 不传。
    # 从 client 自身读取 base_url，与 _run_tool_loop 的快照保持一致，
    # 避免 mid-loop 切换 provider 时与实际请求端点分叉。
    client_base_url = str(getattr(client, "base_url", "") or "")
    create_kwargs = dict(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        stream=True,
        stream_options={"include_usage": True},
    )
    if "bigmodel.cn" in client_base_url.lower():
        create_kwargs["extra_body"] = {
            "thinking": {"type": "enabled", "clear_thinking": False}
        }
    response_stream = client.chat.completions.create(**create_kwargs)

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
    """Build an OpenAI-compatible client using the runtime-config overlay.

    The ``settings`` parameter is kept for signature stability but the live
    ``base_url`` / ``api_key`` come from :mod:`app.core.runtime_config`, which
    falls back to ``Settings`` values on first run.
    """
    base_url, api_key, _ = runtime_config.get_active_client_config()
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=60.0,
        max_retries=2,
    )


def _run_tool_loop(
    settings: Settings,
    messages: list[dict],
    max_tool_rounds: int,
    log_context: dict | None = None,
    *,
    include_yoru_tools: bool = True,
) -> ToolLoopResult:
    # Snapshot the runtime-config LLM settings once per tool loop so the client,
    # base URL and model stay consistent across rounds even if the operator
    # switches provider/model mid-loop.
    base_url, api_key, active_model = runtime_config.get_active_client_config()
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=60.0,
        max_retries=2,
    )
    logs_dir = settings.logs_dir
    ctx = log_context or {}
    turn_type = ctx.get("turn_type", "unknown")
    chat_id = ctx.get("chat_id", "")

    result = ToolLoopResult(reply_text="")

    # Yoru 写工具 (create/update/delete shiori) 只允许在用户回复回合暴露,
    # autosave checkpoint 不带 yoru —— checkpoint 是后台无人值守的回合,
    # description 写的"只在朔夜明确说『记下来』时才调用"靠的就是工具不出现。
    all_tools = OPENAI_TOOLS + build_ops_openai_tools() + build_web_openai_tools() + build_voice_openai_tools()
    if include_yoru_tools:
        all_tools = all_tools + build_yoru_openai_tools()

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
            tools=all_tools,
            model=active_model,
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
                "model": active_model,
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

                # Yoru 写工具的 na/ki/koe 是私密自由文本,日志/SSE 都要脱敏,
                # 不能依赖 inspector.logger.summarize_arguments 的 unknown-tool
                # fallback (它会保留 <200 字符的字符串原样)。
                log_args = (
                    summarize_yoru_args(args_dict)
                    if tool_name in YORU_TOOL_NAMES
                    else args_dict
                )

                if sse_manager.has_active_connection():
                    sse_manager.push("tool_call", {
                        "tool": tool_name,
                        "round": round_index + 1,
                        "args_summary": summarize_arguments(tool_name, log_args),
                    })

                t0 = time.monotonic()
                error_msg = None
                success = True
                tool_result = ""

                try:
                    if tool_name in OPS_TOOL_NAMES:
                        tool_result = execute_ops_tool(tool_name)
                    elif tool_name in WEB_TOOL_NAMES:
                        tool_result = execute_web_tool(tool_name, args_dict)
                    elif tool_name in VOICE_TOOL_NAMES:
                        tool_result = execute_voice_tool(
                            tool_name,
                            args_dict,
                            chat_id=str(chat_id),
                            settings=settings,
                        )
                    elif tool_name in YORU_TOOL_NAMES:
                        tool_result = execute_yoru_tool(tool_name, args_dict)
                    else:
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
                    "arguments_summary": summarize_arguments(tool_name, log_args),
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

        if not streamed_reply or not streamed_reply.strip():
            raise RuntimeError("LLM returned empty content on final round")

        # Single-bubble UX by default; fall back to splitter only when the
        # reply would exceed Telegram's per-message limit (~4096 chars).
        if len(streamed_reply) <= 3800:
            result.reply_segments.append(streamed_reply)
        else:
            result.reply_segments.extend(_split_reply_into_bubbles(streamed_reply))
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
    recent_turns: list[Turn],
    user_text: str,
    max_tool_rounds: int = 6,
    chat_id: str = "",
) -> ToolLoopResult:
    messages = build_reply_messages(
        settings=settings,
        recent_turns=recent_turns,
        user_text=user_text,
    )
    return _run_tool_loop(
        settings=settings,
        messages=messages,
        max_tool_rounds=max_tool_rounds,
        log_context={"turn_type": "reply", "chat_id": chat_id},
    )


def run_memory_checkpoint(
    settings: Settings,
    recent_turns: list[Turn],
    max_tool_rounds: int = 8,
    chat_id: str = "",
) -> ToolLoopResult:
    messages = build_checkpoint_messages(
        settings=settings,
        recent_turns=recent_turns,
    )
    return _run_tool_loop(
        settings=settings,
        messages=messages,
        max_tool_rounds=max_tool_rounds,
        log_context={"turn_type": "checkpoint", "chat_id": chat_id},
        include_yoru_tools=False,
    )
