# Shizuku Bridge — Source Reference for CC

CC: 这一组文件是 `kaguya-shizuku` 仓库的 7 个核心源码 vendor 进来的快照,
用于让你在写 `app/llm/shizuku_tools.py` 时有完整的真相源 (你自己的 git
proxy 拿不到 kaguya-shizuku, 这是绕道).

## 文件用途

| File | 用途 |
|---|---|
| `01-shizuku_mcp-server.py` | **11 个 @mcp.tool() 工具的真相源** — name / description / 参数 / docstring 全在这里. shizuku_tools.py 的工具集和描述以这份为准. |
| `02-shizuku_mcp-client.py` | HTTP 调用风格参考. shizuku_tools.py 走 httpx, 也照同样的 endpoint 路径和 query 风格. |
| `03-backend-models.py` | Pydantic schema 真相 — 字段名 / 类型 / required vs Optional / 验证规则. |
| `04-routes-shizuku.py` | `/api/shizuku` CRUD endpoints (5 个). |
| `05-routes-yume.py` | `/api/yume` endpoints (4 个: list / get / kakera / trigger — 不要桥接 trigger). |
| `06-routes-comment.py` | `/api/comment` endpoints, 含 `/pending`, PATCH, DELETE. |
| `07-routes-achievements.py` | `/api/gan` (12 願掛け) — **本次不桥接, 仅供参考**. |

## 实装顺序

1. 完整看完 `01-shizuku_mcp-server.py` — 这是工具描述真相, 你的 `_DESC_*`
   常量直接对位 docstring (中日双语风格保留).
2. 看 `04` `05` `06` 三个 routes 文件 — 拿到 HTTP path / method / response
   shape.
3. 看 `03-backend-models.py` — 拿到 Pydantic schema, 用来写参数 schema 和
   返回类型.
4. 照 `app/llm/yoru_tools.py` 的结构 (538 行 18 工具) 复刻一份
   `app/llm/shizuku_tools.py` (~11 工具).

## CC 实装完成后

把 `docs/shizuku-bridge-reference/` 目录**保留**作为 long-term 的桥接文档,
但在 PR description 里说明: 这些是 vendored snapshot, 不是 mempalace 项
目本身的代码. 真相仍在 kaguya-shizuku 仓库, 这里的版本可能滞后.
