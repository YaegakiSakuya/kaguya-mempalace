"""Telegram Mini App initData HMAC-SHA256 验证。"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse

from fastapi import HTTPException, Request

AUTH_MAX_AGE = 86400  # 24小时


def verify_init_data_raw(init_data: str) -> dict:
    """纯函数版本，接受 initData 字符串，返回 user dict，失败抛 ValueError。"""
    if not init_data:
        raise ValueError("Missing initData")

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("Bot token not configured")

    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", "")
    if not received_hash:
        raise ValueError("Missing hash")

    auth_date_str = parsed.get("auth_date", "0")
    try:
        auth_date = int(auth_date_str)
    except ValueError:
        raise ValueError("Invalid auth_date")

    if time.time() - auth_date > AUTH_MAX_AGE:
        raise ValueError("initData expired")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise ValueError("Invalid signature")

    user_data = {}
    if "user" in parsed:
        try:
            user_data = json.loads(parsed["user"])
        except json.JSONDecodeError:
            pass
    return user_data


async def verify_telegram_init_data(request: Request) -> dict:
    init_data = (
        request.headers.get("X-Telegram-Init-Data")
        or request.query_params.get("initData")
    )
    try:
        return verify_init_data_raw(init_data or "")
    except ValueError as exc:
        detail = str(exc)
        if detail == "Bot token not configured":
            raise HTTPException(status_code=500, detail=detail)
        raise HTTPException(status_code=401, detail=detail)
