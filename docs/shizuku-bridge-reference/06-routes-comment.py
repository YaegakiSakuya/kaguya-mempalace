"""routes.comment — 朔夜与辉夜的双向对话痕迹

GET    /api/comment?target_type=...&target_id=...    某条 entry 的全部评论 (含回复)
GET    /api/comment/pending                          辉夜未回复的朔夜顶层评论
POST   /api/comment                                  新建 (顶层 / 一级回复)
PATCH  /api/comment/{id}                             修改 body (作者一致 + 未被回复)
DELETE /api/comment/{id}                             删除 (级联删除回复)

嵌套深度限制 1 层: parent_id 只能为 NULL 或指向一条 parent_id IS NULL 的评论.
这不是 SaaS 评论, 不要做无限嵌套.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import db as dbm
from ..models import CommentCreate, CommentOut, CommentPending, CommentTargetType, CommentUpdate


router = APIRouter(prefix="/api/comment", tags=["comment"])


@router.get("/pending", response_model=list[CommentPending])
def list_pending_comments() -> list[CommentPending]:
    """朔夜留下、辉夜还没回复的顶层评论, 附 target 简介让辉夜能定位."""
    with dbm.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.target_type, c.target_id, c.body, c.created_at
            FROM comment c
            WHERE c.parent_id IS NULL
              AND c.author = 'sakuya'
              AND NOT EXISTS (
                SELECT 1 FROM comment r
                WHERE r.parent_id = c.id AND r.author = 'kaguya'
              )
            ORDER BY c.created_at ASC
            """
        ).fetchall()

        out: list[CommentPending] = []
        for r in rows:
            preview = {}
            if r["target_type"] == "shizuku":
                t = conn.execute(
                    "SELECT na, koyomi, iro FROM shizuku WHERE id = ?", (r["target_id"],)
                ).fetchone()
                if t:
                    preview = {"na": t["na"], "koyomi": str(t["koyomi"]), "iro": t["iro"]}
            else:
                t = conn.execute(
                    "SELECT na, nemuri_end FROM yume WHERE id = ?", (r["target_id"],)
                ).fetchone()
                if t:
                    preview = {"na": t["na"], "nemuri_end": str(t["nemuri_end"])}
            out.append(CommentPending(
                id=r["id"], target_type=r["target_type"], target_id=r["target_id"],
                body=r["body"], created_at=r["created_at"], target_preview=preview,
            ))
        return out



def _row_to_out(row: dict) -> CommentOut:
    return CommentOut(
        id=row["id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        parent_id=row["parent_id"],
        author=row["author"],
        body=row["body"],
        created_at=row["created_at"],
    )


@router.get("", response_model=list[CommentOut])
def list_comments(
    target_type: CommentTargetType = Query(...),
    target_id: int = Query(...),
) -> list[CommentOut]:
    with dbm.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM comment
            WHERE target_type = ? AND target_id = ?
            ORDER BY
                COALESCE(parent_id, id) ASC,
                parent_id IS NULL DESC,
                created_at ASC
            """,
            (target_type, target_id),
        ).fetchall()
        return [_row_to_out(r) for r in rows]


@router.post("", response_model=CommentOut, status_code=201)
def create_comment(payload: CommentCreate) -> CommentOut:
    # target 校验: 必须真实存在, 否则评论会变孤儿
    target_table = {"shizuku": "shizuku", "yume": "yume"}[payload.target_type]
    with dbm.get_conn() as conn:
        target = conn.execute(
            f"SELECT id FROM {target_table} WHERE id = ?", (payload.target_id,)
        ).fetchone()
        if target is None:
            raise HTTPException(
                status_code=404,
                detail=f"{payload.target_type} {payload.target_id} が見つからない",
            )

        # 嵌套深度限制: parent 必须存在且自身是顶层
        if payload.parent_id is not None:
            parent = conn.execute(
                "SELECT parent_id, target_type, target_id FROM comment WHERE id = ?",
                (payload.parent_id,),
            ).fetchone()
            if parent is None:
                raise HTTPException(status_code=404, detail="親コメントが見つからない")
            if parent["parent_id"] is not None:
                raise HTTPException(
                    status_code=400, detail="嵌套深度限制 1 层: 回复不可再被回复"
                )
            if (
                parent["target_type"] != payload.target_type
                or parent["target_id"] != payload.target_id
            ):
                raise HTTPException(
                    status_code=400, detail="親コメントは別の対象に属している"
                )

        cur = conn.execute(
            """
            INSERT INTO comment (target_type, target_id, parent_id, author, body, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.target_type,
                payload.target_id,
                payload.parent_id,
                payload.author,
                payload.body,
                dbm.naive_now(),
            ),
        )
        new_id = cur.lastrowid
        conn.commit()
        row = conn.execute("SELECT * FROM comment WHERE id = ?", (new_id,)).fetchone()
        return _row_to_out(row)


@router.patch("/{comment_id}", response_model=CommentOut)
def update_comment(comment_id: int, payload: CommentUpdate) -> CommentOut:
    """修改 body. 限制: 必须是作者本人 (隐式: 只在前端做 sakuya 自检, 后端只验业务规则) +
    顶层评论已被 kaguya 回复后不可改 (不能改对话历史)."""
    with dbm.get_conn() as conn:
        row = conn.execute("SELECT * FROM comment WHERE id = ?", (comment_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="コメントが見つからない")
        if row["parent_id"] is None and row["author"] == "sakuya":
            replied = conn.execute(
                "SELECT 1 FROM comment WHERE parent_id = ? AND author = 'kaguya' LIMIT 1",
                (comment_id,),
            ).fetchone()
            if replied:
                raise HTTPException(
                    status_code=409,
                    detail="既に辉夜が返事をした — 編集できません",
                )
        conn.execute("UPDATE comment SET body = ? WHERE id = ?", (payload.body, comment_id))
        conn.commit()
        row = conn.execute("SELECT * FROM comment WHERE id = ?", (comment_id,)).fetchone()
        return _row_to_out(row)


@router.delete("/{comment_id}", status_code=204)
def delete_comment(comment_id: int) -> None:
    with dbm.get_conn() as conn:
        cur = conn.execute("DELETE FROM comment WHERE id = ?", (comment_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="コメントが見つからない")
        conn.commit()


@router.get("/{comment_id}", response_model=CommentOut)
def get_comment(comment_id: int) -> CommentOut:
    with dbm.get_conn() as conn:
        row = conn.execute("SELECT * FROM comment WHERE id = ?", (comment_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="コメントが見つからない")
        return _row_to_out(row)
