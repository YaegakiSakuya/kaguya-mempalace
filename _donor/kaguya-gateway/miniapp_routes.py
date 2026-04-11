"""Mini App REST API 路由（Session 2）。"""
from __future__ import annotations

import asyncio
from hashlib import sha256
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from api.miniapp_auth import verify_telegram_init_data
from api.sse_manager import sse_manager
from database.config_store import get_config_store
from database.protocol_store import get_protocol_store
from database.supabase_client import get_db
from gateway.telegram_buffer import get_telegram_buffer
import config


router = APIRouter(prefix="/api/miniapp", tags=["miniapp"], dependencies=[Depends(verify_telegram_init_data)])

SECRET_MASK_RE = re.compile(r"^.{6}\.\.\..{4}$")

LAYER_LABELS = {
    "base": "基底层",
    "daily": "日常对话",
    "deep": "深度交流",
    "emotion": "情绪响应",
    "work": "工作",
    "creative": "创作",
    "general": "通用",
}

RUNTIME_CONFIG_CATEGORIES = {
    "runtime",
    "telegram",
    "model",
    "memory",
    "memory_pipeline",
    "worker",
    "queue",
    "scheduler",
    "threshold",
    "feature",
}

RUNTIME_CONFIG_KEYS = {
    "message_mode",
    "buffer_seconds",
    "max_short_replies",
    "memory_window_size",
    "topic_card_enabled",
    "rolling_summary_enabled",
    "memory_recall_enabled",
    "memory_jobs_enabled",
    "worker_poll_interval_sec",
    "embed_enabled",
    "emotion_enabled",
    "extract_memory_enabled",
}

NON_RUNTIME_CONFIG_KEYS = {
    "prompt.persona",
    "system_prompt",
    "persona",
}


class ConfigUpdateRequest(BaseModel):
    value: Any


class ConfigBatchRequest(BaseModel):
    updates: Dict[str, Any]


class ProtocolCreateRequest(BaseModel):
    name: str
    layer: str = "general"
    content: str
    priority: int = 0
    description: str = ""
    is_active: bool = True
    is_mandatory: bool = False


class ProtocolUpdateRequest(BaseModel):
    name: Optional[str] = None
    layer: Optional[str] = None
    content: Optional[str] = None
    priority: Optional[int] = None
    description: Optional[str] = None


class ProtocolToggleRequest(BaseModel):
    is_active: Optional[bool] = None


class ProtocolReorderItem(BaseModel):
    id: str
    priority: int


class ProtocolReorderRequest(BaseModel):
    items: List[ProtocolReorderItem]


class MemoryUpdateRequest(BaseModel):
    content: str


class SummaryUpdateRequest(BaseModel):
    summary: str


class TopicCardUpdateRequest(BaseModel):
    title: str
    card_text: str
    open_loops: List[str]
    subject_axes: Optional[Dict[str, str]] = None
    time_anchors: Optional[List[str]] = None
    ore_refs: Optional[List[str]] = None
    era_ref: Optional[str] = None
    updated_from: Optional[List[str]] = None
    card_state: Optional[str] = None


class ModeSwitchRequest(BaseModel):
    mode: str = Field(pattern="^(short|long)$")


def _mask_secret(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if len(value) < 10:
        return "******"
    return f"{value[:6]}...{value[-4:]}"


def _is_mask_unchanged(new_value: Any, current_value: Any) -> bool:
    if not isinstance(new_value, str) or not isinstance(current_value, str):
        return False
    if not SECRET_MASK_RE.match(new_value):
        return False
    return new_value == _mask_secret(current_value)


def _pagination(page: int, limit: int, total: int) -> Dict[str, Any]:
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "has_more": page * limit < total,
    }


def _sanitize_config_row(row: Dict[str, Any]) -> Dict[str, Any]:
    value = row.get("value")
    if row.get("value_type") == "secret":
        value = _mask_secret(value)
    key = row.get("key") or ""
    category = (row.get("category") or "").strip().lower()
    is_runtime_param = category in RUNTIME_CONFIG_CATEGORIES or key in RUNTIME_CONFIG_KEYS
    if key in NON_RUNTIME_CONFIG_KEYS:
        is_runtime_param = False
    return {
        "key": row.get("key"),
        "value": value,
        "category": row.get("category"),
        "label": row.get("label"),
        "description": row.get("description"),
        "value_type": row.get("value_type"),
        "is_runtime_param": is_runtime_param,
        "is_primary_source": False,
        "updated_at": row.get("updated_at"),
    }


def _normalize_content(content: str) -> str:
    return " ".join((content or "").strip().split())


@router.get("/config")
async def get_configs() -> Dict[str, Any]:
    store = get_config_store()
    if store is None:
        raise HTTPException(status_code=503, detail="ConfigStore not initialized")
    rows = [_sanitize_config_row(row) for row in store.get_all_meta()]
    rows.sort(key=lambda x: x["key"] or "")
    return {"configs": rows}


@router.get("/config/category/{cat}")
async def get_configs_by_category(cat: str) -> Dict[str, Any]:
    store = get_config_store()
    if store is None:
        raise HTTPException(status_code=503, detail="ConfigStore not initialized")
    rows = [_sanitize_config_row(row) for row in store.get_by_category(cat)]
    rows.sort(key=lambda x: x["key"] or "")
    return {"configs": rows}


@router.put("/config/batch")
async def update_config_batch(payload: ConfigBatchRequest) -> Dict[str, Any]:
    store = get_config_store()
    if store is None:
        raise HTTPException(status_code=503, detail="ConfigStore not initialized")

    updates = payload.updates or {}
    if not updates:
        return {"updated_count": 0, "skipped_count": 0, "configs": []}

    metas = {k: store.get_meta(k) for k in updates.keys()}
    missing = [k for k, v in metas.items() if not v]
    if missing:
        raise HTTPException(status_code=404, detail=f"config key not found: {missing[0]}")

    filtered: Dict[str, Any] = {}
    skipped = 0
    for key, value in updates.items():
        meta = metas[key]
        if meta.get("value_type") == "secret" and _is_mask_unchanged(value, meta.get("value")):
            skipped += 1
            continue
        filtered[key] = value

    updated_rows = await store.update_batch(filtered) if filtered else []
    sanitized = [_sanitize_config_row(row) for row in updated_rows]
    return {"updated_count": len(updated_rows), "skipped_count": skipped, "configs": sanitized}


@router.put("/config/{key}")
async def update_config(key: str, payload: ConfigUpdateRequest) -> Dict[str, Any]:
    store = get_config_store()
    if store is None:
        raise HTTPException(status_code=503, detail="ConfigStore not initialized")

    current = store.get_meta(key)
    if not current:
        raise HTTPException(status_code=404, detail="config key not found")

    if current.get("value_type") == "secret" and _is_mask_unchanged(payload.value, current.get("value")):
        return {"updated": False, "reason": "masked_value_unchanged", "config": _sanitize_config_row(current)}

    updated = await store.update(key, payload.value)
    if not updated:
        raise HTTPException(status_code=500, detail="failed to update config")
    return {"updated": True, "config": _sanitize_config_row(updated)}


@router.post("/config/reload")
async def reload_configs() -> Dict[str, Any]:
    store = get_config_store()
    if store is None:
        raise HTTPException(status_code=503, detail="ConfigStore not initialized")
    await store.reload()
    return {"ok": True, "reloaded_at": store._loaded_at.isoformat() if store._loaded_at else None}


@router.get("/protocols")
async def get_protocols() -> Dict[str, Any]:
    protocol_store = get_protocol_store()
    if protocol_store is None:
        raise HTTPException(status_code=503, detail="ProtocolStore not initialized")
    protocols = await protocol_store.get_all()

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in protocols:
        layer = item.get("layer", "general")
        grouped.setdefault(layer, []).append(item)

    groups = []
    for layer, items in grouped.items():
        items.sort(key=lambda x: (-(x.get("priority") or 0), x.get("created_at") or ""))
        groups.append({"layer": layer, "label": LAYER_LABELS.get(layer, layer), "protocols": items})

    groups.sort(key=lambda x: x["layer"])
    return {"groups": groups}


@router.post("/protocols")
async def create_protocol(payload: ProtocolCreateRequest) -> Dict[str, Any]:
    protocol_store = get_protocol_store()
    if protocol_store is None:
        raise HTTPException(status_code=503, detail="ProtocolStore not initialized")
    item = await protocol_store.create(payload.model_dump())
    return {"created": True, "item": item}


@router.put("/protocols/reorder")
async def reorder_protocols(payload: ProtocolReorderRequest) -> Dict[str, Any]:
    protocol_store = get_protocol_store()
    if protocol_store is None:
        raise HTTPException(status_code=503, detail="ProtocolStore not initialized")
    items = [{"id": i.id, "priority": i.priority} for i in payload.items]
    updated = await protocol_store.reorder(items)
    return {
        "updated_count": len(updated),
        "items": [{"id": row.get("id"), "priority": row.get("priority")} for row in updated],
    }


@router.put("/protocols/{protocol_id}")
async def update_protocol(protocol_id: str, payload: ProtocolUpdateRequest) -> Dict[str, Any]:
    protocol_store = get_protocol_store()
    if protocol_store is None:
        raise HTTPException(status_code=503, detail="ProtocolStore not initialized")
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    item = await protocol_store.update(protocol_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="protocol not found")
    return {"updated": True, "item": item}


@router.delete("/protocols/{protocol_id}")
async def delete_protocol(protocol_id: str) -> Dict[str, Any]:
    protocol_store = get_protocol_store()
    if protocol_store is None:
        raise HTTPException(status_code=503, detail="ProtocolStore not initialized")
    try:
        deleted = await protocol_store.delete(protocol_id)
    except PermissionError:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "PROTOCOL_MANDATORY", "message": "mandatory protocol cannot be deleted"}},
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="protocol not found")
    return {"deleted": True, "id": protocol_id}


@router.put("/protocols/{protocol_id}/toggle")
async def toggle_protocol(protocol_id: str, payload: ProtocolToggleRequest) -> Dict[str, Any]:
    protocol_store = get_protocol_store()
    if protocol_store is None:
        raise HTTPException(status_code=503, detail="ProtocolStore not initialized")
    try:
        if payload.is_active is None:
            item = await protocol_store.toggle(protocol_id)
        else:
            item = await protocol_store.set_active(protocol_id, payload.is_active)
    except PermissionError:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "PROTOCOL_MANDATORY", "message": "mandatory protocol cannot be disabled"}},
        )
    if not item:
        raise HTTPException(status_code=404, detail="protocol not found")
    return {"updated": True, "item": item}


@router.get("/memories")
async def list_memories(
    search: Optional[str] = None,
    category: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    result = await get_db().list_memories(page=page, limit=limit, search=search, category=category, archived=False)
    return {"items": result["items"], "pagination": _pagination(page, limit, result["total"])}


@router.get("/memories/archived")
async def list_archived_memories(
    search: Optional[str] = None,
    category: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    result = await get_db().list_memories(page=page, limit=limit, search=search, category=category, archived=True)
    return {"items": result["items"], "pagination": _pagination(page, limit, result["total"])}


@router.get("/memories/stats")
async def memories_stats() -> Dict[str, Any]:
    stats = await get_db().get_memory_stats_overview()
    by_category = [{"category": k, "count": v} for k, v in sorted(stats["by_category"].items())]
    return {
        "total": stats["total"],
        "active": stats["active"],
        "archived": stats["archived"],
        "by_category": by_category,
        "new_last_7_days": stats["new_last_7_days"],
    }


@router.get("/memories/{memory_id}")
async def get_memory(memory_id: str) -> Dict[str, Any]:
    item = await get_db().get_memory_by_id(memory_id)
    if not item:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"item": item}


@router.put("/memories/{memory_id}")
async def update_memory(memory_id: str, payload: MemoryUpdateRequest) -> Dict[str, Any]:
    db = get_db()
    item = await db.update_memory_content(memory_id, payload.content)
    if not item:
        raise HTTPException(status_code=404, detail="memory not found")

    normalized = _normalize_content(payload.content)
    content_hash = sha256(normalized.encode("utf-8")).hexdigest()[:16]
    idempotency_key = f"manual:{memory_id}:embed:{content_hash}:v1"
    jobs = await db.enqueue_jobs([
        {
            "job_type": "embed",
            "turn_unit_id": None,
            "job_class": "heavy",
            "idempotency_key": idempotency_key,
            "payload_json": {"memory_id": str(memory_id), "source": "manual_edit", "content_hash": content_hash},
        }
    ])

    return {
        "updated": True,
        "reindexing": True,
        "job": {"job_type": "embed", "source": "manual_edit", "idempotency_key": idempotency_key},
        "item": item,
        "job_count": len(jobs or []),
    }


@router.delete("/memories/{memory_id}")
async def soft_delete_memory(memory_id: str) -> Dict[str, Any]:
    item = await get_db().soft_delete_memory(memory_id)
    if not item:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"deleted": True, "soft": True, "id": memory_id}


@router.post("/memories/{memory_id}/restore")
async def restore_memory(memory_id: str) -> Dict[str, Any]:
    existing = await get_db().get_memory_by_id(memory_id)
    if not existing:
        raise HTTPException(status_code=404, detail="memory not found")
    await get_db().restore_memory(memory_id)
    return {"restored": True, "id": memory_id}


@router.delete("/memories/{memory_id}/permanent")
async def permanent_delete_memory(memory_id: str) -> Dict[str, Any]:
    existing = await get_db().get_memory_by_id(memory_id)
    if not existing:
        raise HTTPException(status_code=404, detail="memory not found")
    if not existing.get("is_archived"):
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "MEMORY_NOT_ARCHIVED", "message": "memory must be archived before permanent delete"}},
        )
    await get_db().permanent_delete_memory(memory_id)
    return {"deleted": True, "permanent": True, "id": memory_id}


@router.get("/summaries")
async def list_summaries(
    session_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    result = await get_db().list_summaries(page=page, limit=limit, session_id=session_id)
    return {"items": result["items"], "pagination": _pagination(page, limit, result["total"])}


@router.get("/topic-cards")
async def list_topic_cards(
    session_id: str = "default",
    status: str = Query("all", pattern="^(active|archived|all)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    result = await get_db().list_topic_cards(page=page, limit=limit, session_id=session_id, status=status)
    items = []
    for row in result["items"]:
        open_loops = row.get("open_loops")
        open_loops_count = len(open_loops) if isinstance(open_loops, list) else 0
        items.append(
            {
                "id": row.get("id"),
                "session_id": row.get("session_id"),
                "title": row.get("title"),
                "status": row.get("status"),
                "first_turn": row.get("first_turn"),
                "last_turn": row.get("last_turn"),
                "updated_at": row.get("updated_at"),
                "created_at": row.get("created_at"),
                "open_loops_count": open_loops_count,
                "has_subject_axes": bool((row.get("subject_axes") or {}).get("we_side") or (row.get("subject_axes") or {}).get("sakuya_side") or (row.get("subject_axes") or {}).get("kaguya_side")),
                "time_anchor_count": len(row.get("time_anchors") or []) if isinstance(row.get("time_anchors"), list) else 0,
                "ore_refs_count": len(row.get("ore_refs") or []) if isinstance(row.get("ore_refs"), list) else 0,
            }
        )
    return {"items": items, "pagination": _pagination(page, limit, result["total"]), "status": result["status"]}


@router.get("/topic-cards/{card_id}")
async def get_topic_card_detail(card_id: str) -> Dict[str, Any]:
    item = await get_db().get_topic_card_by_id(card_id)
    if not item:
        raise HTTPException(status_code=404, detail="topic card not found")
    return {"item": item}


@router.put("/topic-cards/{card_id}")
async def update_topic_card_detail(card_id: str, payload: TopicCardUpdateRequest) -> Dict[str, Any]:
    db = get_db()
    existing = await db.get_topic_card_by_id(card_id)
    if not existing:
        raise HTTPException(status_code=404, detail="topic card not found")

    open_loops = [str(item).strip() for item in (payload.open_loops or []) if str(item).strip()]
    item = await db.update_topic_card_manual(
        card_id=card_id,
        title=payload.title,
        card_text=payload.card_text,
        open_loops=open_loops,
        subject_axes=payload.subject_axes,
        time_anchors=payload.time_anchors,
        ore_refs=payload.ore_refs,
        era_ref=payload.era_ref,
        updated_from=payload.updated_from,
        card_state=payload.card_state,
    )
    if not item:
        raise HTTPException(status_code=500, detail="failed to update topic card")
    return {"updated": True, "item": item}


@router.get("/jobs/overview")
async def jobs_overview(window_hours: int = Query(24, ge=1, le=336)) -> Dict[str, Any]:
    return await get_db().get_memory_jobs_overview(window_hours=window_hours)


@router.get("/jobs/failed")
async def list_failed_jobs(
    job_type: Optional[str] = None,
    hours: int = Query(168, ge=1, le=720),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    result = await get_db().list_failed_memory_jobs(page=page, limit=limit, hours=hours, job_type=job_type)
    return {"items": result["items"], "pagination": _pagination(page, limit, result["total"]), "hours": result["hours"]}


@router.get("/summaries/{summary_id}")
async def get_summary(summary_id: str) -> Dict[str, Any]:
    item = await get_db().get_summary_by_id(summary_id)
    if not item:
        raise HTTPException(status_code=404, detail="summary not found")
    return {"item": item}


@router.put("/summaries/{summary_id}")
async def update_summary(summary_id: str, payload: SummaryUpdateRequest) -> Dict[str, Any]:
    if not payload.summary.strip():
        raise HTTPException(status_code=422, detail="summary cannot be empty")
    item = await get_db().update_summary(summary_id, payload.summary)
    if not item:
        raise HTTPException(status_code=404, detail="summary not found")
    return {"updated": True, "item": item}


@router.get("/messages")
async def list_messages(
    session_id: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    result = await get_db().list_messages(page=page, limit=limit, session_id=session_id, search=search)
    return {"items": result["items"], "pagination": _pagination(page, limit, result["total"])}


@router.get("/messages/sessions")
async def message_sessions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    result = await get_db().list_message_sessions(page=page, limit=limit)
    return {"items": result["items"], "pagination": _pagination(page, limit, result["total"])}




@router.get("/stream/current")
async def stream_current(request: Request):
    """SSE 端点：实时推送当前消息处理状态。"""
    connection_id, queue = await sse_manager.connect()

    async def event_generator():
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=20)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                if item is None:
                    break
                yield f"event: {item['event']}\ndata: {item['data']}\n\n"
        except asyncio.CancelledError:
            return
        finally:
            await sse_manager.disconnect(connection_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.get("/cot/history")
async def cot_history(
    session_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    result = await get_db().list_cot_history(page=page, limit=limit, session_id=session_id)
    items = []
    for row in result["items"]:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        items.append(
            {
                "assistant_message_id": row.get("id"),
                "session_id": row.get("session_id"),
                "turn_number": row.get("turn_number"),
                "cot": metadata.get("cot"),
                "reply_text": row.get("content"),
                "input_tokens": metadata.get("input_tokens"),
                "output_tokens": metadata.get("output_tokens"),
                "thinking_ms": metadata.get("thinking_ms"),
                "replying_ms": metadata.get("replying_ms"),
                "elapsed_ms": metadata.get("elapsed_ms"),
                "model": metadata.get("model"),
                "processing": metadata.get("processing", {}),
                "memory_intent": metadata.get("memory_intent", {}),
                "created_at": row.get("created_at"),
            }
        )
    return {"items": items, "pagination": _pagination(page, limit, result["total"])}


@router.get("/cot/{turn_id}")
async def cot_detail(turn_id: str) -> Dict[str, Any]:
    row = await get_db().get_cot_by_assistant_message_id(turn_id)
    if not row:
        raise HTTPException(status_code=404, detail="cot not found")
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    return {
        "item": {
            "assistant_message_id": row.get("id"),
            "session_id": row.get("session_id"),
            "turn_number": row.get("turn_number"),
            "cot": metadata.get("cot"),
            "reply_text": row.get("content"),
            "input_tokens": metadata.get("input_tokens"),
            "output_tokens": metadata.get("output_tokens"),
            "thinking_ms": metadata.get("thinking_ms"),
            "replying_ms": metadata.get("replying_ms"),
            "elapsed_ms": metadata.get("elapsed_ms"),
            "model": metadata.get("model"),
            "processing": metadata.get("processing", {}),
            "memory_intent": metadata.get("memory_intent", {}),
            "created_at": row.get("created_at"),
        }
    }


@router.put("/mode/switch")
async def switch_mode(payload: ModeSwitchRequest) -> Dict[str, Any]:
    store = get_config_store()
    if store is None:
        raise HTTPException(status_code=503, detail="ConfigStore not initialized")

    previous_mode = store.get("message_mode", "short")
    await store.update("message_mode", payload.mode)
    mode = store.get("message_mode", "short")
    if previous_mode == "short" and mode == "long":
        asyncio.create_task(get_telegram_buffer().flush_all())
    buffer_seconds = int(store.get("buffer_seconds", 15))
    max_short_replies = int(store.get("max_short_replies", 3))
    return {
        "updated": True,
        "mode": mode,
        "buffer_seconds": buffer_seconds,
        "max_short_replies": max_short_replies,
    }


@router.get("/mode/current")
async def current_mode() -> Dict[str, Any]:
    store = get_config_store()
    if store is None:
        raise HTTPException(status_code=503, detail="ConfigStore not initialized")
    return {
        "mode": store.get("message_mode", "short"),
        "buffer_seconds": int(store.get("buffer_seconds", 15)),
        "max_short_replies": int(store.get("max_short_replies", 3)),
    }
