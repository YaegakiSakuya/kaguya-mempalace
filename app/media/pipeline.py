from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.media.client import ImageRecord, MediaClient, MessageImageRecord
from app.media.storage import (
    build_relative_path,
    compress_image,
    compute_sha256,
    save_bytes_to_uploads,
)
from app.media.vision import VisionAgent, VisionError


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestResult:
    """一次 ingest_image 的返回,含入库结果与元信息。"""

    image: ImageRecord
    message_image: MessageImageRecord
    is_new: bool              # True=这是新图片,本次压缩+VL+入库;False=sha256命中,复用旧记录
    vision_failed: bool       # True=VL调用失败,已降级保存(无description)
    context_block: str        # 已格式化好、可直接塞进 LLM 对话历史的文本块


def format_context_block(image: ImageRecord, caption: Optional[str]) -> str:
    """把 ImageRecord 渲染成一段要注入主对话的文本。
    这是"视觉代理模式"的落点:主模型读到的是文本,不是图。
    """
    lines = ["[朔夜发来一张图片]"]
    if image.vl_description:
        lines.append(f"图像内容：{image.vl_description}")
    else:
        lines.append("图像内容：[视觉识别未完成]")
    if image.ocr_text:
        lines.append(f"图内文字：{image.ocr_text}")
    if caption:
        lines.append(f"朔夜附言：{caption.strip()}")
    return "\n".join(lines)


def ingest_image(
    *,
    raw_bytes: bytes,
    telegram_chat_id: int,
    telegram_message_id: int,
    user_id: int,
    caption: Optional[str],
    uploads_root: Path,
    media_client: MediaClient,
    vision_agent: VisionAgent,
) -> IngestResult:
    """接收 TG 端送来的原始图片字节,走完整流水线。

    流程:
        1. 压缩到合理尺寸/质量
        2. 对压缩后字节计算 sha256,作去重键
        3. 查库:命中则复用,不命中则落盘+调VL+入库
        4. 不管是否去重命中,都要记录一条 message_images(这条消息确实引用了这张图)
        5. 返回一个可注入对话的文本块

    VL 失败时降级:图照样落盘入库,描述留空,上层对话注入"[视觉识别未完成]"提示。
    这样保证用户发图永远有反馈,不会因视觉服务宕机而整条消息静默。
    """
    # 1. 压缩
    compressed = compress_image(raw_bytes)
    sha = compute_sha256(compressed.data)

    # 2. 去重查询
    existing = media_client.find_image_by_sha256(sha)
    vision_failed = False

    if existing is not None:
        logger.info("image dedup hit: sha256=%s id=%s", sha[:12], existing.id)
        image = existing
        is_new = False
    else:
        # 3. 新图:落盘
        relative = build_relative_path(
            chat_id=telegram_chat_id,
            sha256_hex=sha,
            extension=compressed.extension,
        )
        absolute = save_bytes_to_uploads(uploads_root, relative, compressed.data)
        logger.info("image saved: %s (%d bytes)", absolute, compressed.size_bytes)

        # 4. 调VL,失败降级
        vl_description: Optional[str] = None
        vl_model: Optional[str] = None
        ocr_text: Optional[str] = None
        try:
            analysis = vision_agent.analyze(
                compressed.data,
                compressed.mime_type,
                user_hint=caption,
            )
            vl_description = analysis.description
            vl_model = analysis.model
            ocr_text = analysis.ocr_text or None  # 空字符串不入库
        except VisionError:
            logger.exception("vision analyze failed, saving image without description")
            vision_failed = True

        # 5. 入库
        image = media_client.insert_image(
            sha256=sha,
            file_path=relative,
            mime_type=compressed.mime_type,
            size_bytes=compressed.size_bytes,
            width=compressed.width,
            height=compressed.height,
            vl_description=vl_description,
            vl_model=vl_model,
            ocr_text=ocr_text,
        )
        is_new = True

    # 6. 挂消息 — 不管新老,都要记一条引用
    message_image = media_client.insert_message_image(
        image_id=image.id,
        telegram_chat_id=telegram_chat_id,
        telegram_message_id=telegram_message_id,
        user_id=user_id,
        caption=caption,
    )

    return IngestResult(
        image=image,
        message_image=message_image,
        is_new=is_new,
        vision_failed=vision_failed,
        context_block=format_context_block(image, caption),
    )
