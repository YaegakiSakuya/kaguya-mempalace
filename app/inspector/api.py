"""FastAPI Inspector API — read-only observability endpoints for Kaguya MemPalace."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from app.core.config import Settings
from app.inspector.logger import read_jsonl_tail
from app.miniapp.auth import verify_init_data_raw, verify_telegram_init_data
from app.miniapp.sse import sse_manager

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

# Overview cache TTL in seconds
OVERVIEW_TTL_SECONDS = 15


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def _make_auth_dep(settings: Settings):
    """Return a dependency that validates the bearer token via header only."""
    expected = settings.inspector_token

    async def _verify_token(request: Request) -> None:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer ") and auth[7:] == expected:
            return
        raise HTTPException(status_code=401, detail="Unauthorized")

    return _verify_token


# ---------------------------------------------------------------------------
# MemPalace helpers (cached)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_chroma_client(palace_path: str):
    """Return a cached ChromaDB PersistentClient."""
    import chromadb

    os.environ["MEMPALACE_PALACE_PATH"] = palace_path
    return chromadb.PersistentClient(path=palace_path)


def _get_collection(settings: Settings):
    client = _get_chroma_client(str(settings.palace_path))
    try:
        return client.get_collection("mempalace_drawers")
    except Exception:
        return None


def _get_kg(settings: Settings):
    from mempalace.knowledge_graph import KnowledgeGraph, DEFAULT_KG_PATH

    db_path = Path(DEFAULT_KG_PATH)
    if not db_path.exists():
        return None
    return KnowledgeGraph(db_path=str(db_path))


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_inspector_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Kaguya Inspector", docs_url=None, redoc_url=None)
    auth = _make_auth_dep(settings)

    # Overview cache
    _overview_cache: dict[str, Any] = {"data": None, "ts": 0.0}

    # ----- Frontend -----

    @app.get("/")
    async def serve_frontend():
        html = STATIC_DIR / "index.html"
        if not html.exists():
            raise HTTPException(status_code=404, detail="Frontend not found")
        return FileResponse(str(html), media_type="text/html")

    # ----- Overview -----

    @app.get("/api/overview", dependencies=[Depends(auth)])
    async def overview():
        now = time.monotonic()
        if _overview_cache["data"] is not None and (now - _overview_cache["ts"]) < OVERVIEW_TTL_SECONDS:
            return _overview_cache["data"]

        # Use mempalace tool handlers to count wings/rooms instead of full-collection scan
        drawer_count = 0
        wing_count = 0
        room_count = 0

        try:
            from mempalace.mcp_server import TOOLS

            # Use list_wings to get wing count
            wings_result = _parse_tool_result(TOOLS["mempalace_list_wings"]["handler"]())
            wing_list = wings_result if isinstance(wings_result, list) else wings_result.get("wings", [])
            wing_count = len(wing_list)

            # Count rooms per wing and total drawers via taxonomy
            taxonomy_result = _parse_tool_result(TOOLS["mempalace_get_taxonomy"]["handler"]())
            if isinstance(taxonomy_result, dict):
                for wing_data in (taxonomy_result.get("wings") or taxonomy_result.get("taxonomy") or {}).values() if isinstance(taxonomy_result.get("wings", taxonomy_result.get("taxonomy")), dict) else []:
                    if isinstance(wing_data, dict):
                        room_count += len(wing_data.get("rooms", []))
                    elif isinstance(wing_data, list):
                        room_count += len(wing_data)
        except Exception:
            # Fallback: use collection count for drawer total
            pass

        col = _get_collection(settings)
        if col:
            try:
                drawer_count = col.count()
            except Exception:
                pass

        # Count rooms from taxonomy more robustly if the above didn't work
        if room_count == 0 and wing_count > 0:
            try:
                from mempalace.mcp_server import TOOLS
                for wname in wing_list:
                    w = wname if isinstance(wname, str) else (wname.get("name", "") if isinstance(wname, dict) else str(wname))
                    if w:
                        rooms_result = _parse_tool_result(TOOLS["mempalace_list_rooms"]["handler"](wing=w))
                        rlist = rooms_result if isinstance(rooms_result, list) else rooms_result.get("rooms", [])
                        room_count += len(rlist)
            except Exception:
                pass

        # KG stats
        kg_entity_count = 0
        kg_triple_count = 0
        try:
            from mempalace.mcp_server import TOOLS
            kg_raw = TOOLS["mempalace_kg_stats"]["handler"]()
            kg_stats = _parse_tool_result(kg_raw)
            if isinstance(kg_stats, dict):
                kg_entity_count = kg_stats.get("entities", kg_stats.get("entity_count", 0))
                kg_triple_count = kg_stats.get("triples", kg_stats.get("triple_count", 0))
        except Exception:
            pass

        recent_tools = read_jsonl_tail(settings.logs_dir / "tool_calls.jsonl", 10)
        recent_turns = read_jsonl_tail(settings.logs_dir / "turn_summaries.jsonl", 5)

        # Recent diary entries — handle dict payload from mempalace_diary_read
        diary_entries: list[dict] = []
        try:
            from mempalace.mcp_server import TOOLS
            handler = TOOLS.get("mempalace_diary_read", {}).get("handler")
            if handler:
                raw = handler(agent_name="kaguya", last_n=5)
                diary_entries = _parse_diary_result(raw)
        except Exception:
            pass

        result = {
            "drawers": drawer_count,
            "wings": wing_count,
            "rooms": room_count,
            "kg_entities": kg_entity_count,
            "kg_triples": kg_triple_count,
            "recent_tool_calls": recent_tools,
            "recent_turns": recent_turns,
            "recent_diary": diary_entries,
        }

        _overview_cache["data"] = result
        _overview_cache["ts"] = now
        return result

    # ----- Taxonomy -----

    @app.get("/api/taxonomy", dependencies=[Depends(auth)])
    async def taxonomy():
        try:
            from mempalace.mcp_server import TOOLS
            handler = TOOLS["mempalace_get_taxonomy"]["handler"]
            result = handler()
            return _parse_tool_result(result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # ----- Wings / Rooms -----

    @app.get("/api/wings", dependencies=[Depends(auth)])
    async def list_wings():
        try:
            from mempalace.mcp_server import TOOLS
            handler = TOOLS["mempalace_list_wings"]["handler"]
            result = handler()
            return _parse_tool_result(result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/rooms", dependencies=[Depends(auth)])
    async def list_rooms(wing: str = Query(...)):
        try:
            from mempalace.mcp_server import TOOLS
            handler = TOOLS["mempalace_list_rooms"]["handler"]
            result = handler(wing=wing)
            return _parse_tool_result(result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # ----- Drawers -----

    @app.get("/api/drawers", dependencies=[Depends(auth)])
    async def list_drawers(
        wing: str = Query(default=""),
        room: str = Query(default=""),
        limit: int = Query(default=50, le=200),
        offset: int = Query(default=0, ge=0),
    ):
        col = _get_collection(settings)
        if not col:
            return []

        where: dict[str, Any] = {}
        if wing and room:
            where = {"$and": [{"wing": wing}, {"room": room}]}
        elif wing:
            where = {"wing": wing}
        elif room:
            where = {"room": room}

        try:
            kwargs: dict[str, Any] = {
                "include": ["metadatas", "documents"],
                "limit": limit,
                "offset": offset,
            }
            if where:
                kwargs["where"] = where
            data = col.get(**kwargs)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        ids = data.get("ids") or []
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []

        results = []
        for i in range(len(ids)):
            content = (docs[i] or "") if i < len(docs) else ""
            results.append({
                "id": ids[i],
                "content_preview": content[:200],
                "content_full": content,
                "metadata": metas[i] if i < len(metas) else {},
            })

        return results

    # ----- Search -----

    @app.get("/api/search", dependencies=[Depends(auth)])
    async def search(
        q: str = Query(...),
        limit: int = Query(default=10, le=50),
        wing: str = Query(default=""),
    ):
        col = _get_collection(settings)
        if not col:
            return []

        kwargs: dict[str, Any] = {
            "query_texts": [q],
            "n_results": limit,
            "include": ["metadatas", "documents", "distances"],
        }
        if wing:
            kwargs["where"] = {"wing": wing}

        try:
            results = col.query(**kwargs)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        ids = (results.get("ids") or [[]])[0]
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        dists = (results.get("distances") or [[]])[0]

        items = []
        for i in range(len(ids)):
            items.append({
                "id": ids[i],
                "content_preview": (docs[i] or "")[:200] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else {},
                "distance": dists[i] if i < len(dists) else None,
            })

        return items

    # ----- KG -----

    @app.get("/api/kg/stats", dependencies=[Depends(auth)])
    async def kg_stats():
        try:
            from mempalace.mcp_server import TOOLS
            handler = TOOLS["mempalace_kg_stats"]["handler"]
            result = handler()
            return _parse_tool_result(result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/kg/entities", dependencies=[Depends(auth)])
    async def kg_entities(limit: int = Query(default=100, le=500)):
        kg = _get_kg(settings)
        if not kg:
            return []

        try:
            import sqlite3
            db_path = Path(_get_kg(settings).db_path)
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM entities ORDER BY rowid DESC LIMIT ?", (limit,)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/kg/triples", dependencies=[Depends(auth)])
    async def kg_triples(
        entity: str = Query(...),
        limit: int = Query(default=100, le=500),
    ):
        kg = _get_kg(settings)
        if not kg:
            return []

        try:
            result = kg.query_entity(entity, direction="both")
            parsed = _parse_tool_result(result)
            if isinstance(parsed, list):
                return parsed[:limit]
            return parsed
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/kg/timeline", dependencies=[Depends(auth)])
    async def kg_timeline(entity: str = Query(...)):
        try:
            from mempalace.mcp_server import TOOLS
            handler = TOOLS["mempalace_kg_timeline"]["handler"]
            result = handler(entity=entity)
            return _parse_tool_result(result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # ----- Graph -----

    @app.get("/api/graph/stats", dependencies=[Depends(auth)])
    async def graph_stats():
        try:
            from mempalace.mcp_server import TOOLS
            handler = TOOLS["mempalace_graph_stats"]["handler"]
            result = handler()
            return _parse_tool_result(result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/graph/nodes", dependencies=[Depends(auth)])
    async def graph_nodes():
        col = _get_collection(settings)
        if not col:
            return {"nodes": {}, "edges": []}

        try:
            from mempalace.palace_graph import build_graph
            nodes, edges = build_graph(col)
            return {"nodes": nodes, "edges": edges}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/graph/tunnels", dependencies=[Depends(auth)])
    async def graph_tunnels(
        wing_a: str = Query(...),
        wing_b: str = Query(...),
    ):
        try:
            from mempalace.mcp_server import TOOLS
            handler = TOOLS["mempalace_find_tunnels"]["handler"]
            result = handler(wing_a=wing_a, wing_b=wing_b)
            return _parse_tool_result(result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # ----- Diary -----

    @app.get("/api/diary", dependencies=[Depends(auth)])
    async def diary(
        agent: str = Query(default="kaguya"),
        limit: int = Query(default=20, le=100),
    ):
        try:
            from mempalace.mcp_server import TOOLS
            handler = TOOLS["mempalace_diary_read"]["handler"]
            result = handler(agent_name=agent, last_n=limit)
            return _parse_tool_result(result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # ----- Logs (JSONL) -----

    @app.get("/api/usage", dependencies=[Depends(auth)])
    async def usage(last_n: int = Query(default=50, le=500)):
        return read_jsonl_tail(settings.logs_dir / "token_usage.jsonl", last_n)

    @app.get("/api/tools/calls", dependencies=[Depends(auth)])
    async def tool_calls(last_n: int = Query(default=50, le=500)):
        return read_jsonl_tail(settings.logs_dir / "tool_calls.jsonl", last_n)

    @app.get("/api/turns", dependencies=[Depends(auth)])
    async def turns(last_n: int = Query(default=20, le=200)):
        return read_jsonl_tail(settings.logs_dir / "turn_summaries.jsonl", last_n)

    # ===== Mini App 路由 =====

    # SSE 流（initData 通过 query param 传入，EventSource 不支持自定义 header）
    @app.get("/miniapp/stream")
    async def miniapp_sse_stream(request: Request, initData: str = Query(default="")):
        try:
            verify_init_data_raw(initData)
        except ValueError as exc:
            return JSONResponse(status_code=401, content={"detail": str(exc)})

        queue = await sse_manager.connect()

        async def event_generator():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=30.0)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    if item is None:
                        break
                    yield f"event: {item['event']}\ndata: {item['data']}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                await sse_manager.disconnect(queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 以下路由走 Telegram initData 鉴权
    miniapp_auth = [Depends(verify_telegram_init_data)]

    @app.get("/miniapp/history", dependencies=miniapp_auth)
    async def miniapp_history(limit: int = Query(default=20, le=100)):
        items = read_jsonl_tail(settings.logs_dir / "turn_summaries.jsonl", limit)
        items.reverse()
        return {"items": items}

    @app.get("/miniapp/history/tools", dependencies=miniapp_auth)
    async def miniapp_tool_history(limit: int = Query(default=50, le=200)):
        items = read_jsonl_tail(settings.logs_dir / "tool_calls.jsonl", limit)
        items.reverse()
        return {"items": items}

    @app.get("/miniapp/palace/overview", dependencies=miniapp_auth)
    async def miniapp_palace_overview():
        """复用 overview 的查询逻辑，返回宫殿统计。"""
        return await overview()

    @app.get("/miniapp/palace/wings", dependencies=miniapp_auth)
    async def miniapp_palace_wings():
        """Return wings enriched with per-wing rooms_count and drawers_count."""
        try:
            from mempalace.mcp_server import TOOLS
            wings_raw = _parse_tool_result(TOOLS["mempalace_list_wings"]["handler"]())
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        if isinstance(wings_raw, dict):
            wing_list = wings_raw.get("wings") or list(wings_raw.keys())
        else:
            wing_list = wings_raw or []

        names: list[str] = []
        for w in wing_list:
            if isinstance(w, str):
                names.append(w)
            elif isinstance(w, dict):
                n = w.get("name") or w.get("wing")
                if n:
                    names.append(n)

        col = _get_collection(settings)

        enriched: list[dict[str, Any]] = []
        for name in names:
            rooms_count = 0
            drawers_count = 0
            try:
                from mempalace.mcp_server import TOOLS
                rooms_raw = _parse_tool_result(TOOLS["mempalace_list_rooms"]["handler"](wing=name))
                if isinstance(rooms_raw, list):
                    rooms_count = len(rooms_raw)
                elif isinstance(rooms_raw, dict):
                    rlist = rooms_raw.get("rooms")
                    if isinstance(rlist, (list, dict)):
                        rooms_count = len(rlist)
            except Exception:
                pass
            if col is not None:
                try:
                    data = col.get(where={"wing": name}, include=[])
                    drawers_count = len(data.get("ids") or [])
                except Exception:
                    pass
            enriched.append({
                "name": name,
                "rooms_count": rooms_count,
                "drawers_count": drawers_count,
            })

        return {"wings": enriched}

    @app.get("/miniapp/palace/search", dependencies=miniapp_auth)
    async def miniapp_palace_search(
        q: str = Query(...),
        limit: int = Query(default=10, le=50),
    ):
        return await search(q=q, limit=limit, wing="")

    @app.get("/miniapp/palace/wing-activity", dependencies=miniapp_auth)
    async def miniapp_palace_wing_activity(days: int = Query(default=7, ge=1, le=30)):
        """Aggregate mempalace_add_drawer calls in the last N days, grouped by wing."""
        from datetime import datetime, timedelta, timezone

        items = read_jsonl_tail(settings.logs_dir / "tool_calls.jsonl", 2000)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        counts: dict[str, int] = {}
        for it in items:
            if it.get("tool_name") != "mempalace_add_drawer":
                continue
            if it.get("success") is False:
                continue
            ts_str = it.get("ts") or it.get("timestamp")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            except Exception:
                continue
            if ts < cutoff:
                continue
            args = (
                it.get("arguments_summary")
                or it.get("arguments")
                or it.get("args")
                or {}
            )
            wing = args.get("wing") if isinstance(args, dict) else None
            if not wing:
                continue
            counts[wing] = counts.get(wing, 0) + 1

        activity = [{"wing": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]
        return {"days": days, "activity": activity}

    @app.get("/miniapp/palace/kg/timeline", dependencies=miniapp_auth)
    async def miniapp_palace_kg_timeline(limit: int = Query(default=5, ge=1, le=50)):
        try:
            from mempalace.mcp_server import TOOLS
            handler = TOOLS["mempalace_kg_timeline"]["handler"]
            raw = handler()
            parsed = _parse_tool_result(raw)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        entities: list[dict[str, Any]] = []
        triples: list[dict[str, Any]] = []

        if isinstance(parsed, dict):
            ent = parsed.get("entities") or parsed.get("new_entities") or []
            trp = parsed.get("triples") or parsed.get("facts") or parsed.get("new_facts") or []
            if isinstance(ent, list):
                entities = ent
            if isinstance(trp, list):
                triples = trp
        elif isinstance(parsed, list):
            triples = parsed

        return {
            "entities": entities[:limit],
            "triples": triples[:limit],
        }

    @app.get("/miniapp/palace/rooms", dependencies=miniapp_auth)
    async def miniapp_palace_rooms(wing: str = Query(...)):
        return await list_rooms(wing=wing)

    @app.get("/miniapp/palace/drawers", dependencies=miniapp_auth)
    async def miniapp_palace_drawers(
        wing: str = Query(default=""),
        room: str = Query(default=""),
        limit: int = Query(default=20, le=100),
        offset: int = Query(default=0, ge=0),
    ):
        return await list_drawers(wing=wing, room=room, limit=limit, offset=offset)

    @app.get("/miniapp/palace/diary", dependencies=miniapp_auth)
    async def miniapp_palace_diary(limit: int = Query(default=10, le=50)):
        return await diary(agent="kaguya", limit=limit)

    @app.get("/miniapp/palace/kg", dependencies=miniapp_auth)
    async def miniapp_palace_kg():
        return await kg_stats()

    from app.miniapp.config_routes import build_config_router
    app.include_router(build_config_router(settings))

    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_tool_result(result: Any) -> Any:
    """Parse a MemPalace tool result into JSON-serializable form."""
    if isinstance(result, (dict, list)):
        return result
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"text": result}
    return {"value": str(result)}


def _parse_diary_result(raw: Any) -> list[dict]:
    """Parse mempalace_diary_read output into a list of diary entry dicts.

    The handler may return a dict with an 'entries' key, a list, a JSON string,
    or plain text.
    """
    if isinstance(raw, dict):
        # e.g. {"entries": [...], "count": 5}
        entries = raw.get("entries", raw.get("diary", []))
        if isinstance(entries, list):
            return entries
        return [raw]
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            return _parse_diary_result(parsed)
        except json.JSONDecodeError:
            return [{"text": raw}]
    return []
