"""Runtime LLM configuration overlay.

Reads and writes a JSON file at ``{settings.state_dir}/llm_config.json`` that
stores a list of LLM provider credentials and the currently-active (provider,
model) pair. This overlay lets the operator swap providers/models without
restarting the service, while the frozen ``Settings`` dataclass still provides
the cold-start defaults on first run.

All mutations are protected by a module-level ``threading.RLock`` and atomically
persisted to disk. API keys are NEVER returned in plaintext through the public
``*_masked`` helpers.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import Settings, load_settings

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_CONFIG_FILENAME = "llm_config.json"

_lock = threading.RLock()
_state: dict[str, Any] | None = None
_settings: Settings | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _config_path(settings: Settings) -> Path:
    return settings.state_dir / _CONFIG_FILENAME


def _default_state(settings: Settings) -> dict[str, Any]:
    """Build an initial state seeded from the cold-start Settings."""
    now = _now_iso()
    provider_id = str(uuid.uuid4())
    provider = {
        "id": provider_id,
        "name": "Default",
        "base_url": settings.openrouter_base_url,
        "api_key": settings.openrouter_api_key,
        "last_model": settings.openrouter_model,
        "available_models": [],
        "models_refreshed_at": None,
        "created_at": now,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "providers": [provider],
        "active_provider_id": provider_id,
        "active_model": settings.openrouter_model,
    }


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".llm_config.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _load_from_disk(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid llm_config.json (not a dict): {path}")
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("providers", [])
    data.setdefault("active_provider_id", None)
    data.setdefault("active_model", "")
    return data


def _ensure_initialized(settings: Settings | None = None) -> None:
    """Make sure _settings and _state are populated. Safe to call repeatedly."""
    global _state, _settings
    with _lock:
        if _settings is None:
            _settings = settings or load_settings()
        path = _config_path(_settings)
        if _state is None:
            if path.exists():
                _state = _load_from_disk(path)
                logger.info("runtime_config loaded from %s", path)
            else:
                _state = _default_state(_settings)
                _atomic_write(path, _state)
                logger.info("runtime_config initialized new file at %s", path)


def _persist() -> None:
    assert _settings is not None and _state is not None
    _atomic_write(_config_path(_settings), _state)


def _find_provider(provider_id: str) -> dict[str, Any] | None:
    assert _state is not None
    for provider in _state.get("providers", []):
        if provider.get("id") == provider_id:
            return provider
    return None


def _mask_provider(provider: dict[str, Any]) -> dict[str, Any]:
    masked = dict(provider)
    masked["api_key"] = mask_key(provider.get("api_key", ""))
    return masked


# ---------------------------------------------------------------------------
# Public: bootstrap
# ---------------------------------------------------------------------------

def init(settings: Settings) -> None:
    """Explicitly initialize the module with a ``Settings`` instance.

    Optional — public functions will lazily call ``load_settings()`` themselves
    if this is not invoked first. Call this at process startup when you already
    have a ``Settings`` in hand to avoid redundant ``.env`` parsing.
    """
    _ensure_initialized(settings)


# ---------------------------------------------------------------------------
# Public: helpers
# ---------------------------------------------------------------------------

def mask_key(key: str) -> str:
    """Return a display-safe version of an API key.

    Keeps the first 8 and last 4 characters, joining them with ``...``.
    If the key length is <= 12 characters, returns ``"***"`` instead.
    """
    if not isinstance(key, str) or len(key) <= 12:
        return "***"
    return f"{key[:8]}...{key[-4:]}"


# ---------------------------------------------------------------------------
# Public: read-only queries
# ---------------------------------------------------------------------------

def get_active_client_config() -> tuple[str, str, str]:
    """Return ``(base_url, api_key, model)`` for the active provider.

    Raises:
        RuntimeError: if the ``active_provider_id`` does not resolve to a
            stored provider.
    """
    _ensure_initialized()
    with _lock:
        assert _state is not None
        active_id = _state.get("active_provider_id")
        provider = _find_provider(active_id) if active_id else None
        if provider is None:
            raise RuntimeError(
                "no active LLM provider — runtime_config is corrupted or empty"
            )
        model = _state.get("active_model") or provider.get("last_model") or ""
        return (
            provider.get("base_url", ""),
            provider.get("api_key", ""),
            model,
        )


def get_active() -> dict[str, Any]:
    """Return ``{provider_id, provider_name, base_url, model}`` for the active provider.

    The API key is intentionally omitted.

    Raises:
        RuntimeError: if no active provider is configured.
    """
    _ensure_initialized()
    with _lock:
        assert _state is not None
        active_id = _state.get("active_provider_id")
        provider = _find_provider(active_id) if active_id else None
        if provider is None:
            raise RuntimeError("no active LLM provider")
        return {
            "provider_id": provider["id"],
            "provider_name": provider.get("name", ""),
            "base_url": provider.get("base_url", ""),
            "model": _state.get("active_model") or provider.get("last_model") or "",
        }


def list_providers_masked() -> list[dict[str, Any]]:
    """List all providers with API keys masked, sorted by ``created_at`` ascending."""
    _ensure_initialized()
    with _lock:
        assert _state is not None
        providers = list(_state.get("providers", []))
        providers.sort(key=lambda p: p.get("created_at") or "")
        return [_mask_provider(p) for p in providers]


def get_provider_masked(provider_id: str) -> dict[str, Any] | None:
    """Return a single provider with API key masked, or ``None`` if missing."""
    _ensure_initialized()
    with _lock:
        provider = _find_provider(provider_id)
        if provider is None:
            return None
        return _mask_provider(provider)


# ---------------------------------------------------------------------------
# Public: mutations
# ---------------------------------------------------------------------------

def add_provider(name: str, base_url: str, api_key: str) -> dict[str, Any]:
    """Create and persist a new provider. Does not make it active.

    Returns:
        The masked provider dict.
    """
    _ensure_initialized()
    with _lock:
        assert _state is not None
        provider = {
            "id": str(uuid.uuid4()),
            "name": name,
            "base_url": base_url,
            "api_key": api_key,
            "last_model": "",
            "available_models": [],
            "models_refreshed_at": None,
            "created_at": _now_iso(),
        }
        _state["providers"].append(provider)
        _persist()
        return _mask_provider(provider)


def update_provider(
    provider_id: str,
    *,
    name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Partially update a provider's name / base_url / api_key.

    A value of ``None`` means "leave the field unchanged". Empty strings are
    treated as explicit writes.

    Raises:
        KeyError: if ``provider_id`` does not exist.
    """
    _ensure_initialized()
    with _lock:
        provider = _find_provider(provider_id)
        if provider is None:
            raise KeyError(f"provider not found: {provider_id}")
        if name is not None:
            provider["name"] = name
        if base_url is not None:
            provider["base_url"] = base_url
        if api_key is not None:
            provider["api_key"] = api_key
        _persist()
        return _mask_provider(provider)


def delete_provider(provider_id: str) -> None:
    """Remove a provider.

    Raises:
        ValueError: if the provider is currently active, or if removing it
            would leave the provider list empty.
        KeyError: if the provider does not exist.
    """
    _ensure_initialized()
    with _lock:
        assert _state is not None
        provider = _find_provider(provider_id)
        if provider is None:
            raise KeyError(f"provider not found: {provider_id}")
        if _state.get("active_provider_id") == provider_id:
            raise ValueError("cannot delete the currently active provider")
        if len(_state.get("providers", [])) <= 1:
            raise ValueError("cannot delete the last remaining provider")
        _state["providers"] = [
            p for p in _state["providers"] if p.get("id") != provider_id
        ]
        _persist()


def set_active(provider_id: str, model: str) -> dict[str, Any]:
    """Switch the active provider/model pair. Also updates the provider's ``last_model``.

    Returns:
        The same shape as :func:`get_active`.

    Raises:
        KeyError: if the provider does not exist.
    """
    _ensure_initialized()
    with _lock:
        assert _state is not None
        provider = _find_provider(provider_id)
        if provider is None:
            raise KeyError(f"provider not found: {provider_id}")
        provider["last_model"] = model
        _state["active_provider_id"] = provider_id
        _state["active_model"] = model
        _persist()
        return {
            "provider_id": provider["id"],
            "provider_name": provider.get("name", ""),
            "base_url": provider.get("base_url", ""),
            "model": model,
        }


def _get_provider_credentials(provider_id: str) -> tuple[str, str, str]:
    """Internal-only: return ``(base_url, api_key, last_model)`` for a provider.

    Returns the UNMASKED api_key and therefore must never be surfaced through
    an HTTP response. Reserved for server-side outbound calls such as the
    ``/models`` refresh and ``/ping`` handlers.

    Raises:
        KeyError: if the provider does not exist.
    """
    _ensure_initialized()
    with _lock:
        provider = _find_provider(provider_id)
        if provider is None:
            raise KeyError(f"provider not found: {provider_id}")
        return (
            provider.get("base_url", ""),
            provider.get("api_key", ""),
            provider.get("last_model", ""),
        )


def update_models_cache(provider_id: str, models: list[str]) -> None:
    """Cache the list of available models reported by a provider.

    Raises:
        KeyError: if the provider does not exist.
    """
    _ensure_initialized()
    with _lock:
        provider = _find_provider(provider_id)
        if provider is None:
            raise KeyError(f"provider not found: {provider_id}")
        provider["available_models"] = list(models)
        provider["models_refreshed_at"] = _now_iso()
        _persist()
