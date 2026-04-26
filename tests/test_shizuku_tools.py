from __future__ import annotations

import json

import respx
from httpx import Response

from app.llm.shizuku_tools import build_shizuku_openai_tools, execute_shizuku_tool


EXPECTED_TOOL_NAMES = {
    "shizuku_list",
    "shizuku_get",
    "shizuku_create",
    "yume_list",
    "yume_get",
    "yume_kakera",
    "comment_list",
    "comment_pending",
    "comment_reply",
    "comment_edit",
    "comment_delete",
}


def test_build_shizuku_openai_tools_has_11_schemas() -> None:
    tools = build_shizuku_openai_tools()
    names = {t["function"]["name"] for t in tools}
    assert len(tools) == 11
    assert names == EXPECTED_TOOL_NAMES


@respx.mock
def test_execute_shizuku_list() -> None:
    route = respx.get("http://127.0.0.1:8772/api/shizuku").mock(
        return_value=Response(200, json=[])
    )
    execute_shizuku_tool("shizuku_list", {"limit": 10, "offset": 5, "iro": "月白"})
    req = route.calls[0].request
    assert req.url.params.get("limit") == "10"
    assert req.url.params.get("offset") == "5"
    assert req.url.params.get("iro") == "月白"


@respx.mock
def test_execute_shizuku_get() -> None:
    route = respx.get("http://127.0.0.1:8772/api/shizuku/9").mock(
        return_value=Response(200, json={"id": 9})
    )
    execute_shizuku_tool("shizuku_get", {"shizuku_id": 9})
    assert route.called


@respx.mock
def test_execute_shizuku_create() -> None:
    route = respx.post("http://127.0.0.1:8772/api/shizuku").mock(
        return_value=Response(201, json={"id": 11})
    )
    execute_shizuku_tool("shizuku_create", {"koyomi": "2026-04-26T22:14:00", "ki": "x"})
    req = route.calls[0].request
    assert json.loads(req.content) == {"koyomi": "2026-04-26T22:14:00", "ki": "x"}


@respx.mock
def test_execute_yume_list() -> None:
    route = respx.get("http://127.0.0.1:8772/api/yume").mock(
        return_value=Response(200, json=[])
    )
    execute_shizuku_tool("yume_list", {"limit": 3, "offset": 1})
    req = route.calls[0].request
    assert req.url.params.get("limit") == "3"
    assert req.url.params.get("offset") == "1"


@respx.mock
def test_execute_yume_get() -> None:
    route = respx.get("http://127.0.0.1:8772/api/yume/7").mock(
        return_value=Response(200, json={"id": 7})
    )
    execute_shizuku_tool("yume_get", {"yume_id": 7})
    assert route.called


@respx.mock
def test_execute_yume_kakera() -> None:
    route = respx.get("http://127.0.0.1:8772/api/yume/7/kakera").mock(
        return_value=Response(200, json=[])
    )
    execute_shizuku_tool("yume_kakera", {"yume_id": 7})
    assert route.called


@respx.mock
def test_execute_comment_list() -> None:
    route = respx.get("http://127.0.0.1:8772/api/comment").mock(
        return_value=Response(200, json=[])
    )
    execute_shizuku_tool("comment_list", {"target_type": "shizuku", "target_id": 5})
    req = route.calls[0].request
    assert req.url.params.get("target_type") == "shizuku"
    assert req.url.params.get("target_id") == "5"


@respx.mock
def test_execute_comment_pending() -> None:
    route = respx.get("http://127.0.0.1:8772/api/comment/pending").mock(
        return_value=Response(200, json=[])
    )
    execute_shizuku_tool("comment_pending", {})
    assert route.called


@respx.mock
def test_execute_comment_reply() -> None:
    route = respx.post("http://127.0.0.1:8772/api/comment").mock(
        return_value=Response(201, json={"id": 21})
    )
    execute_shizuku_tool(
        "comment_reply",
        {
            "target_type": "yume",
            "target_id": 7,
            "parent_id": 3,
            "body": "收到",
        },
    )
    req = route.calls[0].request
    assert json.loads(req.content) == {
        "target_type": "yume",
        "target_id": 7,
        "parent_id": 3,
        "body": "收到",
        "author": "kaguya",
    }


@respx.mock
def test_execute_comment_edit() -> None:
    route = respx.patch("http://127.0.0.1:8772/api/comment/4").mock(
        return_value=Response(200, json={"id": 4})
    )
    execute_shizuku_tool("comment_edit", {"comment_id": 4, "body": "改稿"})
    req = route.calls[0].request
    assert json.loads(req.content) == {"body": "改稿"}


@respx.mock
def test_execute_comment_delete() -> None:
    route = respx.delete("http://127.0.0.1:8772/api/comment/4").mock(
        return_value=Response(204)
    )
    execute_shizuku_tool("comment_delete", {"comment_id": 4})
    assert route.called
