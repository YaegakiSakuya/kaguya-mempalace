from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.core.config import Settings
from app.inspector.realtime import realtime_bus
from app.miniapp.auth import issue_session_token, resolve_session_token, verify_init_data, verify_session_token

STATIC_DIR = Path(__file__).parent / "static"


class MiniAppAuthRequest(BaseModel):
    init_data: str


def create_miniapp_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/miniapp", tags=["miniapp"])

    def _verify_session(token: str = Depends(resolve_session_token)) -> dict:
        payload = verify_session_token(settings, token)
        chat_id = str(payload["chat_id"])
        if settings.telegram_allowed_chat_ids and chat_id not in settings.telegram_allowed_chat_ids:
            raise HTTPException(status_code=403, detail="chat is not allowed")
        return payload

    @router.post("/auth")
    async def miniapp_auth(payload: MiniAppAuthRequest):
        verified = verify_init_data(settings, payload.init_data)
        chat_id = verified["chat_id"]
        if settings.telegram_allowed_chat_ids and chat_id not in settings.telegram_allowed_chat_ids:
            raise HTTPException(status_code=403, detail="chat is not allowed")

        token, exp = issue_session_token(settings, chat_id)
        return {
            "token": token,
            "expires_at": exp,
            "expires_in": settings.miniapp_session_ttl_seconds,
            "chat_id": chat_id,
            "user": verified["user"],
        }

    @router.get("/current")
    async def miniapp_current(session: dict = Depends(_verify_session)):
        return realtime_bus.current(chat_id=str(session["chat_id"]))

    @router.get("/history")
    async def miniapp_history(limit: int = Query(default=20, ge=1, le=100), session: dict = Depends(_verify_session)):
        return {"items": realtime_bus.history(chat_id=str(session["chat_id"]), limit=limit)}

    @router.get("/stream")
    async def miniapp_stream(
        request: Request,
        token: str = Depends(resolve_session_token),
    ):
        session = verify_session_token(settings, token)
        chat_id = str(session["chat_id"])
        if settings.telegram_allowed_chat_ids and chat_id not in settings.telegram_allowed_chat_ids:
            raise HTTPException(status_code=403, detail="chat is not allowed")

        async def event_generator():
            last_event_id = 0
            while True:
                if await request.is_disconnected():
                    break

                events = realtime_bus.events_since(last_event_id, chat_id=chat_id)
                if events:
                    for event in events:
                        last_event_id = max(last_event_id, int(event["id"]))
                        payload = json.dumps(event["data"], ensure_ascii=False)
                        yield f"id: {event['id']}\nevent: {event['event']}\ndata: {payload}\n\n"
                else:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    return router


def miniapp_frontend_response() -> FileResponse:
    html = STATIC_DIR / "index.html"
    if not html.exists():
        raise HTTPException(status_code=404, detail="Mini App frontend not found")
    return FileResponse(str(html), media_type="text/html")
