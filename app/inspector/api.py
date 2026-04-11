from __future__ import annotations

import json
import sqlite3
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.config import Settings
from app.inspector.logger import read_jsonl_tail

OVERVIEW_TTL_SECONDS = 10.0


class OverviewCache:
    def __init__(self) -> None:
        self.value: dict[str, Any] | None = None
        self.expires_at: float = 0.0


_OVERVIEW_CACHE = OverviewCache()


@lru_cache(maxsize=1)
def _get_chroma_client(palace_path: str):
    import chromadb

    return chromadb.PersistentClient(path=palace_path)


@lru_cache(maxsize=8)
def _get_chroma_collection(palace_path: str, collection_name: str):
    client = _get_chroma_client(palace_path)
    return client.get_collection(name=collection_name)


def _guess_collection_name(settings: Settings) -> str:
    return "drawers"


def _wings_rooms_from_taxonomy(settings: Settings) -> tuple[int, int]:
    try:
        from mempalace.mcp_server import tool_get_taxonomy

        taxonomy = tool_get_taxonomy() or {}
    except Exception:
        return 0, 0

    wings_obj = taxonomy.get("wings") if isinstance(taxonomy, dict) else None
    if not isinstance(wings_obj, list):
        return 0, 0

    wing_count = len(wings_obj)
    room_count = 0
    for wing in wings_obj:
        if isinstance(wing, dict) and isinstance(wing.get("rooms"), list):
            room_count += len(wing["rooms"])
    return wing_count, room_count


def _find_kg_sqlite(settings: Settings) -> Path | None:
    candidates = [
        settings.palace_path / "kg.sqlite3",
        settings.palace_path / "kg.sqlite",
        settings.palace_path / "knowledge_graph.db",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _kg_stats(settings: Settings) -> dict[str, int]:
    db_path = _find_kg_sqlite(settings)
    if not db_path:
        return {"entities": 0, "triples": 0}

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        entities = cur.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        triples = cur.execute("SELECT COUNT(*) FROM triples").fetchone()[0]
    return {"entities": int(entities), "triples": int(triples)}


def _extract_diary_entries(diaries: Any) -> list[dict[str, Any]]:
    # mempalace_diary_read returns a dict payload, not raw list/string.
    if isinstance(diaries, dict):
        for key in ("entries", "items", "results", "data"):
            value = diaries.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []
    if isinstance(diaries, list):
        return [item for item in diaries if isinstance(item, dict)]
    return []


def _auth(settings: Settings, authorization: str | None = Header(default=None)) -> None:
    token = settings.inspector_token
    if not token:
        raise HTTPException(status_code=404, detail="Inspector disabled")
    expected = f"Bearer {token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def create_inspector_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Kaguya MemPalace Inspector", version="1")
    static_path = Path(__file__).parent / "static" / "index.html"

    def require_auth(authorization: str | None = Header(default=None)) -> None:
        _auth(settings, authorization)

    @app.get("/", dependencies=[Depends(require_auth)])
    def inspector_index() -> FileResponse:
        return FileResponse(static_path)

    @app.get("/api/overview", dependencies=[Depends(require_auth)])
    def api_overview() -> dict[str, Any]:
        now = time.monotonic()
        if _OVERVIEW_CACHE.value and _OVERVIEW_CACHE.expires_at > now:
            return _OVERVIEW_CACHE.value

        wing_count, room_count = _wings_rooms_from_taxonomy(settings)

        drawer_count = 0
        try:
            collection = _get_chroma_collection(str(settings.palace_path), _guess_collection_name(settings))
            drawer_count = int(collection.count())
        except Exception:
            drawer_count = 0

        kg = _kg_stats(settings)
        tool_calls = read_jsonl_tail(settings.logs_dir / "tool_calls.jsonl", limit=10)

        diary_entries: list[dict[str, Any]] = []
        try:
            from mempalace.mcp_server import mempalace_diary_read

            diary_payload = mempalace_diary_read(limit=5)
            diary_entries = _extract_diary_entries(diary_payload)[:5]
        except Exception:
            diary_entries = []

        result = {
            "drawers": drawer_count,
            "wings": wing_count,
            "rooms": room_count,
            "kg_entities": kg["entities"],
            "kg_triples": kg["triples"],
            "recent_tool_calls": tool_calls,
            "recent_diary_entries": diary_entries,
        }
        _OVERVIEW_CACHE.value = result
        _OVERVIEW_CACHE.expires_at = now + OVERVIEW_TTL_SECONDS
        return result

    @app.get("/api/taxonomy", dependencies=[Depends(require_auth)])
    def api_taxonomy() -> Any:
        from mempalace.mcp_server import tool_get_taxonomy

        return tool_get_taxonomy()

    @app.get("/api/wings", dependencies=[Depends(require_auth)])
    def api_wings() -> Any:
        from mempalace.mcp_server import tool_list_wings

        return tool_list_wings()

    @app.get("/api/rooms", dependencies=[Depends(require_auth)])
    def api_rooms(wing: str = Query(...)) -> Any:
        from mempalace.mcp_server import tool_list_rooms

        return tool_list_rooms(wing=wing)

    @app.get("/api/drawers", dependencies=[Depends(require_auth)])
    def api_drawers(wing: str = Query(...), room: str = Query(...), limit: int = Query(50, ge=1, le=200)) -> Any:
        collection = _get_chroma_collection(str(settings.palace_path), _guess_collection_name(settings))
        raw = collection.get(where={"wing": wing, "room": room}, limit=limit)
        ids = raw.get("ids", [])
        docs = raw.get("documents", [])
        metadatas = raw.get("metadatas", [])
        rows: list[dict[str, Any]] = []
        for idx, drawer_id in enumerate(ids):
            content = docs[idx] if idx < len(docs) else ""
            metadata = metadatas[idx] if idx < len(metadatas) else {}
            rows.append({"id": drawer_id, "preview": (content or "")[:200], "metadata": metadata or {}})
        return {"items": rows}

    @app.get("/api/logs/tool-calls", dependencies=[Depends(require_auth)])
    def api_tool_logs(limit: int = Query(50, ge=1, le=500)) -> Any:
        return {"items": read_jsonl_tail(settings.logs_dir / "tool_calls.jsonl", limit=limit)}

    @app.get("/api/logs/token-usage", dependencies=[Depends(require_auth)])
    def api_usage_logs(limit: int = Query(50, ge=1, le=500)) -> Any:
        return {"items": read_jsonl_tail(settings.logs_dir / "token_usage.jsonl", limit=limit)}

    @app.get("/api/logs/turns", dependencies=[Depends(require_auth)])
    def api_turn_logs(limit: int = Query(50, ge=1, le=500)) -> Any:
        return {"items": read_jsonl_tail(settings.logs_dir / "turn_summaries.jsonl", limit=limit)}

    return app
