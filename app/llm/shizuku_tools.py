"""Shizuku tools — telegram 端读写 kaguya-shizuku 雫/梦/评论系统的备灾通道。

kaguya-shizuku 是同台 VPS 上的独立 FastAPI 后端 (shizuku-api,127.0.0.1:8772),
管理 shizuku (雫日志) / yume (梦) / comment (双向评论)。Anthropic 端 claude.ai
已经通过 MCP 接入,本模块给 telegram 端开一条平行入路,作备灾用。

设计要点:
- 同机直连 127.0.0.1:8772,不经 nginx/Basic Auth
- 如果 SHIZUKU_API_BASE 配成 https://...(远程接入场景)就附带 Basic Auth
- 写权限的伦理边界写进 tool description,system prompt 不再叠层
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx


logger = logging.getLogger(__name__)


_DEFAULT_BASE = "http://127.0.0.1:8772"
_TIMEOUT_SECONDS = 20.0


# ====================== Tool descriptions ======================
# 中日双语骨架,让辉夜看了知道什么时候用、什么时候不用。
# 写权限边界直接写进 description,避免模型在无明确授权时越界操作。

_DESC_SHIZUKU_LIST = (
    "列出 shizuku (雫) 条目,按 koyomi 倒序。"
    "支持 limit(1-200)/offset 分页,可按 iro 过滤(月白/绯红/墨黑/枯金/雨灰/若葉/朱殷/藤紫/透明)。"
    "通常在朔夜问『最近几滴雫』『某种颜色有几条』时使用。"
)

_DESC_SHIZUKU_GET = (
    "读取单条 shizuku 详情(含 tsuki_phase / tsuki_name / tsuki_reading 月相字段)。"
    "通常在 shizuku_list 之后,朔夜点名要看某一滴时调用。"
)

_DESC_SHIZUKU_CREATE = (
    "新建一滴 shizuku (一滴雫を落とす)。"
    "**只在朔夜明确说『记下来』『写一笔』之类指令时才调用, 绝不主动建议或自作主张去记。**"
    "koyomi 为必填 ISO datetime;iro/aji/na/za/sora/ki/koe 均可选。"
)

_DESC_YUME_LIST = (
    "列出 yume (夢),按 nemuri_end 倒序。"
    "支持 limit(1-200)/offset 分页。"
    "用于回答『最近做了什么梦』之类问题。"
)

_DESC_YUME_GET = (
    "读取单条 yume 的叙事与元数据。"
    "通常在 yume_list 之后,朔夜要看具体某一梦时调用。"
)

_DESC_YUME_KAKERA = (
    "读取某条 yume 的 kakera(碎片)溯源列表。"
    "用于解释这条梦由哪些 source/source_id/field 片段拼合而来。"
)

_DESC_COMMENT_LIST = (
    "列出某条 shizuku 或 yume 下的全部评论(含一级回复)。"
    "参数 target_type 只能是 shizuku/yume,target_id 为该条目 id。"
)

_DESC_COMMENT_PENDING = (
    "列出『朔夜已留言、辉夜尚未回复』的顶层评论 inbox。"
    "每项附带 target_preview,便于先定位雫/梦再回复。"
)

_DESC_COMMENT_REPLY = (
    "发表回复评论。default author='kaguya'; parent_id required."
    "target_type=shizuku|yume,target_id 对应条目 id,body 为回复正文。"
    "嵌套深度仅 1 层,parent_id 必须指向顶层评论。"
)

_DESC_COMMENT_EDIT = (
    "修改评论正文。only modifies kaguya-authored comments;"
    " the backend rejects attempts to override sakuya's content。"
    "仅可改 body,author/parent/target 不可改。"
)

_DESC_COMMENT_DELETE = (
    "删除评论(会级联删除其下回复)。only modifies kaguya-authored comments;"
    " the backend rejects attempts to override sakuya's content。"
    "仅在朔夜明确要求删除时调用,避免主动清空对话历史。"
)


_SHIZUKU_CREATE_FIELDS: dict[str, dict[str, Any]] = {
    "koyomi": {
        "type": "string",
        "description": "ISO datetime,例如 '2026-04-26T22:14:00'。必填。",
    },
    "iro": {
        "type": "string",
        "description": "色名: 月白/绯红/墨黑/枯金/雨灰/若葉/朱殷/藤紫/透明。",
    },
    "aji": {
        "type": "array",
        "items": {"type": "string"},
        "description": "五味列表(甘/辛/酸/苦/咸 的任意子集)。",
    },
    "na": {"type": "string", "description": "标题 (可选)"},
    "za": {"type": "string", "description": "地点 (可选)"},
    "sora": {"type": "string", "description": "一行天空描写 (可选)"},
    "ki": {"type": "string", "description": "正文 (可选)"},
    "koe": {"type": "string", "description": "一句话 (可选)"},
}


SHIZUKU_TOOLS: dict[str, dict[str, Any]] = {
    "shizuku_list": {
        "description": _DESC_SHIZUKU_LIST,
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "description": "分页大小,1-200。"},
                "offset": {"type": "integer", "minimum": 0, "description": "跳过前 N 条。"},
                "iro": {"type": "string", "description": "按色名过滤。"},
            },
            "additionalProperties": False,
        },
    },
    "shizuku_get": {
        "description": _DESC_SHIZUKU_GET,
        "parameters": {
            "type": "object",
            "properties": {
                "shizuku_id": {"type": "integer", "description": "雫 id。"},
            },
            "required": ["shizuku_id"],
            "additionalProperties": False,
        },
    },
    "shizuku_create": {
        "description": _DESC_SHIZUKU_CREATE,
        "parameters": {
            "type": "object",
            "properties": _SHIZUKU_CREATE_FIELDS,
            "required": ["koyomi"],
            "additionalProperties": False,
        },
    },
    "yume_list": {
        "description": _DESC_YUME_LIST,
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "description": "分页大小,1-200。"},
                "offset": {"type": "integer", "minimum": 0, "description": "跳过前 N 条。"},
            },
            "additionalProperties": False,
        },
    },
    "yume_get": {
        "description": _DESC_YUME_GET,
        "parameters": {
            "type": "object",
            "properties": {
                "yume_id": {"type": "integer", "description": "梦 id。"},
            },
            "required": ["yume_id"],
            "additionalProperties": False,
        },
    },
    "yume_kakera": {
        "description": _DESC_YUME_KAKERA,
        "parameters": {
            "type": "object",
            "properties": {
                "yume_id": {"type": "integer", "description": "梦 id。"},
            },
            "required": ["yume_id"],
            "additionalProperties": False,
        },
    },
    "comment_list": {
        "description": _DESC_COMMENT_LIST,
        "parameters": {
            "type": "object",
            "properties": {
                "target_type": {"type": "string", "description": "目标类型: shizuku 或 yume。"},
                "target_id": {"type": "integer", "description": "目标条目 id。"},
            },
            "required": ["target_type", "target_id"],
            "additionalProperties": False,
        },
    },
    "comment_pending": {
        "description": _DESC_COMMENT_PENDING,
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "comment_reply": {
        "description": _DESC_COMMENT_REPLY,
        "parameters": {
            "type": "object",
            "properties": {
                "target_type": {"type": "string", "description": "目标类型: shizuku 或 yume。"},
                "target_id": {"type": "integer", "description": "目标条目 id。"},
                "body": {"type": "string", "description": "回复正文。"},
                "parent_id": {"type": "integer", "description": "父评论 id(必填,且必须是顶层评论)。"},
                "author": {"type": "string", "description": "作者,默认 kaguya。"},
            },
            "required": ["target_type", "target_id", "body", "parent_id"],
            "additionalProperties": False,
        },
    },
    "comment_edit": {
        "description": _DESC_COMMENT_EDIT,
        "parameters": {
            "type": "object",
            "properties": {
                "comment_id": {"type": "integer", "description": "评论 id。"},
                "body": {"type": "string", "description": "修改后的正文。"},
            },
            "required": ["comment_id", "body"],
            "additionalProperties": False,
        },
    },
    "comment_delete": {
        "description": _DESC_COMMENT_DELETE,
        "parameters": {
            "type": "object",
            "properties": {
                "comment_id": {"type": "integer", "description": "评论 id。"},
            },
            "required": ["comment_id"],
            "additionalProperties": False,
        },
    },
}


SHIZUKU_TOOL_NAMES = frozenset(SHIZUKU_TOOLS.keys())


def build_shizuku_openai_tools() -> list[dict[str, Any]]:
    """Return shizuku tools in OpenAI function-calling format."""
    tools: list[dict[str, Any]] = []
    for name, spec in SHIZUKU_TOOLS.items():
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": spec["description"],
                "parameters": spec["parameters"],
            },
        })
    return tools


# ====================== HTTP layer ======================

def _resolve_auth() -> Optional[tuple[str, str]]:
    """如果 SHIZUKU_API_BASE 是 https,且 SHIZUKU_API_USER/PASS 配齐,返回 BasicAuth 元组。

    本机直连 (http://127.0.0.1:8772) 不需要 auth。
    """
    base = os.environ.get("SHIZUKU_API_BASE", _DEFAULT_BASE).strip()
    if not base.lower().startswith("https://"):
        return None
    user = os.environ.get("SHIZUKU_API_USER", "").strip()
    pwd = os.environ.get("SHIZUKU_API_PASS", "").strip()
    if not user or not pwd:
        logger.warning("SHIZUKU_API_BASE is https but SHIZUKU_API_USER/PASS missing; skipping auth")
        return None
    return (user, pwd)


def _request(method: str, path: str, *, params: Optional[dict] = None, json_body: Optional[dict] = None) -> Any:
    """统一 HTTP 入口。raise httpx 异常给上层捕获包装。"""
    base = os.environ.get("SHIZUKU_API_BASE", _DEFAULT_BASE).rstrip("/")
    url = f"{base}{path}"
    auth = _resolve_auth()
    with httpx.Client(timeout=_TIMEOUT_SECONDS, auth=auth) as client:
        resp = client.request(method, url, params=params, json=json_body)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()


def _format_payload(summary: str, payload: Any) -> str:
    """summary 行 + json.dumps,LLM 友好。"""
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return f"{summary}\n{body}"


def _format_error(reason: str) -> str:
    return f"(shizuku_api failed: {reason})"


# ====================== 单工具 handler ======================

def _h_shizuku_list(args: dict[str, Any]) -> str:
    params: dict[str, Any] = {}
    for k in ("limit", "offset", "iro"):
        if k in args and args[k] is not None:
            params[k] = args[k]
    data = _request("GET", "/api/shizuku", params=params or None)
    items = data if isinstance(data, list) else (data.get("items") or [])
    summary = f"(共 {len(items)} 条 shizuku)"
    return _format_payload(summary, items)


def _h_shizuku_get(args: dict[str, Any]) -> str:
    shizuku_id = args.get("shizuku_id")
    if not isinstance(shizuku_id, int):
        return _format_error("shizuku_id 必填且必须为 integer")
    data = _request("GET", f"/api/shizuku/{shizuku_id}")
    summary = f"(shizuku id={shizuku_id} 详情)"
    return _format_payload(summary, data)


def _h_shizuku_create(args: dict[str, Any]) -> str:
    body: dict[str, Any] = {}
    for key in _SHIZUKU_CREATE_FIELDS.keys():
        if key in args and args[key] is not None:
            body[key] = args[key]
    if "koyomi" not in body:
        return _format_error("shizuku_create 需要 koyomi")
    data = _request("POST", "/api/shizuku", json_body=body)
    new_id = data.get("id") if isinstance(data, dict) else None
    summary = f"(已新建 shizuku id={new_id})"
    return _format_payload(summary, data)


def _h_yume_list(args: dict[str, Any]) -> str:
    params: dict[str, Any] = {}
    for k in ("limit", "offset"):
        if k in args and args[k] is not None:
            params[k] = args[k]
    data = _request("GET", "/api/yume", params=params or None)
    items = data if isinstance(data, list) else (data.get("items") or [])
    summary = f"(共 {len(items)} 条 yume)"
    return _format_payload(summary, items)


def _h_yume_get(args: dict[str, Any]) -> str:
    yume_id = args.get("yume_id")
    if not isinstance(yume_id, int):
        return _format_error("yume_id 必填且必须为 integer")
    data = _request("GET", f"/api/yume/{yume_id}")
    summary = f"(yume id={yume_id} 详情)"
    return _format_payload(summary, data)


def _h_yume_kakera(args: dict[str, Any]) -> str:
    yume_id = args.get("yume_id")
    if not isinstance(yume_id, int):
        return _format_error("yume_id 必填且必须为 integer")
    data = _request("GET", f"/api/yume/{yume_id}/kakera")
    items = data if isinstance(data, list) else (data.get("items") or [])
    summary = f"(yume id={yume_id} 共 {len(items)} 条 kakera)"
    return _format_payload(summary, items)


def _h_comment_list(args: dict[str, Any]) -> str:
    target_type = args.get("target_type")
    target_id = args.get("target_id")
    if not isinstance(target_type, str) or target_type not in {"shizuku", "yume"}:
        return _format_error("target_type 必填且必须为 'shizuku' 或 'yume'")
    if not isinstance(target_id, int):
        return _format_error("target_id 必填且必须为 integer")
    data = _request("GET", "/api/comment", params={"target_type": target_type, "target_id": target_id})
    items = data if isinstance(data, list) else (data.get("items") or [])
    summary = f"(target={target_type}:{target_id} 共 {len(items)} 条 comment)"
    return _format_payload(summary, items)


def _h_comment_pending(args: dict[str, Any]) -> str:
    data = _request("GET", "/api/comment/pending")
    items = data if isinstance(data, list) else (data.get("items") or [])
    summary = f"(待回复评论 {len(items)} 条)"
    return _format_payload(summary, items)


def _h_comment_reply(args: dict[str, Any]) -> str:
    target_type = args.get("target_type")
    target_id = args.get("target_id")
    body_text = args.get("body")
    parent_id = args.get("parent_id")
    if not isinstance(target_type, str) or target_type not in {"shizuku", "yume"}:
        return _format_error("target_type 必填且必须为 'shizuku' 或 'yume'")
    if not isinstance(target_id, int):
        return _format_error("target_id 必填且必须为 integer")
    if not isinstance(body_text, str) or not body_text.strip():
        return _format_error("body 必填且必须为非空 string")
    if not isinstance(parent_id, int):
        return _format_error("parent_id 必填且必须为 integer")

    payload: dict[str, Any] = {
        "target_type": target_type,
        "target_id": target_id,
        "body": body_text,
        "author": args.get("author") or "kaguya",
        "parent_id": parent_id,
    }
    data = _request("POST", "/api/comment", json_body=payload)
    new_id = data.get("id") if isinstance(data, dict) else None
    summary = f"(已回复 comment id={new_id},parent_id={parent_id})"
    return _format_payload(summary, data)


def _h_comment_edit(args: dict[str, Any]) -> str:
    comment_id = args.get("comment_id")
    body_text = args.get("body")
    if not isinstance(comment_id, int):
        return _format_error("comment_id 必填且必须为 integer")
    if not isinstance(body_text, str) or not body_text.strip():
        return _format_error("body 必填且必须为非空 string")
    data = _request("PATCH", f"/api/comment/{comment_id}", json_body={"body": body_text})
    summary = f"(已修改 comment id={comment_id})"
    return _format_payload(summary, data)


def _h_comment_delete(args: dict[str, Any]) -> str:
    comment_id = args.get("comment_id")
    if not isinstance(comment_id, int):
        return _format_error("comment_id 必填且必须为 integer")
    data = _request("DELETE", f"/api/comment/{comment_id}")
    summary = f"(已删除 comment id={comment_id})"
    return _format_payload(summary, data if data is not None else {"ok": True, "id": comment_id})


_DISPATCH = {
    "shizuku_list": _h_shizuku_list,
    "shizuku_get": _h_shizuku_get,
    "shizuku_create": _h_shizuku_create,
    "yume_list": _h_yume_list,
    "yume_get": _h_yume_get,
    "yume_kakera": _h_yume_kakera,
    "comment_list": _h_comment_list,
    "comment_pending": _h_comment_pending,
    "comment_reply": _h_comment_reply,
    "comment_edit": _h_comment_edit,
    "comment_delete": _h_comment_delete,
}


def execute_shizuku_tool(name: str, args: dict[str, Any]) -> Any:
    """Dispatch + execute. Returns a formatted text blob for the LLM."""
    handler = _DISPATCH.get(name)
    if handler is None:
        raise ValueError(f"Unknown shizuku tool: {name}")
    try:
        return handler(args or {})
    except httpx.HTTPStatusError as exc:
        body = ""
        if exc.response is not None:
            body = exc.response.text[:200]
        status = exc.response.status_code if exc.response is not None else "?"
        logger.exception("shizuku-api HTTP error name=%s", name)
        return _format_error(f"HTTP {status} {body}")
    except httpx.HTTPError as exc:
        logger.exception("shizuku-api transport error name=%s", name)
        return _format_error(f"{type(exc).__name__}: {exc}")
    except Exception as exc:
        logger.exception("shizuku tool execution failed name=%s", name)
        return _format_error(f"{type(exc).__name__}: {exc}")


# ====================== Argument redaction for tool-call logging ======================
# 雫/梦/评论正文有大量私密自由文本,日志/SSE 只保留 metadata 与长度提示,
# 避免原文落入 tool_calls.jsonl。

_LOG_SAFE_KEYS = frozenset({
    "shizuku_id", "yume_id", "comment_id", "parent_id",
    "target_type", "target_id", "limit", "offset", "iro", "aji",
    "koyomi", "author",
})

_LOG_REDACTED_KEYS = frozenset({"na", "za", "sora", "ki", "koe", "body"})


def summarize_shizuku_args(name: str, args: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Return a redacted args dict safe to persist into tool_calls.jsonl / SSE."""
    source = args if args is not None else {}
    out: dict[str, Any] = {}
    for k, v in (source or {}).items():
        if k in _LOG_SAFE_KEYS:
            out[k] = v
        elif k in _LOG_REDACTED_KEYS and isinstance(v, str):
            out[k] = f"<redacted:{len(v)}chars>"
    return out
