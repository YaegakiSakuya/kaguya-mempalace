from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI


logger = logging.getLogger(__name__)


_VISION_PROMPT = """请分析这张图片，用中文输出一个 JSON 对象，必须且仅包含以下两个字段：

description: 一段 50-150 字的自然描述，涵盖图中主要内容、场景、氛围、可识别的物件、画面构图或情绪基调。避免空洞形容词，避免推测人物身份。若图中有明显的异常或值得注意的细节（如错位、残缺、标注），要一并写出。

ocr_text: 图中可辨识文字的纯文本转录，按视觉顺序拼接成一段，用换行分隔不同区块。若无文字，填空字符串 ""。

请直接输出 JSON 对象，不要使用代码块包裹，不要加任何解释或前后文。"""


@dataclass(frozen=True)
class VisionAnalysis:
    description: str
    ocr_text: str
    model: str
    raw_response: str  # 完整原始回复，用于调试或异常排查


class VisionError(RuntimeError):
    """视觉代理调用失败的统一异常类型。"""


class VisionAgent:
    """视觉代理,一次调用把图片翻译成 description + ocr_text 两段文本。

    默认接硅基流动(SiliconFlow)提供的 OpenAI 兼容接口,
    底层模型由构造参数决定(当前默认 Qwen/Qwen3-VL-235B-A22B-Instruct)。
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 60.0,
        max_tokens: int = 800,
    ) -> None:
        if not api_key:
            raise ValueError("VisionAgent requires api_key")
        if not model:
            raise ValueError("VisionAgent requires model")
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self._model = model
        self._max_tokens = max_tokens

    def analyze(
        self,
        image_bytes: bytes,
        mime_type: str,
        user_hint: Optional[str] = None,
    ) -> VisionAnalysis:
        """看一张图,返回结构化的 VisionAnalysis。

        image_bytes: 建议是已经过 compress_image 压缩的字节,避免烧 token
        mime_type: "image/jpeg" / "image/png" / "image/webp"
        user_hint: 可选的附加上下文,例如 TG caption,模型会参考但不必严格遵循
        """
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{mime_type};base64,{b64}"

        prompt = _VISION_PROMPT
        if user_hint:
            prompt = f"{prompt}\n\n[附加上下文: {user_hint.strip()}]"

        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": data_url}},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                temperature=0.2,
                max_tokens=self._max_tokens,
            )
        except Exception as exc:
            raise VisionError(f"视觉模型调用失败: {exc}") from exc

        content = resp.choices[0].message.content or ""
        raw = content.strip()

        description, ocr_text = self._parse_response(raw)

        return VisionAnalysis(
            description=description,
            ocr_text=ocr_text,
            model=self._model,
            raw_response=raw,
        )

    @staticmethod
    def _parse_response(raw: str) -> tuple[str, str]:
        """从模型回复里抽出 description 和 ocr_text。

        正常情况是纯 JSON。对抗模型偶尔加 markdown 代码围栏、多余解释的情况,
        用正则剥一层 fence,再 json.loads。失败则把整段当 description,ocr 留空。
        """
        text = raw

        # 剥 ```json ... ``` 或 ``` ... ``` 围栏
        fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()

        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                desc = str(obj.get("description", "")).strip()
                ocr = str(obj.get("ocr_text", "")).strip()
                if desc:
                    return desc, ocr
        except json.JSONDecodeError:
            logger.warning("Vision response is not valid JSON, falling back to raw text")

        # 降级:把整段raw当description,ocr置空
        return raw, ""
