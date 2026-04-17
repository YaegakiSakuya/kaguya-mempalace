"""Mini-app routes for managing the runtime LLM configuration overlay.

All routes live under ``/miniapp/config/*``. They combine Telegram Mini App
``initData`` signature verification (``verify_telegram_init_data``) with an
explicit allowlist check against ``settings.telegram_allowed_chat_ids`` so that
only the operator (not any Telegram user who can present valid Mini App
``initData`` for this bot) can mutate global LLM provider state. API keys are
never returned in responses — :mod:`app.core.runtime_config` always masks them.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.core import runtime_config
from app.core.config import Settings
from app.miniapp.auth import verify_telegram_init_data

logger = logging.getLogger(__name__)

MODELS_REFRESH_TIMEOUT_SECONDS = 15.0
PING_TIMEOUT_SECONDS = 10.0


# ---------------------------------------------------------------------------
# Request body schemas
# ---------------------------------------------------------------------------

class AddProviderBody(BaseModel):
    name: str = ""
    base_url: str = ""
    api_key: str = ""


class UpdateProviderBody(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None


class SetActiveBody(BaseModel):
    provider_id: str = ""
    model: str = ""


class PingBody(BaseModel):
    model: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message})


def _validate_base_url(base_url: str) -> str | None:
    url = base_url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        return "base_url must start with http:// or https://"
    return None


def _fetch_models(base_url: str, api_key: str) -> list[str]:
    """Call ``GET {base_url}/models`` and extract model ids from the ``data`` array.

    Raises:
        requests.HTTPError: upstream non-2xx.
        requests.RequestException: network / timeout errors.
        ValueError: response JSON is not in the OpenAI-compatible shape.
    """
    url = base_url.rstrip("/") + "/models"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=MODELS_REFRESH_TIMEOUT_SECONDS,
    )
    if resp.status_code >= 400:
        snippet = (resp.text or "")[:200].strip()
        raise requests.HTTPError(
            f"HTTP {resp.status_code}: {snippet or resp.reason}"
        )
    try:
        payload = resp.json()
    except ValueError as exc:
        raise ValueError(f"upstream returned invalid JSON: {exc}") from exc

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise ValueError("upstream response missing 'data' array")

    models: list[str] = []
    for item in data:
        if isinstance(item, dict):
            mid = item.get("id")
            if isinstance(mid, str) and mid:
                models.append(mid)
    return models


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def build_config_router(settings: Settings) -> APIRouter:
    """Build the ``/miniapp/config/*`` router.

    Args:
        settings: The process-wide :class:`Settings`. Passed so the router
            factory can ensure the runtime_config module is initialized with
            the same settings used by the rest of the app, and so that the
            allowlist check can consult ``telegram_allowed_chat_ids``.

    Returns:
        A ``fastapi.APIRouter`` with all config endpoints registered.
    """
    # Make sure runtime_config is wired to the same settings we were given.
    runtime_config.init(settings)

    # Allowlist dep: signature-valid initData alone is not enough — the Telegram
    # user id must also appear in ``telegram_allowed_chat_ids`` when it is set.
    # When the allowlist is empty we mirror the bot's own "open" policy (see
    # ``app/main.py::is_allowed_chat``) so the gate is never stricter than the
    # bot itself.
    allowed_ids = {
        str(cid).strip()
        for cid in (settings.telegram_allowed_chat_ids or [])
        if str(cid).strip()
    }

    async def _verify_allowed_user(
        user: dict = Depends(verify_telegram_init_data),
    ) -> dict:
        if not allowed_ids:
            return user
        uid = str(user.get("id", "")).strip()
        if not uid or uid not in allowed_ids:
            raise HTTPException(status_code=403, detail="user not allowed")
        return user

    auth = [Depends(_verify_allowed_user)]
    router = APIRouter(prefix="/miniapp/config", tags=["config"])

    # ----- Providers list / create -----

    @router.get("/providers", dependencies=auth)
    async def list_providers() -> dict[str, Any]:
        providers = runtime_config.list_providers_masked()
        try:
            active = runtime_config.get_active()
            active_id = active["provider_id"]
        except RuntimeError:
            active_id = None
        return {"providers": providers, "active_provider_id": active_id}

    @router.post("/providers", dependencies=auth, status_code=status.HTTP_201_CREATED)
    async def create_provider(body: AddProviderBody):
        name = body.name.strip()
        base_url = body.base_url.strip()
        api_key = body.api_key.strip()

        if not name or not base_url or not api_key:
            return _error(400, "name, base_url and api_key are all required")

        url_err = _validate_base_url(base_url)
        if url_err:
            return _error(400, url_err)

        provider = runtime_config.add_provider(
            name=name, base_url=base_url, api_key=api_key
        )
        return {"provider": provider}

    # ----- Single provider: update / delete -----

    @router.patch("/providers/{provider_id}", dependencies=auth)
    async def patch_provider(provider_id: str, body: UpdateProviderBody):
        kwargs: dict[str, Any] = {}

        if body.name is not None:
            name = body.name.strip()
            if not name:
                return _error(400, "name must not be empty")
            kwargs["name"] = name

        if body.base_url is not None:
            base_url = body.base_url.strip()
            if not base_url:
                return _error(400, "base_url must not be empty")
            url_err = _validate_base_url(base_url)
            if url_err:
                return _error(400, url_err)
            kwargs["base_url"] = base_url

        # api_key semantics: absent or empty string => leave unchanged.
        # Non-empty => rotate to the new value.
        if body.api_key is not None and body.api_key.strip():
            kwargs["api_key"] = body.api_key.strip()

        try:
            provider = runtime_config.update_provider(provider_id, **kwargs)
        except KeyError:
            return _error(404, f"provider not found: {provider_id}")
        return {"provider": provider}

    @router.delete("/providers/{provider_id}", dependencies=auth)
    async def remove_provider(provider_id: str):
        try:
            runtime_config.delete_provider(provider_id)
        except KeyError:
            return _error(404, f"provider not found: {provider_id}")
        except ValueError as exc:
            return _error(409, str(exc))
        return Response(status_code=204)

    # ----- Active provider -----

    @router.get("/active", dependencies=auth)
    async def get_active():
        try:
            return runtime_config.get_active()
        except RuntimeError as exc:
            return _error(404, str(exc))

    @router.post("/active", dependencies=auth)
    async def set_active(body: SetActiveBody):
        provider_id = body.provider_id.strip()
        model = body.model.strip()
        if not provider_id or not model:
            return _error(400, "provider_id and model are required")
        try:
            return runtime_config.set_active(provider_id, model)
        except KeyError:
            return _error(404, f"provider not found: {provider_id}")

    # ----- Model list refresh -----

    @router.post("/providers/{provider_id}/models", dependencies=auth)
    async def refresh_models(provider_id: str):
        try:
            base_url, api_key, _ = runtime_config._get_provider_credentials(
                provider_id
            )
        except KeyError:
            return _error(404, f"provider not found: {provider_id}")

        try:
            models = _fetch_models(base_url, api_key)
        except requests.HTTPError as exc:
            logger.warning("models refresh upstream error: %s", exc)
            return _error(502, str(exc))
        except requests.Timeout:
            return _error(502, "upstream /models request timed out")
        except requests.RequestException as exc:
            logger.warning("models refresh network error: %s", exc)
            return _error(502, f"network error: {exc}")
        except ValueError as exc:
            return _error(502, str(exc))

        runtime_config.update_models_cache(provider_id, models)

        refreshed = runtime_config.get_provider_masked(provider_id) or {}
        return {
            "models": models,
            "refreshed_at": refreshed.get("models_refreshed_at"),
        }

    # ----- Ping test -----

    @router.post("/providers/{provider_id}/ping", dependencies=auth)
    async def ping_provider(provider_id: str, body: PingBody):
        try:
            base_url, api_key, last_model = runtime_config._get_provider_credentials(
                provider_id
            )
        except KeyError:
            return _error(404, f"provider not found: {provider_id}")

        model = (body.model or last_model or "").strip()
        if not model:
            return {
                "ok": False,
                "error": "no model specified and provider has no last_model",
                "model": "",
            }

        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "error": f"openai SDK unavailable: {exc}", "model": model}

        try:
            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=PING_TIMEOUT_SECONDS,
                max_retries=0,
            )
            t0 = time.monotonic()
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            return {"ok": True, "latency_ms": latency_ms, "model": model}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "model": model}

    return router
