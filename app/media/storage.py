from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from PIL import Image


logger = logging.getLogger(__name__)

# 压缩目标:最大边1568px,JPEG质量85。这是对VL模型友好且节省token的常见值。
# 参考 Anthropic / OpenAI 视觉文档里对图片预处理的推荐量级。
_MAX_EDGE = 1568
_JPEG_QUALITY = 85

# 保留的透明通道:PNG / WebP。其他一律转JPEG。
_KEEP_ALPHA_FORMATS = {"PNG", "WEBP"}


@dataclass(frozen=True)
class CompressedImage:
    """压缩后的图片,尚未落盘。用于后续计算sha256与保存。"""

    data: bytes
    mime_type: str
    extension: Literal["jpg", "png", "webp"]
    width: int
    height: int

    @property
    def size_bytes(self) -> int:
        return len(self.data)


def compute_sha256(data: bytes) -> str:
    """返回64字符的十六进制sha256,用于字节级去重。"""
    return hashlib.sha256(data).hexdigest()


def compress_image(raw_bytes: bytes) -> CompressedImage:
    """把任意格式的图片字节流压缩到合理大小。

    - 最大边限制为 _MAX_EDGE,短边按比例缩放
    - 有透明通道保留PNG/WebP,否则统一转JPEG
    - EXIF方向信息被应用后丢弃(避免下游解读错误方向)
    """
    img = Image.open(io.BytesIO(raw_bytes))

    # 必须在 exif_transpose 之前 capture 原始格式和 mode
    # 否则 transpose 会把 img.format 清成 None,导致下游格式判断错误
    original_format = (img.format or "JPEG").upper()
    original_mode = img.mode

    # 应用EXIF方向,然后丢弃EXIF
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        logger.debug("EXIF transpose skipped", exc_info=True)

    keep_alpha = original_format in _KEEP_ALPHA_FORMATS and original_mode in ("RGBA", "LA", "P")

    # 等比缩放到最大边
    w, h = img.size
    longest = max(w, h)
    if longest > _MAX_EDGE:
        scale = _MAX_EDGE / longest
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    if keep_alpha:
        # PNG优先(无损),失败退回WebP
        target_format = "PNG"
        ext: Literal["jpg", "png", "webp"] = "png"
        mime = "image/png"
        img.save(buf, format=target_format, optimize=True)
    else:
        # 非透明一律JPEG
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        ext = "jpg"
        mime = "image/jpeg"
        img.save(buf, format="JPEG", quality=_JPEG_QUALITY, optimize=True)

    out_bytes = buf.getvalue()
    return CompressedImage(
        data=out_bytes,
        mime_type=mime,
        extension=ext,
        width=img.size[0],
        height=img.size[1],
    )


def build_relative_path(
    chat_id: int,
    sha256_hex: str,
    extension: str,
    now: datetime | None = None,
) -> str:
    """构造图片在uploads目录下的相对路径。

    格式: {year}/{month}/{chat_id}/{timestamp}_{sha_prefix}.{ext}
    例如:   2026/04/-1001234567890/1729340000_a1b2c3d4.jpg

    按年月分片,避免单目录堆积。chat_id当子目录便于按人/群分类清理。
    """
    now = now or datetime.now(timezone.utc)
    ts = int(now.timestamp())
    sha_prefix = sha256_hex[:8]
    return f"{now.year:04d}/{now.month:02d}/{chat_id}/{ts}_{sha_prefix}.{extension}"


def save_bytes_to_uploads(
    uploads_root: Path,
    relative_path: str,
    data: bytes,
) -> Path:
    """把字节写到 uploads_root/relative_path,自动创建父目录。返回绝对路径。"""
    absolute = uploads_root / relative_path
    absolute.parent.mkdir(parents=True, exist_ok=True)
    absolute.write_bytes(data)
    return absolute
