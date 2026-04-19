from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImageRecord:
    id: str
    sha256: str
    file_path: str
    mime_type: str
    size_bytes: int
    width: Optional[int]
    height: Optional[int]
    vl_description: Optional[str]
    vl_model: Optional[str]
    ocr_text: Optional[str]
    created_at: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ImageRecord":
        return cls(
            id=row["id"],
            sha256=row["sha256"],
            file_path=row["file_path"],
            mime_type=row["mime_type"],
            size_bytes=row["size_bytes"],
            width=row.get("width"),
            height=row.get("height"),
            vl_description=row.get("vl_description"),
            vl_model=row.get("vl_model"),
            ocr_text=row.get("ocr_text"),
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class MessageImageRecord:
    id: str
    image_id: str
    telegram_chat_id: int
    telegram_message_id: int
    user_id: int
    caption: Optional[str]
    created_at: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "MessageImageRecord":
        return cls(
            id=row["id"],
            image_id=row["image_id"],
            telegram_chat_id=row["telegram_chat_id"],
            telegram_message_id=row["telegram_message_id"],
            user_id=row["user_id"],
            caption=row.get("caption"),
            created_at=row["created_at"],
        )


class MediaClient:
    """kaguya-media Supabase project 的薄客户端,走 PostgREST。

    使用 service_role key 访问,绕过 RLS。仅后端使用,不要泄露到前端。
    封装 images 与 message_images 两张表的 CRUD。
    """

    def __init__(self, url: str, service_key: str, timeout: float = 15.0) -> None:
        if not url or not service_key:
            raise ValueError("MediaClient requires both url and service_key")
        self._base = f"{url.rstrip('/')}/rest/v1"
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MediaClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ---------- images ----------

    def insert_image(
        self,
        *,
        sha256: str,
        file_path: str,
        mime_type: str,
        size_bytes: int,
        width: Optional[int] = None,
        height: Optional[int] = None,
        vl_description: Optional[str] = None,
        vl_model: Optional[str] = None,
        ocr_text: Optional[str] = None,
    ) -> ImageRecord:
        payload = {
            "sha256": sha256,
            "file_path": file_path,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "width": width,
            "height": height,
            "vl_description": vl_description,
            "vl_model": vl_model,
            "ocr_text": ocr_text,
        }
        resp = self._client.post(f"{self._base}/images", json=payload)
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            raise RuntimeError("insert_image returned empty response")
        return ImageRecord.from_row(rows[0])

    def find_image_by_sha256(self, sha256: str) -> Optional[ImageRecord]:
        resp = self._client.get(
            f"{self._base}/images",
            params={"sha256": f"eq.{sha256}", "limit": "1"},
        )
        resp.raise_for_status()
        rows = resp.json()
        return ImageRecord.from_row(rows[0]) if rows else None

    def get_image(self, image_id: str) -> Optional[ImageRecord]:
        resp = self._client.get(
            f"{self._base}/images",
            params={"id": f"eq.{image_id}", "limit": "1"},
        )
        resp.raise_for_status()
        rows = resp.json()
        return ImageRecord.from_row(rows[0]) if rows else None

    def update_image_description(
        self,
        image_id: str,
        *,
        vl_description: Optional[str] = None,
        vl_model: Optional[str] = None,
        ocr_text: Optional[str] = None,
    ) -> Optional[ImageRecord]:
        updates: dict[str, Any] = {}
        if vl_description is not None:
            updates["vl_description"] = vl_description
        if vl_model is not None:
            updates["vl_model"] = vl_model
        if ocr_text is not None:
            updates["ocr_text"] = ocr_text
        if not updates:
            return self.get_image(image_id)
        resp = self._client.patch(
            f"{self._base}/images",
            params={"id": f"eq.{image_id}"},
            json=updates,
        )
        resp.raise_for_status()
        rows = resp.json()
        return ImageRecord.from_row(rows[0]) if rows else None

    def delete_image(self, image_id: str) -> None:
        """删除一条图片记录。message_images 的外键 on delete cascade 会连带清理关联行。"""
        resp = self._client.delete(
            f"{self._base}/images",
            params={"id": f"eq.{image_id}"},
        )
        resp.raise_for_status()

    # ---------- message_images ----------

    def insert_message_image(
        self,
        *,
        image_id: str,
        telegram_chat_id: int,
        telegram_message_id: int,
        user_id: int,
        caption: Optional[str] = None,
    ) -> MessageImageRecord:
        payload = {
            "image_id": image_id,
            "telegram_chat_id": telegram_chat_id,
            "telegram_message_id": telegram_message_id,
            "user_id": user_id,
            "caption": caption,
        }
        resp = self._client.post(f"{self._base}/message_images", json=payload)
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            raise RuntimeError("insert_message_image returned empty response")
        return MessageImageRecord.from_row(rows[0])

    def list_images_for_message(
        self,
        telegram_chat_id: int,
        telegram_message_id: int,
    ) -> list[MessageImageRecord]:
        resp = self._client.get(
            f"{self._base}/message_images",
            params={
                "telegram_chat_id": f"eq.{telegram_chat_id}",
                "telegram_message_id": f"eq.{telegram_message_id}",
                "order": "created_at.asc",
            },
        )
        resp.raise_for_status()
        return [MessageImageRecord.from_row(r) for r in resp.json()]
