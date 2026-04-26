"""models — Pydantic 模型 (in/out)

字段命名沿用 yoru 的日语 romaji 传统:
  koyomi (暦) / iro (色) / aji (味) / na (名) / za (座) /
  sora (空) / ki (記) / koe (聲)

iro 九色与 aji 五味的合法值在这里集中校验.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── 静态常量 ────────────────────────────────────────────────────────────────
IRO_NAMES: tuple[str, ...] = (
    "月白", "绯红", "墨黑", "枯金", "雨灰",
    "若葉", "朱殷", "藤紫", "透明",
)
"""iro 九色 — 见 CLAUDE.md §7.4. 透明的 hex = NULL."""

IRO_HEX: dict[str, Optional[str]] = {
    "月白":  "#7AAFC8",
    "绯红":  "#B03838",
    "墨黑":  "#484440",
    "枯金":  "#A88A38",
    "雨灰":  "#6A7890",
    "若葉":  "#5A9E5A",
    "朱殷":  "#7A1A1A",
    "藤紫":  "#9070B0",
    "透明":  None,
}

AJI_VALUES: tuple[str, ...] = ("甘", "辛", "酸", "苦", "咸")

CommentAuthor = Literal["sakuya", "kaguya"]
CommentTargetType = Literal["shizuku", "yume"]


# ── shizuku ─────────────────────────────────────────────────────────────────
class ShizukuBase(BaseModel):
    koyomi:  datetime
    iro:     Optional[str] = None
    iro_hex: Optional[str] = None
    aji:     list[str] = Field(default_factory=list)
    na:      Optional[str] = None
    za:      Optional[str] = None
    sora:    Optional[str] = None
    ki:      Optional[str] = None
    koe:     Optional[str] = None

    @field_validator("iro")
    @classmethod
    def _iro_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if v not in IRO_NAMES:
            raise ValueError(f"iro must be one of {IRO_NAMES}, got {v!r}")
        return v

    @field_validator("aji")
    @classmethod
    def _aji_valid(cls, v: list[str]) -> list[str]:
        for a in v:
            if a not in AJI_VALUES:
                raise ValueError(f"aji entries must be one of {AJI_VALUES}, got {a!r}")
        return list(dict.fromkeys(v))

    @model_validator(mode="after")
    def _sync_iro_hex(self):
        # 若用户提供了 iro 但没给 hex, 用静态表回填.
        # 透明 → hex = None, 这是设计文档定义的语义.
        if self.iro is not None and self.iro_hex is None:
            self.iro_hex = IRO_HEX.get(self.iro)
        return self


class ShizukuCreate(ShizukuBase):
    pass


class ShizukuUpdate(BaseModel):
    koyomi:  Optional[datetime] = None
    iro:     Optional[str] = None
    iro_hex: Optional[str] = None
    aji:     Optional[list[str]] = None
    na:      Optional[str] = None
    za:      Optional[str] = None
    sora:    Optional[str] = None
    ki:      Optional[str] = None
    koe:     Optional[str] = None

    @field_validator("iro")
    @classmethod
    def _iro_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if v not in IRO_NAMES:
            raise ValueError(f"iro must be one of {IRO_NAMES}, got {v!r}")
        return v

    @field_validator("aji")
    @classmethod
    def _aji_valid(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return None
        for a in v:
            if a not in AJI_VALUES:
                raise ValueError(f"aji entries must be one of {AJI_VALUES}, got {a!r}")
        return list(dict.fromkeys(v))


class ShizukuOut(ShizukuBase):
    id:           int
    created_at:   datetime
    tsuki_phase:  float
    tsuki_name:   str
    tsuki_reading: str


# ── yume ────────────────────────────────────────────────────────────────────
class YumeOut(BaseModel):
    id:           int
    nemuri_start: datetime
    nemuri_end:   datetime
    yume_type:    Literal["utatane", "nemuri"]
    aji_main:     Optional[str] = None
    aji_blend:    list[str] = Field(default_factory=list)
    sora:         Optional[str] = None
    na:           Optional[str] = None
    ki:           str
    kakera_count: int
    created_at:   datetime


class KakeraOut(BaseModel):
    yume_id:   int
    source:    Literal["shizuku", "shiori", "yume"]
    source_id: int
    field:     Literal["ki", "koe", "sora"]
    fragment:  str
    aji:       list[str] = Field(default_factory=list)


# ── comment ─────────────────────────────────────────────────────────────────
class CommentCreate(BaseModel):
    target_type: CommentTargetType
    target_id:   int
    parent_id:   Optional[int] = None
    author:      CommentAuthor
    body:        str = Field(min_length=1)


class CommentUpdate(BaseModel):
    """Edit a comment's body. author / parent_id / target are immutable."""
    body: str = Field(min_length=1)


class CommentPending(BaseModel):
    """A sakuya top-level comment awaiting kaguya's reply, with target preview."""
    id:          int
    target_type: CommentTargetType
    target_id:   int
    body:        str
    created_at:  datetime
    target_preview: dict   # {"na": ..., "koyomi": ...} or {"na": ..., "nemuri_end": ...}


class CommentOut(BaseModel):
    id:          int
    target_type: CommentTargetType
    target_id:   int
    parent_id:   Optional[int] = None
    author:      CommentAuthor
    body:        str
    created_at:  datetime


# ── achievement ─────────────────────────────────────────────────────────────
class AchievementOut(BaseModel):
    id:        str
    name:      str
    reading:   str
    desc:      str
    earned:    bool
    earned_at: Optional[datetime] = None


# ── stats ───────────────────────────────────────────────────────────────────
class StatsOut(BaseModel):
    shizuku_total:  int
    yume_total:     int
    iro_distribution:  dict[str, int]
    aji_distribution:  dict[str, int]
    silent_count:   int  # 透明 / 沉默 状态条数
