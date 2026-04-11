# TASK: Inspector PR 修复

请对当前 `claude/review-docs-start-work-uhkf4` 分支做以下修改。不要新增功能，只修复已有代码的问题。

## 修复 1: `/api/overview` 全量扫描问题

`api.py` 的 `overview()` 里 `col.get(include=["metadatas"])` 会拉全量 drawer metadata 到内存。

改为：
- drawer 总数用 `col.count()`
- wing/room 计数调用 `TOOLS["mempalace_get_taxonomy"]["handler"]()` 然后从结果中提取 wing 数和 room 数
- 删掉原来遍历全部 metadatas 的逻辑

## 修复 2: `/api/overview` diary 返回值处理

`tool_diary_read` 返回的是 `{"agent": "kaguya", "entries": [...], "total": N, "showing": N}` 这个 dict。

当前代码的 `isinstance(raw, list)` 和 `raw.startswith("[")` 都不会命中。改为：

```python
if isinstance(raw, dict):
    diary_entries = raw.get("entries", [])
```

## 修复 3: ChromaDB PersistentClient 缓存

`_get_collection()` 每次请求都 `new PersistentClient`，构造成本高。

改为模块级缓存，按 `palace_path` 做 key：

```python
_chroma_cache: dict[str, chromadb.PersistentClient] = {}

def _get_collection(settings: Settings):
    import chromadb
    path_str = str(settings.palace_path)
    if path_str not in _chroma_cache:
        _chroma_cache[path_str] = chromadb.PersistentClient(path=path_str)
    client = _chroma_cache[path_str]
    try:
        return client.get_collection("mempalace_drawers")
    except Exception:
        return None
```

## 修复 4: `/api/drawers` 真正在 ChromaDB 层做 limit

当前 `col.get()` 拉全量后在 Python 端截断。改为给 `col.get()` 传 `limit=limit` 参数：

```python
kwargs: dict[str, Any] = {"include": ["metadatas", "documents"], "limit": limit}
```

然后删掉后面的 `min(len(ids), limit)` 截断逻辑，直接遍历全部返回结果。

## 修复 5: `_read_tail_large` 不完整行 bug

从文件中间开始读 chunk 时，`lines[0]` 可能是不完整的行。在 `remaining > 0` 时应丢弃第一个元素：

```python
text_lines = [l.decode("utf-8", errors="replace").strip() for l in lines]
# First element may be a partial line unless we read from file start
if remaining > 0 and text_lines:
    text_lines = text_lines[1:]
```

注意：这里的 `remaining` 是循环结束后的值。需要在循环外保存是否读到了文件开头的标志。改为：

```python
read_from_start = remaining == 0
# ...
if not read_from_start and text_lines:
    text_lines = text_lines[1:]
```

## 修复 6: `palace_writes` 字段命名

`ToolLoopResult.palace_writes` 的 key 从 `drawers_added` / `kg_triples_added` / `diary_entries` 改为 `drawer_write_calls` / `kg_write_calls` / `diary_write_calls`。

同步修改以下位置：
- `client.py` 中 `ToolLoopResult` 的 `palace_writes` 默认值
- `client.py` 中 `_PALACE_WRITE_TOOLS` 的 value
- `index.html` 前端 `TraceTab` 里读取 `pw.drawers_added` 等的地方，改为对应新 key

## 修复 7: 去掉 query param 鉴权

`api.py` 的 `_make_auth_dep` 中删掉 query param token 检查（`request.query_params.get("token")`），只保留 Authorization header 验证。

`index.html` 前端的 `getToken()` 中删掉从 URL query param 读 token 的逻辑，只保留 localStorage 读取。登录界面输入 token 后存入 localStorage。

## 修复 8: turn_id 碰撞

`main.py` 的 `_write_turn_summary` 里 `turn_id` 基于秒级时间戳，同秒内会碰撞。

改为加一个随机后缀：

```python
import secrets
turn_id = f"turn_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{chat_id}_{secrets.token_hex(4)}"
```

## 修复 9: `/api/graph/nodes` 缓存

`build_graph()` 会遍历全量 ChromaDB，每次请求都跑一遍太贵。加一个简单的 TTL 缓存（60秒）：

```python
_graph_cache: dict[str, tuple[float, dict]] = {}
_GRAPH_TTL = 60

def _get_cached_graph(settings):
    import time
    key = str(settings.palace_path)
    now = time.monotonic()
    if key in _graph_cache and now - _graph_cache[key][0] < _GRAPH_TTL:
        return _graph_cache[key][1]
    col = _get_collection(settings)
    if not col:
        return {"nodes": {}, "edges": []}
    from mempalace.palace_graph import build_graph
    nodes, edges = build_graph(col)
    result = {"nodes": nodes, "edges": edges}
    _graph_cache[key] = (now, result)
    return result
```

然后 `/api/graph/nodes` 和 `/api/graph/stats` 都用这个缓存。
