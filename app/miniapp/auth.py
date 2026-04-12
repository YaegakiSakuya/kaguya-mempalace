from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException, Query

from app.core.config import Settings


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def verify_init_data(settings: Settings, init_data: str) -> dict:
    parts = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parts.pop("hash", "")
    if not received_hash:
        raise HTTPException(status_code=401, detail="missing initData hash")

    data_check = "\n".join(f"{k}={v}" for k, v in sorted(parts.items()))
    secret_key = hmac.new(b"WebAppData", settings.telegram_bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(status_code=401, detail="invalid initData signature")

    try:
        auth_date = int(parts.get("auth_date", "0"))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid auth_date") from exc

    now = int(time.time())
    if auth_date <= 0 or (now - auth_date) > settings.miniapp_initdata_max_age_seconds:
        raise HTTPException(status_code=401, detail="expired initData")

    user_raw = parts.get("user", "")
    if not user_raw:
        raise HTTPException(status_code=401, detail="missing user info")
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=401, detail="invalid user payload") from exc

    user_id = str(user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="missing user id")

    return {
        "user": user,
        "user_id": user_id,
        "chat_id": user_id,
        "auth_date": auth_date,
    }


def issue_session_token(settings: Settings, chat_id: str) -> tuple[str, int]:
    now = int(time.time())
    exp = now + settings.miniapp_session_ttl_seconds
    payload = {"chat_id": str(chat_id), "iat": now, "exp": exp}
    payload_raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_part = _b64url(payload_raw)
    sig = hmac.new(
        settings.miniapp_session_secret.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    token = f"{payload_part}.{_b64url(sig)}"
    return token, exp


def verify_session_token(settings: Settings, token: str) -> dict:
    try:
        payload_part, sig_part = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid session token format") from exc

    expected_sig = hmac.new(
        settings.miniapp_session_secret.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    try:
        provided_sig = _b64url_decode(sig_part)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="invalid session token signature") from exc
    if not hmac.compare_digest(expected_sig, provided_sig):
        raise HTTPException(status_code=401, detail="invalid session token signature")

    try:
        payload = json.loads(_b64url_decode(payload_part))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="invalid session payload") from exc

    now = int(time.time())
    exp = int(payload.get("exp") or 0)
    if exp <= now:
        raise HTTPException(status_code=401, detail="session expired")

    chat_id = str(payload.get("chat_id") or "")
    if not chat_id:
        raise HTTPException(status_code=401, detail="missing chat_id in session")

    return payload


def extract_bearer_token(authorization: str | None) -> str:
    auth = (authorization or "").strip()
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return ""


def resolve_session_token(authorization: str | None = Header(default=None), token: str = Query(default="")) -> str:
    candidate = extract_bearer_token(authorization) or token.strip()
    if not candidate:
        raise HTTPException(status_code=401, detail="missing session token")
    return candidate
