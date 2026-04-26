"""shizuku_mcp.client — Thin HTTP client to shizuku-api

Reads KAGUYA_SHIZUKU_API_BASE (default http://127.0.0.1:8772) and exposes
small typed-ish methods for the MCP server to call. Keeps the MCP server
process loosely coupled from the FastAPI app: they can run on the same
host or different hosts, only HTTP between them.
"""
from __future__ import annotations

import os
from typing import Any

import httpx


DEFAULT_BASE = "http://127.0.0.1:8772"


class ShizukuClient:
    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self.base = (base_url or os.environ.get("KAGUYA_SHIZUKU_API_BASE", DEFAULT_BASE)).rstrip("/")
        self._http = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._http.close()

    # ── shizuku ────────────────────────────────────────────────────────────
    def list_shizuku(self, limit: int = 20, offset: int = 0, iro: str | None = None) -> list[dict]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if iro is not None:
            params["iro"] = iro
        r = self._http.get(f"{self.base}/api/shizuku", params=params)
        r.raise_for_status()
        return r.json()

    def get_shizuku(self, shizuku_id: int) -> dict:
        r = self._http.get(f"{self.base}/api/shizuku/{shizuku_id}")
        r.raise_for_status()
        return r.json()

    def create_shizuku(self, payload: dict) -> dict:
        r = self._http.post(f"{self.base}/api/shizuku", json=payload)
        r.raise_for_status()
        return r.json()

    # ── yume ───────────────────────────────────────────────────────────────
    def list_yume(self, limit: int = 20, offset: int = 0) -> list[dict]:
        r = self._http.get(f"{self.base}/api/yume", params={"limit": limit, "offset": offset})
        r.raise_for_status()
        return r.json()

    def get_yume(self, yume_id: int) -> dict:
        r = self._http.get(f"{self.base}/api/yume/{yume_id}")
        r.raise_for_status()
        return r.json()

    def get_yume_kakera(self, yume_id: int) -> list[dict]:
        r = self._http.get(f"{self.base}/api/yume/{yume_id}/kakera")
        r.raise_for_status()
        return r.json()

    # ── comment ────────────────────────────────────────────────────────────
    def list_comments(self, target_type: str, target_id: int) -> list[dict]:
        r = self._http.get(
            f"{self.base}/api/comment",
            params={"target_type": target_type, "target_id": target_id},
        )
        r.raise_for_status()
        return r.json()

    def create_comment(self, payload: dict) -> dict:
        r = self._http.post(f"{self.base}/api/comment", json=payload)
        r.raise_for_status()
        return r.json()

    def list_pending_comments(self) -> list[dict]:
        """GET /api/comment/pending — sakuya 留下未被 kaguya 回复的顶层评论."""
        r = self._http.get(f"{self.base}/api/comment/pending")
        r.raise_for_status()
        return r.json()

    def edit_comment(self, comment_id: int, body: str) -> dict:
        """PATCH /api/comment/{id} — 修改 body. 业务规则后端校验 (作者一致 + 未被回复)."""
        r = self._http.patch(f"{self.base}/api/comment/{comment_id}", json={"body": body})
        r.raise_for_status()
        return r.json()

    def delete_comment(self, comment_id: int) -> None:
        """DELETE /api/comment/{id} — 删除评论 (级联删除回复)."""
        r = self._http.delete(f"{self.base}/api/comment/{comment_id}")
        r.raise_for_status()
