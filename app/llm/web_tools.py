"""Web search tool, powered by Tavily.

辉夜的联网搜索能力。结构上仿照 ops_tools.py:提供 OpenAI function-calling
schema + 单点 dispatch。内部通过 Tavily REST API 调度,走 httpx,
不引任何外部 SDK。
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx


logger = logging.getLogger(__name__)


_TAVILY_ENDPOINT = "https://api.tavily.com/search"
_DEFAULT_MAX_RESULTS = 5
_HARD_MAX_RESULTS = 10
_TIMEOUT_SECONDS = 20.0


# 搜索哲学:什么时候该搜、什么时候不搜。写进 description,
# 让 LLM 自己判断。不靠 system prompt 里再塞一遍教条。
_WEB_SEARCH_DESCRIPTION = (
    "用搜索引擎查最新的事实信息。适合用来回答:"
    "当前状态类问题(某人现在任什么职、某公司当前CEO、政策是否还有效)、"
    "时间敏感的信息(最近的新闻、事件、发布)、"
    "你记不清或不确定的专有名词/产品/人物,"
    "以及朔夜明确要你「帮我搜一下/查一查」的指令。"
    "不要用来查:历史常识、文学哲学理论、数学、显然不会变化的事实,"
    "也不要在朔夜只是想找你聊天、倾诉、共感的时刻动用它。"
    "不要一次查询里塞太多词,1-6 个关键词最有效。"
)


WEB_TOOLS: dict[str, dict[str, Any]] = {
    "web_search": {
        "description": _WEB_SEARCH_DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "1-6 个关键词。太长的自然语言问句搜索效果反而差。",
                },
                "max_results": {
                    "type": "integer",
                    "description": f"返回多少条结果,默认 {_DEFAULT_MAX_RESULTS},上限 {_HARD_MAX_RESULTS}。",
                    "minimum": 1,
                    "maximum": _HARD_MAX_RESULTS,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}


WEB_TOOL_NAMES = frozenset(WEB_TOOLS.keys())


def build_web_openai_tools() -> list[dict[str, Any]]:
    """Return web tools in OpenAI function-calling format."""
    tools = []
    for name, spec in WEB_TOOLS.items():
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": spec["description"],
                "parameters": spec["parameters"],
            },
        })
    return tools


def _format_results(query: str, results: list[dict[str, Any]]) -> str:
    """把 Tavily 返回的结果清洗成对 LLM 友好的文本。"""
    if not results:
        return f"(no search results for: {query})"
    lines = [f"搜索关键词:{query}", f"共 {len(results)} 条结果:\n"]
    for i, r in enumerate(results, 1):
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        content = (r.get("content") or "").strip()
        # 裁剪每条 snippet,避免单条吞掉太多上下文
        if len(content) > 600:
            content = content[:600] + "..."
        published = (r.get("published_date") or "").strip()
        header = f"[{i}] {title}"
        if published:
            header += f"  ({published})"
        lines.append(header)
        if url:
            lines.append(f"    {url}")
        if content:
            lines.append(f"    {content}")
        lines.append("")
    return "\n".join(lines).strip()


def execute_web_tool(name: str, args: dict[str, Any]) -> str:
    """Dispatch + execute a web tool. Returns a formatted text blob for the LLM."""
    if name != "web_search":
        raise ValueError(f"Unknown web tool: {name}")

    query = (args.get("query") or "").strip()
    if not query:
        return "(empty query; nothing to search)"

    max_results = int(args.get("max_results") or _DEFAULT_MAX_RESULTS)
    max_results = max(1, min(max_results, _HARD_MAX_RESULTS))

    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        return "(web search disabled: TAVILY_API_KEY not set)"

    payload = {
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            resp = client.post(_TAVILY_ENDPOINT, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.exception("tavily HTTP error")
        body = exc.response.text[:200] if exc.response is not None else ""
        return f"(web search failed: HTTP {exc.response.status_code if exc.response else '?'}) {body}"
    except Exception as exc:
        logger.exception("tavily request failed")
        return f"(web search failed: {type(exc).__name__}: {exc})"

    results = data.get("results") or []
    return _format_results(query, results)
