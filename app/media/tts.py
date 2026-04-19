"""MiniMax speech synthesis client.

通过 POST /v1/t2a_v2?GroupId=... 同步调用 MiniMax TTS,返回 mp3 音频字节。

第一版日语 voice_id (kaguya_ja_v1) 已就绪,中文 voice_id 未来补齐。
_select_voice_id 在两者都配置时根据文本是否含日文假名自动路由;
只有一侧配置时就用那一侧,不报错。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx


logger = logging.getLogger(__name__)


_T2A_ENDPOINT = "https://api.minimaxi.com/v1/t2a_v2"
_DEFAULT_MODEL = "speech-2.8-hd"
_TIMEOUT_SECONDS = 30.0


class TTSError(Exception):
    """TTS synthesis failed."""


@dataclass
class TTSResult:
    audio: bytes
    mime_type: str
    duration_ms: int
    usage_characters: int
    voice_id: str


def _has_kana(text: str) -> bool:
    """Detect Japanese hiragana/katakana (not kanji — shared with Chinese)."""
    for ch in text:
        if "\u3040" <= ch <= "\u309f":  # hiragana
            return True
        if "\u30a0" <= ch <= "\u30ff":  # katakana
            return True
    return False


class MiniMaxTTSClient:
    def __init__(
        self,
        *,
        api_key: str,
        group_id: str,
        voice_id_ja: str = "",
        voice_id_zh: str = "",
        model: str = _DEFAULT_MODEL,
    ) -> None:
        if not api_key or not group_id:
            raise ValueError("MiniMax api_key and group_id are required")
        if not (voice_id_ja or voice_id_zh):
            raise ValueError("At least one voice_id (ja or zh) must be configured")
        self.api_key = api_key
        self.group_id = group_id
        self.voice_id_ja = voice_id_ja
        self.voice_id_zh = voice_id_zh
        self.model = model

    def _select_voice_id(self, text: str, language: Optional[str]) -> str:
        if language == "ja":
            return self.voice_id_ja or self.voice_id_zh
        if language == "zh":
            return self.voice_id_zh or self.voice_id_ja
        # auto: 有日文假名则 ja;否则优先 zh,zh 空则 fallback ja
        if _has_kana(text) and self.voice_id_ja:
            return self.voice_id_ja
        return self.voice_id_zh or self.voice_id_ja

    def synthesize(
        self,
        text: str,
        *,
        language: Optional[str] = None,
        speed: float = 1.0,
        vol: float = 1.0,
        pitch: int = 0,
    ) -> TTSResult:
        voice_id = self._select_voice_id(text, language)
        if not voice_id:
            raise TTSError("no voice_id available for this request")

        url = f"{_T2A_ENDPOINT}?GroupId={self.group_id}"
        payload = {
            "model": self.model,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": speed,
                "vol": vol,
                "pitch": pitch,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300] if exc.response is not None else ""
            logger.exception("minimax TTS HTTP error")
            raise TTSError(f"HTTP {exc.response.status_code}: {body}") from exc
        except httpx.HTTPError as exc:
            logger.exception("minimax TTS http error")
            raise TTSError(f"{type(exc).__name__}: {exc}") from exc
        except Exception as exc:
            logger.exception("minimax TTS request failed")
            raise TTSError(f"{type(exc).__name__}: {exc}") from exc

        base_resp = data.get("base_resp") or {}
        if base_resp.get("status_code") != 0:
            raise TTSError(f"minimax error {base_resp}")

        audio_hex = (data.get("data") or {}).get("audio") or ""
        if not audio_hex:
            raise TTSError(f"empty audio field in response: {data}")

        try:
            audio_bytes = bytes.fromhex(audio_hex)
        except ValueError as exc:
            raise TTSError(f"audio hex decode failed: {exc}") from exc

        extra = data.get("extra_info") or {}
        return TTSResult(
            audio=audio_bytes,
            mime_type="audio/mpeg",
            duration_ms=int(extra.get("audio_length") or 0),
            usage_characters=int(extra.get("usage_characters") or len(text)),
            voice_id=voice_id,
        )
