from __future__ import annotations

from app.media.client import ImageRecord, MediaClient, MessageImageRecord
from app.media.storage import (
    CompressedImage,
    build_relative_path,
    compress_image,
    compute_sha256,
    save_bytes_to_uploads,
)
from app.media.vision import VisionAgent, VisionAnalysis, VisionError
from app.media.pipeline import IngestResult, format_context_block, ingest_image

__all__ = [
    # Supabase client
    "ImageRecord",
    "MediaClient",
    "MessageImageRecord",
    # 本地存储 & 预处理
    "CompressedImage",
    "build_relative_path",
    "compress_image",
    "compute_sha256",
    "save_bytes_to_uploads",
    # 视觉代理
    "VisionAgent",
    "VisionAnalysis",
    "VisionError",
    # Pipeline
    "IngestResult",
    "format_context_block",
    "ingest_image",
]
