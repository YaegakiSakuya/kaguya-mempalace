"""routes.yume — 梦的窗口

  GET  /api/yume                列表
  GET  /api/yume/{id}           单条
  GET  /api/yume/{id}/kakera    碎片溯源
  POST /api/yume/trigger        手动触发引擎跑一次 (M2)

POST /api/yume/trigger 是朔夜从前端按钮 / MCP 工具的入口. 内部走与 systemd timer
完全相同的 narrator.run_once, 因此同一段间隙触发两次也不会重复生成 (幂等).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from .. import db as dbm
from ..models import KakeraOut, YumeOut
from ..yume_engine import narrator
from ..yume_engine.llm_client import LLMConfigError


log = logging.getLogger("kaguya.yume.api")


router = APIRouter(prefix="/api/yume", tags=["yume"])


def _row_to_yume(row: dict) -> YumeOut:
    return YumeOut(
        id=row["id"],
        nemuri_start=row["nemuri_start"],
        nemuri_end=row["nemuri_end"],
        yume_type=row["yume_type"],
        aji_main=row["aji_main"],
        aji_blend=dbm.decode_aji(row["aji_blend"]),
        sora=row["sora"],
        na=row["na"],
        ki=row["ki"],
        kakera_count=row["kakera_count"],
        created_at=row["created_at"],
    )


@router.get("", response_model=list[YumeOut])
def list_yume(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[YumeOut]:
    with dbm.get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM yume ORDER BY nemuri_end DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_row_to_yume(r) for r in rows]


@router.get("/{yume_id}", response_model=YumeOut)
def get_yume(yume_id: int) -> YumeOut:
    with dbm.get_conn() as conn:
        row = conn.execute("SELECT * FROM yume WHERE id = ?", (yume_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="梦境引擎暂未醒来")
        return _row_to_yume(row)


@router.post("/trigger", status_code=200)
def trigger_yume() -> dict:
    """手动触发一次 yume engine.

    返回:
      {"yume_id": <id>, "status": "created"}     新梦已生成
      {"yume_id": null, "status": "no_gap"}     当前没有可造梦的睡眠间隙
      503  if mempalace LLM 配置不可读 (部署期未注入 KAGUYA_LLM_CONFIG_PATH)
    """
    with dbm.get_conn() as conn:
        try:
            yume_id = narrator.run_once(conn)
        except LLMConfigError as exc:
            log.warning("yume trigger blocked by llm config: %s", exc)
            raise HTTPException(status_code=503, detail="梦境引擎暂未醒来 — LLM 配置不可读")
    if yume_id is None:
        return {"yume_id": None, "status": "no_gap"}
    return {"yume_id": yume_id, "status": "created"}


@router.get("/{yume_id}/kakera", response_model=list[KakeraOut])
def get_yume_kakera(yume_id: int) -> list[KakeraOut]:
    with dbm.get_conn() as conn:
        head = conn.execute("SELECT id FROM yume WHERE id = ?", (yume_id,)).fetchone()
        if head is None:
            raise HTTPException(status_code=404, detail="梦境引擎暂未醒来")
        rows = conn.execute(
            "SELECT * FROM yume_kakera WHERE yume_id = ?",
            (yume_id,),
        ).fetchall()
        return [
            KakeraOut(
                yume_id=r["yume_id"],
                source=r["source"],
                source_id=r["source_id"],
                field=r["field"],
                fragment=r["fragment"],
                aji=dbm.decode_aji(r["aji"]),
            )
            for r in rows
        ]
