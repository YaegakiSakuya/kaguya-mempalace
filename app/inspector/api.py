"""FastAPI Inspector API — read-only observability endpoints for Kaguya MemPalace."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import Settings
from app.inspector.logger import read_jsonl_tail

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def _make_auth_dep(settings: Settings):
    """Return a dependency that validates the bearer token or query param."""
    expected = settings.inspector_token

    async def _verify_token(request: Request) -> None:
        # Check Authorization header
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer ") and auth[7:] == expected:
            return
        # Check query param
        if request.query_params.get("token") == expected:
            return
        raise HTTPException(status_code=401, detail="Unauthorized")

    return _verify_token


# ---------------------------------------------------------------------------
# MemPalace helpers (lazy, per-request)
# ---------------------------------------------------------------------------

def _get_collection(settings: Settings):
    import chromadb

    os.environ["MEMPALACE_PALACE_PATH"] = str(settings.palace_path)
    client = chromadb.PersistentClient(path=str(settings.palace_path))
    try:
        return client.get_collection("mempalace_drawers")
    except Exception:
        return None


def _get_kg(settings: Settings):
    from mempalace.knowledge_graph import KnowledgeGraph

    db_path = settings.palace_path / "knowledge_graph.sqlite3"
    if not db_path.exists():
        return None
    return KnowledgeGraph(db_path=str(db_path))


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_inspector_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Kaguya Inspector", docs_url=None, redoc_url=None)
    auth = _make_auth_dep(settings)

    # ----- Frontend -----

    @app.get("/")
    async def serve_frontend(token: str = Query(default="")):
        html = STATIC_DIR / "index.html"
        if not html.exists():
            raise HTTPException(status_code=404, detail="Frontend not found")
        return FileResponse(str(html), media_type="text/html")

    # ----- Overview -----

    @app.get("/api/overview", dependencies=[Depends(auth)])
    async def overview():
        col = _get_collection(settings)
        kg = _get_kg(settings)

        drawer_count = 0
        wings: set[str] = set()
        rooms: set[str] = set()

        if col:
            try:
                all_meta = col.get(include=["metadatas"])
                metas = all_meta.get("metadatas") or []
                drawer_count = len(metas)
                for m in metas:
                    if m.get("wing"):
                        wings.add(m["wing"])
                    if m.get("room"):
                        rooms.add(m["room"])
            except Exception:
                pass

        kg_entity_count = 0
        kg_triple_count = 0
        if kg:
            try:
                stats = kg.stats()
                if isinstance(stats, dict):
                    kg_entity_count = stats.get("entities", 0)
                    kg_triple_count = stats.get("triples", 0)
                elif isinstance(stats, str):
                    s = json.loads(stats)
                    kg_entity_count = s.get("entities", 0)
                    kg_triple_count = s.get("triples", 0)
            except Exception:
                pass

        recent_tools = read_jsonl_tail(settings.logs_dir / "tool_calls.jsonl", 10)
        recent_turns = read_jsonl_tail(settings.logs_dir / "turn_summaries.jsonl", 5)

        # Recent diary entries
        diary_entries: list[dict] = []
        try:
            from mempalace.mcp_server import TOOLS
            handler = TOOLS.get("mempalace_diary_read", {}).get("handler")
            if handler:
                raw = handler(agent_name="kaguya", last_n=5)
                if isinstance(raw, str):
                    diary_entries = json.loads(raw) if raw.startswith("[") else [{"text": raw}]
                elif isinstance(raw, list):
                    diary_entries = raw
        except Exception:
            pass

        return {
            "drawers": drawer_count,
            "wings": len(wings),
            "rooms": len(rooms),
            "kg_entities": kg_entity_count,
            "kg_triples": kg_triple_count,
            "recent_tool_calls": recent_tools,
            "recent_turns": recent_turns,
            "recent_diary": diary_entries,
        }

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
            kwargs: dict[str, Any] = {"include": ["metadatas", "documents"]}
            if where:
                kwargs["where"] = where
            data = col.get(**kwargs)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        ids = data.get("ids") or []
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []

        results = []
        for i in range(min(len(ids), limit)):
            content = (docs[i] or "") if i < len(docs) else ""
            results.append({
                "id": ids[i],
                "content_preview": content[:200],
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
            db_path = settings.palace_path / "knowledge_graph.sqlite3"
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
