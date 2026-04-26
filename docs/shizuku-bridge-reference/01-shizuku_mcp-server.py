"""shizuku_mcp.server — FastMCP entrypoint

Note on package name: this package is `shizuku_mcp`, not `mcp`. The
upstream SDK owns the top-level `mcp` import name, so a local `mcp/`
directory would shadow `mcp.server.fastmcp` and crash on startup.

Exposes a minimal toolset for kaguya (the assistant) to read & write into
shizuku.db over HTTP via the FastAPI service. M1 ships read tools for all
three resources plus write tools where the asymmetry matters:

  shizuku_list / shizuku_get / shizuku_create
  yume_list    / yume_get    / yume_kakera
  comment_list / comment_reply

`comment_reply` is the bridge described in CLAUDE.md §2.2 — sakuya leaves
notes from the web UI, kaguya replies through here from claude.ai.

yume creation (POST /api/yume/trigger) is M2 and not surfaced here.
"""
from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from .client import ShizukuClient


mcp = FastMCP("kaguya-shizuku", host="127.0.0.1", port=8773)
_client = ShizukuClient()


# ── shizuku ────────────────────────────────────────────────────────────────
@mcp.tool()
def shizuku_list(limit: int = 20, offset: int = 0, iro: Optional[str] = None) -> list[dict]:
    """List shizuku (雫) entries, newest first.

    Args:
        limit: page size, 1-200.
        offset: how many entries to skip.
        iro: filter by iro name (one of 月白/绯红/墨黑/枯金/雨灰/若葉/朱殷/藤紫/透明).
    """
    return _client.list_shizuku(limit=limit, offset=offset, iro=iro)


@mcp.tool()
def shizuku_get(shizuku_id: int) -> dict:
    """Read a single shizuku by id, including computed tsuki phase."""
    return _client.get_shizuku(shizuku_id)


@mcp.tool()
def shizuku_create(
    koyomi: str,
    iro: Optional[str] = None,
    aji: Optional[list[str]] = None,
    na: Optional[str] = None,
    za: Optional[str] = None,
    sora: Optional[str] = None,
    ki: Optional[str] = None,
    koe: Optional[str] = None,
) -> dict:
    """Drop a new shizuku (一滴雫を落とす).

    Args:
        koyomi: ISO datetime, e.g. "2026-04-26T22:14:00". Required.
        iro:    one of the 9 iro names. None / "透明" for the silent state.
        aji:    list of 五味 entries (any subset of 甘/辛/酸/苦/咸).
        na:     title.
        za:     location (座).
        sora:   one-line sky description (the only window that looks outward).
        ki:     body text.
        koe:    one-line voice (一句話).
    """
    payload: dict = {"koyomi": koyomi}
    if iro is not None:
        payload["iro"] = iro
    if aji is not None:
        payload["aji"] = aji
    if na is not None:
        payload["na"] = na
    if za is not None:
        payload["za"] = za
    if sora is not None:
        payload["sora"] = sora
    if ki is not None:
        payload["ki"] = ki
    if koe is not None:
        payload["koe"] = koe
    return _client.create_shizuku(payload)


# ── yume ───────────────────────────────────────────────────────────────────
@mcp.tool()
def yume_list(limit: int = 20, offset: int = 0) -> list[dict]:
    """List dreams (夢), most recent first. Empty list if engine has not run yet."""
    return _client.list_yume(limit=limit, offset=offset)


@mcp.tool()
def yume_get(yume_id: int) -> dict:
    """Read a single dream's narrative + metadata."""
    return _client.get_yume(yume_id)


@mcp.tool()
def yume_kakera(yume_id: int) -> list[dict]:
    """Trace the fragments (碎片) that fed a given dream."""
    return _client.get_yume_kakera(yume_id)


# ── comment ────────────────────────────────────────────────────────────────
@mcp.tool()
def comment_list(target_type: str, target_id: int) -> list[dict]:
    """List comments on a shizuku or a yume.

    Args:
        target_type: "shizuku" or "yume".
        target_id:   id of that entry.
    """
    return _client.list_comments(target_type, target_id)


@mcp.tool()
def comment_reply(
    target_type: str,
    target_id: int,
    body: str,
    parent_id: Optional[int] = None,
    author: str = "kaguya",
) -> dict:
    """Leave a comment / reply.

    The default author is "kaguya" because this MCP tool is designed to be
    called from the kaguya side. Pass author="sakuya" only if explicitly
    speaking on sakuya's behalf.

    Nesting is limited to 1 level: parent_id must reference a top-level
    comment (whose own parent_id is NULL), otherwise the API returns 400.
    """
    payload: dict = {
        "target_type": target_type,
        "target_id": target_id,
        "body": body,
        "author": author,
    }
    if parent_id is not None:
        payload["parent_id"] = parent_id
    return _client.create_comment(payload)


@mcp.tool()
def comment_pending() -> list[dict]:
    """List comments awaiting kaguya's reply.

    Returns sakuya's top-level comments that have NO kaguya reply yet.
    Each item carries a target_preview ({na, koyomi/nemuri_end, ...})
    so kaguya can decide which雫 / 梦 to revisit before replying.

    Use this tool first when you start a session — it's your inbox.
    """
    return _client.list_pending_comments()


@mcp.tool()
def comment_edit(comment_id: int, body: str) -> dict:
    """Edit your own comment's body.

    The backend rejects the call if:
      - you try to edit sakuya's comment that already has a kaguya reply
        (don't rewrite history)
      - the comment doesn't exist

    Author / parent / target are immutable — only body can change.
    """
    return _client.edit_comment(comment_id, body)


@mcp.tool()
def comment_delete(comment_id: int) -> dict:
    """Delete a comment. Cascades to any replies under it.

    Use sparingly. Deleting sakuya's comment that you've already replied to
    will also drop your reply.
    """
    _client.delete_comment(comment_id)
    return {"ok": True, "id": comment_id}


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
