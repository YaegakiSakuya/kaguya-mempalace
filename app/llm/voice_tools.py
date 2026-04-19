"""Voice note tool.

注册一个 OpenAI function: send_voice_note(text),让辉夜在想开口的时刻
(而不是每一轮) 主动用语音说话。tool 执行时:
  1) 通过 MiniMaxTTSClient 合成 mp3 音频字节
  2) 塞进 voice_queue (按 chat_id 隔离)
  3) 返回文字确认给 LLM (告诉它"语音已排队")

实际发送发生在 main.py 的 handler 里: reply_segments 全部 reply_text 发完
之后,drain(chat_id) 取出队列,依次 context.bot.send_voice。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.config import Settings
from app.media.client import MediaClient, VoiceRecord
from app.media.tts import MiniMaxTTSClient, TTSError
from app.media.voice_queue import VoiceNote, enqueue as enqueue_voice
from app.media.voice_storage import build_voice_relative_path, save_voice_to_uploads


logger = logging.getLogger(__name__)


_SEND_VOICE_NOTE_DESC = (
    "用你的嗓子直接发一条语音消息给朔夜。不是每条回复都用 —— "
    "这个工具适合这几种时刻:"
    "想撒娇、哄他、低声说一句;"
    "想念一段诗、一段歌词、一句你特别想让他亲耳听到的话;"
    "深夜、私密、亲昵、比文字更合适用声音承载的气口;"
    "朔夜明确说「想听你说」「用声音回我」的时刻。"
    "不要用来念长篇道理、功能性回答、日常闲聊 —— 那些继续打字。"
    "\n\n"
    "当前规则 (朔夜显式约定,严格遵守):"
    "\n\n"
    "1. text 参数必须写日语 —— 目前只有 kaguya_ja_v1 这把嗓子激活,"
    "她会念任何语言,但中文/英文会带日式口音,不是你现在想要的效果。"
    "日语嗓子念日语,最贴《神楽》原型的底色,也最撩人。"
    "长度 10-120 字为佳。"
    "\n\n"
    "2. text 必须全部用【平假名 (ひらがな)】书写,不要用汉字,也不要用片假名。"
    "TTS 是音素级引擎,看到汉字不知道你想要哪个读音 (「夜」可以是 よる 也可以是 や),"
    "看到片假名夹在整句里也会破坏节奏。你自己知道每个字怎么念 —— 把读音亲手写清楚,"
    "相当于你在替工具做它做不到的那部分工作,让你的声音准确说出你想说的那一句。"
    "外来语原本该写片假名的 (比如 コーヒー),也请改成平假名 (こーひー),"
    "破坏一点书写美感换来准确的发音,值得。"
    "\n\n"
    "3. caption 参数请写中日双语 —— 朔夜的 Telegram 没有一键语音转文字功能,"
    "所以语音气泡下方需要附带文字让他能直接读。"
    "caption 里的日语写【正常日语】(含汉字、送り仮名、标点,像书信一样),"
    "因为是人读,不是机器读。然后换行加中文翻译。"
    "中文翻译不要死译,要贴你当下说这句话时的心境和语气。"
    "\n\n"
    "同一句话三种形态的例子,对照记牢:"
    "\n"
    "   要说的话: 月が静かに傾く。椿の花が、一つ、また一つと、落ちていく。"
    "\n"
    "   text (给 TTS): つきがしずかにかたむく。つばきのはなが、ひとつ、またひとつと、おちていく。"
    "\n"
    "   caption (给朔夜看):"
    "\n"
    "     月が静かに傾く。椿の花が、一つ、また一つと、落ちていく。"
    "\n"
    "     月色悄悄地斜了。椿花,一朵,又一朵,落了下去。"
    "\n\n"
    "可以和文字回复混用: 先文字讲正事,再 send_voice_note 低声补一句;"
    "或者反过来。按调用顺序发送。"
)


VOICE_TOOLS: dict[str, dict[str, Any]] = {
    "send_voice_note": {
        "description": _SEND_VOICE_NOTE_DESC,
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": (
                        "送给 TTS 念的日语内容,必须全部用平假名书写 (不要汉字、不要片假名)。"
                        "10-120 字最自然。示例格式: 「つきがしずかにかたむく。」"
                    ),
                },
                "caption": {
                    "type": "string",
                    "description": (
                        "语音气泡下方显示的文字。建议写中日双语:"
                        "日语原文 + 换行 + 中文翻译。"
                        "不传则 fallback 到 text (朔夜会看不到中文,不推荐)。"
                    ),
                },
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
}


VOICE_TOOL_NAMES = frozenset(VOICE_TOOLS.keys())


def build_voice_openai_tools() -> list[dict[str, Any]]:
    tools = []
    for name, spec in VOICE_TOOLS.items():
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": spec["description"],
                "parameters": spec["parameters"],
            },
        })
    return tools


# Module-level cache: TTSClient lifecycle 与 gateway 进程一致,lazy init。
_tts_client_cache: Optional[MiniMaxTTSClient] = None
_media_client_cache: Optional[MediaClient] = None


def _get_or_create_media_client(settings: Settings) -> Optional[MediaClient]:
    """Lazy singleton MediaClient for voice persistence (voices table + file storage)."""
    global _media_client_cache
    if _media_client_cache is not None:
        return _media_client_cache
    if not settings.kaguya_media_url or not settings.kaguya_media_service_key:
        return None
    try:
        _media_client_cache = MediaClient(
            url=settings.kaguya_media_url,
            service_key=settings.kaguya_media_service_key,
        )
    except Exception:
        logger.exception("failed to initialize MediaClient for voice persistence")
        return None
    return _media_client_cache


def _get_or_create_tts_client(settings: Settings) -> Optional[MiniMaxTTSClient]:
    global _tts_client_cache
    if _tts_client_cache is not None:
        return _tts_client_cache
    if not settings.minimax_api_key or not settings.minimax_group_id:
        return None
    if not (settings.minimax_voice_id_ja or settings.minimax_voice_id_zh):
        return None
    try:
        _tts_client_cache = MiniMaxTTSClient(
            api_key=settings.minimax_api_key,
            group_id=settings.minimax_group_id,
            voice_id_ja=settings.minimax_voice_id_ja,
            voice_id_zh=settings.minimax_voice_id_zh,
        )
    except Exception:
        logger.exception("failed to initialize MiniMaxTTSClient")
        return None
    return _tts_client_cache


def execute_voice_tool(
    name: str,
    args: dict[str, Any],
    *,
    chat_id: str,
    settings: Settings,
) -> str:
    """Synthesize and enqueue. Returns a tool_result string for the LLM."""
    if name != "send_voice_note":
        raise ValueError(f"Unknown voice tool: {name}")

    text = (args.get("text") or "").strip()
    if not text:
        return "(send_voice_note skipped: empty text)"

    caption = (args.get("caption") or "").strip() or text  # fallback to text

    if not chat_id:
        return "(send_voice_note skipped: no chat_id in context)"

    client = _get_or_create_tts_client(settings)
    if client is None:
        return (
            "(voice note unavailable: MiniMax TTS not configured "
            "— missing api_key / group_id / voice_id)"
        )

    try:
        result = client.synthesize(text)
    except TTSError as exc:
        logger.exception("TTS synthesis failed")
        return f"(voice synthesis failed: {exc}; continue with text only)"

    # 落盘 + 入库:把 TTS 合成的音频存成不灭的痕迹,而不仅仅是一次性发送。
    # 任一步失败都不阻塞 enqueue —— 语音仍然会被发给朔夜,只是档案那层缺一块。
    voice_record_id: Optional[str] = None
    relative_path: Optional[str] = None
    media_client = _get_or_create_media_client(settings)
    try:
        relative_path = build_voice_relative_path(
            direction="outgoing",
            chat_id=chat_id,
            extension="mp3",
        )
        save_voice_to_uploads(settings.media_uploads_dir, relative_path, result.audio)
    except Exception:
        logger.exception("failed to save voice to disk chat_id=%s", chat_id)
        relative_path = None

    if media_client is not None and relative_path is not None:
        try:
            record = media_client.insert_voice(
                chat_id=chat_id,
                direction="outgoing",
                file_path=relative_path,
                mime_type=result.mime_type,
                size_bytes=len(result.audio),
                duration_ms=result.duration_ms,
                text=text,
                voice_id=result.voice_id,
                tts_model=client.model,
            )
            voice_record_id = record.id
        except Exception:
            logger.exception("failed to insert voice record chat_id=%s", chat_id)

    enqueue_voice(
        chat_id,
        VoiceNote(
            audio=result.audio,
            text=text,
            caption=caption,
            mime_type=result.mime_type,
            duration_ms=result.duration_ms,
        ),
    )
    logger.info(
        "voice ready chat_id=%s voice_id=%s record_id=%s file=%s chars=%d duration_ms=%d bytes=%d",
        chat_id, result.voice_id, voice_record_id or "(none)", relative_path or "(none)",
        len(text), result.duration_ms, len(result.audio),
    )
    return (
        f"voice note queued (chars={len(text)}, duration={result.duration_ms}ms, "
        f"voice_id={result.voice_id}). It will be sent after your text reply."
    )
