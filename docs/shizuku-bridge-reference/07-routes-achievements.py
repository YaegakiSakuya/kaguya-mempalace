"""routes.achievements — 12 条 願掛け 成就

GET /api/gan      返回全部 12 条 + 当前是否解锁

成就规则在 design-ref/drafts-v2.html line 84-97 与 kaguya-shizuku.html line 140-153
两份设计稿里完全一致, 此处直接落实.

规则与设计稿一一对应:
  furisode      振袖     第一条雫
  nananokami    七日書   连续 7 天写日记
  goshiki       五色     5 种以上不同的 iro
  gomishi       五味子   单条雫标注全部五味
  mochizuki_ki  望月記   满月之夜写日记
  tsugomori_ki  晦日記   晦日写日记
  hyakushizuku  百雫     累计 100 条日记
  akatsuki      暁       凌晨 3-5 点写日记
  sukitoori     透明     只有 koyomi 的纯沉默
  soragoto      空事     累计 50 条 sora
  shioumi       潮海     一月内标了 10 次咸
  amanogawa     天の川   七夕当日写日记 (7/7)

注: §6.6 中提到的 mu-on / kare-i (沉默触发) 属于 yume engine 的反向作用,
M2 实装. 这里只覆盖 design-ref 列出的 12 条.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter

from .. import db as dbm
from ..models import AchievementOut
from ..moon import is_full_moon, is_new_moon


router = APIRouter(prefix="/api/gan", tags=["gan"])


# ── 成就静态定义 ────────────────────────────────────────────────────────────
ACHIEVEMENTS: list[dict] = [
    {"id": "furisode",     "name": "振袖",   "reading": "ふりそで",     "desc": "第一条雫"},
    {"id": "nananokami",   "name": "七日書", "reading": "ななのかしょ", "desc": "连续 7 天写日记"},
    {"id": "goshiki",      "name": "五色",   "reading": "ごしき",       "desc": "5 种以上不同的 iro"},
    {"id": "gomishi",      "name": "五味子", "reading": "ごみし",       "desc": "单条雫标注全部五味"},
    {"id": "mochizuki_ki", "name": "望月記", "reading": "もちづきき",   "desc": "满月之夜写日记"},
    {"id": "tsugomori_ki", "name": "晦日記", "reading": "つごもりき",   "desc": "晦日写日记"},
    {"id": "hyakushizuku", "name": "百雫",   "reading": "ひゃくしずく", "desc": "累计 100 条日记"},
    {"id": "akatsuki",     "name": "暁",     "reading": "あかつき",     "desc": "凌晨 3-5 点写日记"},
    {"id": "sukitoori",    "name": "透明",   "reading": "すきとおり",   "desc": "只有 koyomi 的纯沉默"},
    {"id": "soragoto",     "name": "空事",   "reading": "そらごと",     "desc": "累计 50 条 sora"},
    {"id": "shioumi",      "name": "潮海",   "reading": "しおうみ",     "desc": "一月内标了 10 次咸"},
    {"id": "amanogawa",    "name": "天の川", "reading": "あまのがわ",   "desc": "七夕当日写日记"},
]


# ── 单条规则判定 ────────────────────────────────────────────────────────────
def _check_furisode(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT COUNT(*) AS n FROM shizuku").fetchone()
    return row["n"] >= 1


def _check_hyakushizuku(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT COUNT(*) AS n FROM shizuku").fetchone()
    return row["n"] >= 100


def _check_nananokami(conn: sqlite3.Connection) -> bool:
    """历史上任意 7 个连续日历日各有一条 shizuku.

    成就一旦达成就永久解锁 (achievement_state 缓存第一次解锁的时间戳),
    所以扫描整张表而不是滑动窗口 — 否则一个完成过 7 天连写但今天才点开
    页面的用户永远拿不到这个签.
    """
    rows = conn.execute(
        "SELECT DISTINCT date(koyomi) AS d FROM shizuku ORDER BY d DESC"
    ).fetchall()
    if len(rows) < 7:
        return False
    dates = [datetime.strptime(r["d"], "%Y-%m-%d").date() for r in rows]
    streak = 1
    for i in range(1, len(dates)):
        if (dates[i - 1] - dates[i]).days == 1:
            streak += 1
            if streak >= 7:
                return True
        else:
            streak = 1
    return streak >= 7


def _check_goshiki(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(DISTINCT iro) AS n FROM shizuku WHERE iro IS NOT NULL"
    ).fetchone()
    return row["n"] >= 5


def _check_gomishi(conn: sqlite3.Connection) -> bool:
    """某一条雫的 aji JSON 数组同时包含全部五味."""
    rows = conn.execute("SELECT aji FROM shizuku WHERE aji IS NOT NULL").fetchall()
    for r in rows:
        aji = dbm.decode_aji(r["aji"])
        if {"甘", "辛", "酸", "苦", "咸"}.issubset(aji):
            return True
    return False


def _check_mochizuki_ki(conn: sqlite3.Connection) -> bool:
    rows = conn.execute("SELECT koyomi FROM shizuku").fetchall()
    return any(is_full_moon(r["koyomi"]) for r in rows)


def _check_tsugomori_ki(conn: sqlite3.Connection) -> bool:
    rows = conn.execute("SELECT koyomi FROM shizuku").fetchall()
    return any(is_new_moon(r["koyomi"]) for r in rows)


def _check_akatsuki(conn: sqlite3.Connection) -> bool:
    """凌晨 3-5 点 (3:00 含, 5:00 不含) 写过日记."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM shizuku
        WHERE CAST(strftime('%H', koyomi) AS INTEGER) IN (3, 4)
        """
    ).fetchone()
    return row["n"] >= 1


def _check_sukitoori(conn: sqlite3.Connection) -> bool:
    """只有 koyomi, 其余字段全空 (含 aji 空数组)."""
    rows = conn.execute(
        """
        SELECT iro, na, za, sora, ki, koe, aji FROM shizuku
        WHERE COALESCE(iro,'') = ''
          AND COALESCE(na,'')  = ''
          AND COALESCE(za,'')  = ''
          AND COALESCE(sora,'')= ''
          AND COALESCE(ki,'')  = ''
          AND COALESCE(koe,'') = ''
        """
    ).fetchall()
    for r in rows:
        if not dbm.decode_aji(r["aji"]):
            return True
    return False


def _check_soragoto(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM shizuku WHERE COALESCE(sora,'') <> ''"
    ).fetchone()
    return row["n"] >= 50


def _check_shioumi(conn: sqlite3.Connection) -> bool:
    """任意 30 天滚动窗口里 aji 含咸的雫 >= 10 条."""
    rows = conn.execute(
        """
        SELECT date(koyomi) AS d, aji FROM shizuku
        WHERE aji LIKE '%咸%'
        ORDER BY koyomi
        """
    ).fetchall()
    salty_dates = [
        datetime.strptime(r["d"], "%Y-%m-%d").date()
        for r in rows
        if "咸" in dbm.decode_aji(r["aji"])
    ]
    for i in range(len(salty_dates)):
        window_end = salty_dates[i]
        count = sum(
            1 for d in salty_dates[i:] if (d - window_end).days < 30
        )
        if count >= 10:
            return True
    return False


def _check_amanogawa(conn: sqlite3.Connection) -> bool:
    """七夕 (7 月 7 日) 当天写过."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM shizuku WHERE strftime('%m-%d', koyomi) = '07-07'"
    ).fetchone()
    return row["n"] >= 1


_RULES = {
    "furisode":     _check_furisode,
    "nananokami":   _check_nananokami,
    "goshiki":      _check_goshiki,
    "gomishi":      _check_gomishi,
    "mochizuki_ki": _check_mochizuki_ki,
    "tsugomori_ki": _check_tsugomori_ki,
    "hyakushizuku": _check_hyakushizuku,
    "akatsuki":     _check_akatsuki,
    "sukitoori":    _check_sukitoori,
    "soragoto":     _check_soragoto,
    "shioumi":      _check_shioumi,
    "amanogawa":    _check_amanogawa,
}


# ── HTTP ────────────────────────────────────────────────────────────────────
@router.get("", response_model=list[AchievementOut])
def list_achievements() -> list[AchievementOut]:
    out: list[AchievementOut] = []
    with dbm.get_conn() as conn:
        cached = {
            r["id"]: r["earned_at"]
            for r in conn.execute("SELECT id, earned_at FROM achievement_state").fetchall()
        }
        any_new = False
        for meta in ACHIEVEMENTS:
            aid = meta["id"]
            earned = aid in cached
            if not earned and _RULES[aid](conn):
                conn.execute(
                    "INSERT OR IGNORE INTO achievement_state (id, earned_at) VALUES (?, ?)",
                    (aid, dbm.naive_now()),
                )
                cached[aid] = dbm.naive_now()
                earned = True
                any_new = True
            out.append(
                AchievementOut(
                    id=aid,
                    name=meta["name"],
                    reading=meta["reading"],
                    desc=meta["desc"],
                    earned=earned,
                    earned_at=cached.get(aid) if earned else None,
                )
            )
        if any_new:
            conn.commit()
    return out
