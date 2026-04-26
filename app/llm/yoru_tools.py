"""Yoru tools — telegram 端读写 kaguya-yoru 私人亲密关系记录系统的备灾通道。

kaguya-yoru 是同台 VPS 上的独立 FastAPI 后端 (yoru-api,127.0.0.1:8770),
管理 te (体位 catalog,98 条) / zu (身体部位,18 条) / shiori (栞,亲密关系
日记记录) / achievements (12 条解锁成就)。Anthropic 端 claude.ai 已经通过
MCP 接入,本模块给 telegram 端开一条平行入路,作备灾用。

设计要点:
- 同机直连 127.0.0.1:8770,不经 nginx/Basic Auth
- 如果 YORU_API_BASE 配成 https://...(远程接入场景)就附带 Basic Auth
- 写权限的伦理边界写进 tool description,system prompt 不再叠层
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx


logger = logging.getLogger(__name__)


_DEFAULT_BASE = "http://127.0.0.1:8770"
_TIMEOUT_SECONDS = 20.0


# ====================== Tool descriptions ======================
# 中日双语骨架,让辉夜看了知道什么时候用、什么时候不用。
# 写权限的伦理边界 (创建/删除栞) 写在 description 自身,
# 不依赖 system prompt 反复申明。

_DESC_LIST_TE = (
    "列出 yoru 的体位 catalog (te,共 98 条)。"
    "可选 category 过滤,合法值: 正常位 / 座位 / 侧位 / 交叉位 / 后背位 / "
    "骑乘位 / 伸长位 / 立位 / 口技 / 手技 / 前后戏 / 场景 / 变则 / 道具 / 未定。"
    "通常在新建栞前用来定位 te_id。"
)

_DESC_LIST_ZU = (
    "列出 yoru 的身体部位 catalog (zu,共 18 条)。"
    "可选 zone 过滤,合法值: 头面 / 上半身 / 四肢 / 下半身。"
    "新建栞时如果要附 zu_ids,先用这个工具拿到正确 id。"
)

_DESC_LIST_SHIORI = (
    "列出所有栞 (亲密关系记录),按 koyomi 时间倒序。"
    "可选 month=YYYY-MM 过滤某一月份,limit 截取头 N 条 (1-50)。"
    "栞的内容很私密,只在朔夜明确要求查阅历史时使用,不要主动翻档。"
)

_DESC_GET_SHIORI = (
    "取单条栞的完整详情,包含 te 关联和 zu 关联及每条 zu 的 note。"
    "通常在 yoru_list_shiori 之后,朔夜想看具体某一笔时调用。"
)

_DESC_ACHIEVEMENTS = (
    "返回 12 条成就的当前解锁进度 (七夜待 / 不知火 / 百花繚乱 / 等)。"
    "当朔夜询问『我们解锁了什么』『进度怎样』『还差多少』之类问题时使用。"
)

_DESC_STATS_BY_DAY = (
    "返回 {YYYY-MM-DD: [shiori,...]} 的日聚合,用于回答跨日期范围的"
    "频次/分布问题。可选 year_month=YYYY-MM 过滤。"
)

_DESC_TE_COUNTS = (
    "返回每个 te_id 的累计使用次数,用于回答『最常用的体位是什么』"
    "『XX 这一手用过多少次』之类问题。"
)

_DESC_CREATE_SHIORI = (
    "新建一笔栞 (亲密记录)。"
    "**只在朔夜明确说『记下来』『写一笔』『把这一夜挂上去』之类指令时才调用,"
    "绝不主动建议或自作主张去记。**"
    "koyomi (ISO datetime) 没指定时用当前时间;te_id 拿不准时先用 yoru_list_te 查。"
    "可附 zu_ids 列表关联身体部位。"
)

_DESC_UPDATE_SHIORI = (
    "修改某条栞的字段。只发要改的字段,不传的字段保持原值不动。"
    "在朔夜明确说『把那笔栞的 XX 改成 YY』之类指令时使用。"
)

_DESC_DELETE_SHIORI = (
    "删除一条栞,**仅在朔夜明确要求删除时使用**,不要因任何推理或"
    "代为决策而调用。后端是硬删,不可恢复。"
)


# ====================== Schema 定义 ======================

# 写操作 (create / update) 共享的字段 schema 片段。
# create 把 koyomi + te_id 列入 required,update 只 require shiori_id。
_SHIORI_WRITE_FIELDS: dict[str, dict[str, Any]] = {
    "koyomi": {
        "type": "string",
        "description": "ISO datetime,例如 '2026-04-25T22:00:00'。create 时必填。",
    },
    "te_id": {
        "type": "integer",
        "description": "体位 id,从 yoru_list_te 查到。create 时必填。",
    },
    "na": {"type": "string", "description": "诗名 (可选)"},
    "za": {"type": "string", "description": "地点 (可选)"},
    "suna": {"type": "integer", "description": "持续分钟 (可选)"},
    "hoshi_s": {
        "type": "integer",
        "minimum": 1,
        "maximum": 5,
        "description": "朔评分,1-5 (可选,默认 4)",
    },
    "hoshi_k": {
        "type": "integer",
        "minimum": 1,
        "maximum": 5,
        "description": "輝评分,1-5 (可选,默认 4)",
    },
    "shio": {"type": "integer", "description": "潮吹次数 (可选,默认 0)"},
    "sha": {"type": "integer", "description": "射精次数 (可选,默认 0)"},
    "cho": {"type": "integer", "description": "她的高潮次数 (可选,默认 0)"},
    "ki": {"type": "string", "description": "散文/感想 (可选)"},
    "koe": {"type": "string", "description": "她说的一句话 (可选)"},
    "zu_ids": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "zu_id": {
                    "type": "integer",
                    "description": "身体部位 id,从 yoru_list_zu 查",
                },
                "note": {
                    "type": "string",
                    "description": "对这个部位在这一笔栞里的具体描写。落在感官细节上,有具体动作、触感、声音、痕迹。例:『锁骨·第一个齿印落在这里』『穴·侧入转仰卧·龟头碾过左壁那块凸起·水声很大』『手·小指勾着小指站在月光底下』。可省略。",
                },
            },
            "required": ["zu_id"],
        },
        "description": "关联身体部位列表 (可选)。每项 {zu_id, note?}。zu_id 从 yoru_list_zu 拿。note 是这个部位在这一笔里独有的细节,栞的密度由这些 note 撑起来,有就写,不要敷衍泛泛。",
    },
}


YORU_TOOLS: dict[str, dict[str, Any]] = {
    "yoru_list_te": {
        "description": _DESC_LIST_TE,
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "类别过滤,见 description 列出的 15 个类。",
                },
            },
            "additionalProperties": False,
        },
    },
    "yoru_list_zu": {
        "description": _DESC_LIST_ZU,
        "parameters": {
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "description": "部位区域过滤: 头面 / 上半身 / 四肢 / 下半身",
                },
            },
            "additionalProperties": False,
        },
    },
    "yoru_list_shiori": {
        "description": _DESC_LIST_SHIORI,
        "parameters": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "YYYY-MM 形式过滤某月,例如 '2026-04'。",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "只取头 N 条,1-50。",
                },
            },
            "additionalProperties": False,
        },
    },
    "yoru_get_shiori": {
        "description": _DESC_GET_SHIORI,
        "parameters": {
            "type": "object",
            "properties": {
                "shiori_id": {
                    "type": "integer",
                    "description": "栞 id。",
                },
            },
            "required": ["shiori_id"],
            "additionalProperties": False,
        },
    },
    "yoru_get_achievements": {
        "description": _DESC_ACHIEVEMENTS,
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "yoru_get_stats_by_day": {
        "description": _DESC_STATS_BY_DAY,
        "parameters": {
            "type": "object",
            "properties": {
                "year_month": {
                    "type": "string",
                    "description": "YYYY-MM 形式过滤某月,例如 '2026-04'。",
                },
            },
            "additionalProperties": False,
        },
    },
    "yoru_get_te_counts": {
        "description": _DESC_TE_COUNTS,
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "yoru_create_shiori": {
        "description": _DESC_CREATE_SHIORI,
        "parameters": {
            "type": "object",
            "properties": _SHIORI_WRITE_FIELDS,
            "required": ["koyomi", "te_id"],
            "additionalProperties": False,
        },
    },
    "yoru_update_shiori": {
        "description": _DESC_UPDATE_SHIORI,
        "parameters": {
            "type": "object",
            "properties": {
                "shiori_id": {
                    "type": "integer",
                    "description": "要修改的栞 id。",
                },
                **_SHIORI_WRITE_FIELDS,
            },
            "required": ["shiori_id"],
            "additionalProperties": False,
        },
    },
    "yoru_delete_shiori": {
        "description": _DESC_DELETE_SHIORI,
        "parameters": {
            "type": "object",
            "properties": {
                "shiori_id": {
                    "type": "integer",
                    "description": "要删除的栞 id。硬删不可恢复。",
                },
            },
            "required": ["shiori_id"],
            "additionalProperties": False,
        },
    },
}


YORU_TOOL_NAMES = frozenset(YORU_TOOLS.keys())


def build_yoru_openai_tools() -> list[dict[str, Any]]:
    """Return yoru tools in OpenAI function-calling format."""
    tools: list[dict[str, Any]] = []
    for name, spec in YORU_TOOLS.items():
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
    """如果 YORU_API_BASE 是 https,且 YORU_API_USER/PASS 配齐,返回 BasicAuth 元组。

    本机直连 (http://127.0.0.1:8770) 不需要 auth。
    """
    base = os.environ.get("YORU_API_BASE", _DEFAULT_BASE).strip()
    if not base.lower().startswith("https://"):
        return None
    user = os.environ.get("YORU_API_USER", "").strip()
    pwd = os.environ.get("YORU_API_PASS", "").strip()
    if not user or not pwd:
        logger.warning("YORU_API_BASE is https but YORU_API_USER/PASS missing; skipping auth")
        return None
    return (user, pwd)


def _request(method: str, path: str, *, params: Optional[dict] = None, json_body: Optional[dict] = None) -> Any:
    """统一 HTTP 入口。raise httpx 异常给上层捕获包装。"""
    base = os.environ.get("YORU_API_BASE", _DEFAULT_BASE).rstrip("/")
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
    return f"(yoru_api failed: {reason})"


# ====================== 单工具 handler ======================

def _h_list_te(args: dict[str, Any]) -> str:
    data = _request("GET", "/api/te")
    items = data if isinstance(data, list) else (data.get("items") or [])
    category = (args.get("category") or "").strip()
    if category:
        items = [t for t in items if (t.get("category") or "") == category]
    summary = f"(共 {len(items)} 条 te" + (f",category={category}" if category else "") + ")"
    return _format_payload(summary, items)


def _h_list_zu(args: dict[str, Any]) -> str:
    data = _request("GET", "/api/zu")
    items = data if isinstance(data, list) else (data.get("items") or [])
    zone = (args.get("zone") or "").strip()
    if zone:
        items = [z for z in items if (z.get("zone") or "") == zone]
    summary = f"(共 {len(items)} 条 zu" + (f",zone={zone}" if zone else "") + ")"
    return _format_payload(summary, items)


def _h_list_shiori(args: dict[str, Any]) -> str:
    data = _request("GET", "/api/shiori")
    items = data if isinstance(data, list) else (data.get("items") or [])
    month = (args.get("month") or "").strip()
    if month:
        items = [s for s in items if (s.get("koyomi") or "").startswith(month)]
    limit = args.get("limit")
    if isinstance(limit, int) and limit > 0:
        items = items[:limit]
    latest = items[0].get("koyomi") if items else None
    summary = (
        f"(共 {len(items)} 条栞"
        + (f",month={month}" if month else "")
        + (f",最新 koyomi={latest}" if latest else "")
        + ")"
    )
    return _format_payload(summary, items)


def _h_get_shiori(args: dict[str, Any]) -> str:
    shiori_id = args.get("shiori_id")
    if not isinstance(shiori_id, int):
        return _format_error("shiori_id 必填且必须为 integer")
    data = _request("GET", f"/api/shiori/{shiori_id}")
    summary = f"(栞 id={shiori_id} 详情)"
    return _format_payload(summary, data)


def _h_get_achievements(args: dict[str, Any]) -> str:
    data = _request("GET", "/api/achievements")
    items = data if isinstance(data, list) else (data.get("items") or [])
    unlocked = sum(1 for a in items if a.get("unlocked"))
    summary = f"(成就总数 {len(items)},已解锁 {unlocked})"
    return _format_payload(summary, items)


def _h_get_stats_by_day(args: dict[str, Any]) -> str:
    data = _request("GET", "/api/stats/by-day")
    if not isinstance(data, dict):
        return _format_error(f"unexpected payload type: {type(data).__name__}")
    year_month = (args.get("year_month") or "").strip()
    if year_month:
        data = {k: v for k, v in data.items() if k.startswith(year_month)}
    summary = f"(共 {len(data)} 天有记录" + (f",month={year_month}" if year_month else "") + ")"
    return _format_payload(summary, data)


def _h_get_te_counts(args: dict[str, Any]) -> str:
    data = _request("GET", "/api/stats/te-counts")
    if not isinstance(data, dict):
        return _format_error(f"unexpected payload type: {type(data).__name__}")
    summary = f"(共 {len(data)} 个 te 有累计计数)"
    return _format_payload(summary, data)


def _h_create_shiori(args: dict[str, Any]) -> str:
    body: dict[str, Any] = {}
    for key in _SHIORI_WRITE_FIELDS.keys():
        if key in args and args[key] is not None:
            body[key] = args[key]
    if "koyomi" not in body or "te_id" not in body:
        return _format_error("create_shiori 需要 koyomi 和 te_id")
    data = _request("POST", "/api/shiori", json_body=body)
    new_id = data.get("id") if isinstance(data, dict) else None
    summary = f"(已新建栞 id={new_id})"
    return _format_payload(summary, data)


def _h_update_shiori(args: dict[str, Any]) -> str:
    shiori_id = args.get("shiori_id")
    if not isinstance(shiori_id, int):
        return _format_error("shiori_id 必填且必须为 integer")
    body: dict[str, Any] = {}
    for key in _SHIORI_WRITE_FIELDS.keys():
        if key in args and args[key] is not None:
            body[key] = args[key]
    if not body:
        return _format_error("update_shiori 至少要传一个字段")
    data = _request("PUT", f"/api/shiori/{shiori_id}", json_body=body)
    summary = f"(已更新栞 id={shiori_id},改动字段 {sorted(body.keys())})"
    return _format_payload(summary, data)


def _h_delete_shiori(args: dict[str, Any]) -> str:
    shiori_id = args.get("shiori_id")
    if not isinstance(shiori_id, int):
        return _format_error("shiori_id 必填且必须为 integer")
    data = _request("DELETE", f"/api/shiori/{shiori_id}")
    summary = f"(已删除栞 id={shiori_id})"
    return _format_payload(summary, data if data is not None else {"ok": True, "id": shiori_id})


_DISPATCH = {
    "yoru_list_te": _h_list_te,
    "yoru_list_zu": _h_list_zu,
    "yoru_list_shiori": _h_list_shiori,
    "yoru_get_shiori": _h_get_shiori,
    "yoru_get_achievements": _h_get_achievements,
    "yoru_get_stats_by_day": _h_get_stats_by_day,
    "yoru_get_te_counts": _h_get_te_counts,
    "yoru_create_shiori": _h_create_shiori,
    "yoru_update_shiori": _h_update_shiori,
    "yoru_delete_shiori": _h_delete_shiori,
}


def execute_yoru_tool(name: str, args: dict[str, Any]) -> str:
    """Dispatch + execute. Returns a formatted text blob for the LLM."""
    handler = _DISPATCH.get(name)
    if handler is None:
        raise ValueError(f"Unknown yoru tool: {name}")
    try:
        return handler(args or {})
    except httpx.HTTPStatusError as exc:
        body = ""
        if exc.response is not None:
            body = exc.response.text[:200]
        status = exc.response.status_code if exc.response is not None else "?"
        logger.exception("yoru-api HTTP error name=%s", name)
        return _format_error(f"HTTP {status} {body}")
    except httpx.HTTPError as exc:
        logger.exception("yoru-api transport error name=%s", name)
        return _format_error(f"{type(exc).__name__}: {exc}")
    except Exception as exc:
        logger.exception("yoru tool execution failed name=%s", name)
        return _format_error(f"{type(exc).__name__}: {exc}")


# ====================== Argument redaction for tool-call logging ======================
# 栞的散文 (ki) / 她说的话 (koe) / 诗名 (na) / 地点 (za) 都是高度私密的自由文本,
# 不能进 jsonl 操作日志。这里给一份 yoru 专属白名单,只保留 metadata 类字段
# (id / 计数 / 评分 / 时间 / 类别),自由文本一律丢弃,长字符串只返回长度提示。
# 由 client.py 在 dispatch 时显式调用,绕过 inspector.logger.summarize_arguments
# 的 unknown-tool fallback (它会把 <200 字符的字符串原样保留)。

_LOG_SAFE_KEYS = frozenset({
    "shiori_id", "te_id", "zu_ids",
    "koyomi", "month", "year_month", "limit",
    "category", "zone",
    "suna", "hoshi_s", "hoshi_k", "shio", "sha", "cho",
})

_LOG_REDACTED_KEYS = frozenset({"na", "za", "ki", "koe"})


def summarize_yoru_args(args: dict[str, Any]) -> dict[str, Any]:
    """Return a redacted args dict safe to persist into tool_calls.jsonl / SSE.

    Whitelist 策略: 只保留 metadata 字段;na/za/ki/koe 这种自由文本只留长度。
    """
    out: dict[str, Any] = {}
    for k, v in (args or {}).items():
        if k in _LOG_SAFE_KEYS:
            out[k] = v
        elif k in _LOG_REDACTED_KEYS and isinstance(v, str):
            out[k] = f"<redacted:{len(v)}chars>"
        # 未知 key 直接丢弃,不冒险落盘
    return out
