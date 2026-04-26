"""routes.shizuku — 雫 CRUD

POST   /api/shizuku            创建一滴雫
GET    /api/shizuku            列表 (分页)
GET    /api/shizuku/{id}       单条
PATCH  /api/shizuku/{id}       局部更新
DELETE /api/shizuku/{id}       删除

每条返回都带 tsuki_phase / tsuki_name / tsuki_reading 三个由 koyomi 现算的月相字段.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import db as dbm
from ..models import IRO_HEX, ShizukuCreate, ShizukuOut, ShizukuUpdate
from ..moon import get_moon_phase


router = APIRouter(prefix="/api/shizuku", tags=["shizuku"])


def _row_to_out(row: dict) -> ShizukuOut:
    moon = get_moon_phase(row["koyomi"])
    return ShizukuOut(
        id=row["id"],
        koyomi=row["koyomi"],
        iro=row["iro"],
        iro_hex=row["iro_hex"],
        aji=dbm.decode_aji(row["aji"]),
        na=row["na"],
        za=row["za"],
        sora=row["sora"],
        ki=row["ki"],
        koe=row["koe"],
        created_at=row["created_at"],
        tsuki_phase=moon.phase,
        tsuki_name=moon.name,
        tsuki_reading=moon.reading,
    )


@router.post("", response_model=ShizukuOut, status_code=201)
def create_shizuku(payload: ShizukuCreate) -> ShizukuOut:
    with dbm.get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO shizuku (koyomi, iro, iro_hex, aji, na, za, sora, ki, koe, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.koyomi.isoformat(sep=" "),
                payload.iro,
                payload.iro_hex,
                dbm.encode_aji(payload.aji) if payload.aji else "[]",
                payload.na,
                payload.za,
                payload.sora,
                payload.ki,
                payload.koe,
                dbm.naive_now(),
            ),
        )
        new_id = cur.lastrowid
        conn.commit()
        row = conn.execute("SELECT * FROM shizuku WHERE id = ?", (new_id,)).fetchone()
        return _row_to_out(row)


@router.get("", response_model=list[ShizukuOut])
def list_shizuku(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    iro: Optional[str] = Query(None),
) -> list[ShizukuOut]:
    sql = "SELECT * FROM shizuku"
    params: list = []
    if iro is not None:
        sql += " WHERE iro = ?"
        params.append(iro)
    sql += " ORDER BY koyomi DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with dbm.get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [_row_to_out(r) for r in rows]


@router.get("/{shizuku_id}", response_model=ShizukuOut)
def get_shizuku(shizuku_id: int) -> ShizukuOut:
    with dbm.get_conn() as conn:
        row = conn.execute("SELECT * FROM shizuku WHERE id = ?", (shizuku_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="雫が見つからない")
        return _row_to_out(row)


@router.patch("/{shizuku_id}", response_model=ShizukuOut)
def update_shizuku(shizuku_id: int, payload: ShizukuUpdate) -> ShizukuOut:
    fields: list[str] = []
    values: list = []

    data = payload.model_dump(exclude_unset=True)
    if "koyomi" in data and data["koyomi"] is not None:
        fields.append("koyomi = ?")
        values.append(data["koyomi"].isoformat(sep=" "))

    # iro/iro_hex 同步: 客户端单独 PATCH iro 时, 用 IRO_HEX 表回填 hex 以避免
    # 残留旧颜色 (透明 → NULL).
    if "iro" in data and "iro_hex" not in data:
        data["iro_hex"] = IRO_HEX.get(data["iro"]) if data["iro"] is not None else None

    for col in ("iro", "iro_hex", "na", "za", "sora", "ki", "koe"):
        if col in data:
            fields.append(f"{col} = ?")
            values.append(data[col])
    if "aji" in data:
        fields.append("aji = ?")
        values.append(dbm.encode_aji(data["aji"]) if data["aji"] is not None else None)

    if not fields:
        # 没传任何字段, 直接读回
        with dbm.get_conn() as conn:
            row = conn.execute("SELECT * FROM shizuku WHERE id = ?", (shizuku_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="雫が見つからない")
            return _row_to_out(row)

    values.append(shizuku_id)
    with dbm.get_conn() as conn:
        cur = conn.execute(
            f"UPDATE shizuku SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="雫が見つからない")
        conn.commit()
        row = conn.execute("SELECT * FROM shizuku WHERE id = ?", (shizuku_id,)).fetchone()
        return _row_to_out(row)


@router.delete("/{shizuku_id}", status_code=204)
def delete_shizuku(shizuku_id: int) -> None:
    with dbm.get_conn() as conn:
        cur = conn.execute("DELETE FROM shizuku WHERE id = ?", (shizuku_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="雫が見つからない")
        conn.commit()
