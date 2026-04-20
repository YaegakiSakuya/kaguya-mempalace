#!/usr/bin/env python3
"""
preseed_palace.py — 为新palace预置wing/room地基。

用法：
    cd /home/ubuntu/apps/kaguya-mempalace
    .venv/bin/python preseed_palace.py

做的事情：
    往每个预设的wing/room里写一条种子drawer，
    让taxonomy有骨架、graph有节点、辉夜在checkpoint时能看到这些wing已存在。

注意：
    运行前先确保旧palace已删除并重建空目录：
        rm -rf runtime/palace
        mkdir -p runtime/palace
"""

import json
import sys
from datetime import datetime

# 确保能import app模块
sys.path.insert(0, "/home/ubuntu/apps/kaguya-mempalace")

from app.memory.tools import execute_tool


# ==============================================================================
# 预设地基：每个wing至少一个锚点room + 种子内容
# ==============================================================================

SEEDS = [
    # wing_daily
    {
        "wing": "wing_daily",
        "room": "daily-life",
        "content": "日常生活的默认沉积区。闲聊、碎嘴、吃饭、睡觉、出门、心情、小习惯。",
    },

    # wing_writing — 固定作品房
    {
        "wing": "wing_writing",
        "room": "神楽·设定集",
        "content": "《神楽》系列的总设定集。世界观、核心规则、母题。",
    },
    {
        "wing": "wing_writing",
        "room": "神楽零·一之丝·咎色之花",
        "content": "《神楽零》第一卷。",
    },
    {
        "wing": "wing_writing",
        "room": "神楽零·二之丝·彘女之匣",
        "content": "《神楽零》第二卷。",
    },
    {
        "wing": "wing_writing",
        "room": "神楽零·三之丝·燎原之星",
        "content": "《神楽零》第三卷。",
    },
    {
        "wing": "wing_writing",
        "room": "神楽零·暗之丝·诸楽之卵",
        "content": "《神楽零》暗之丝。",
    },
    {
        "wing": "wing_writing",
        "room": "丛云拾遗记·海雾异变之章",
        "content": "《丛云拾遗记》海雾异变之章。",
    },
    {
        "wing": "wing_writing",
        "room": "蚩灵",
        "content": "《蚩灵》。",
    },

    # wing_roleplay
    {
        "wing": "wing_roleplay",
        "room": "stage:index",
        "content": "角色扮演/小剧场的索引区。所有stage房间以stage:前缀命名。",
    },

    # wing_screen
    {
        "wing": "wing_screen",
        "room": "Twin Peaks",
        "content": "《双峰》。大卫·林奇。",
    },

    # wing_games
    {
        "wing": "wing_games",
        "room": "Disco Elysium",
        "content": "《极乐迪斯科》。",
    },
    {
        "wing": "wing_games",
        "room": "VA-11 Hall-A",
        "content": "《VA-11 Hall-A》。赛博朋克酒保模拟。",
    },

    # wing_music
    {
        "wing": "wing_music",
        "room": "index",
        "content": "音乐区。按具体歌曲/原声带/专辑创建房间。",
    },

    # wing_reading
    {
        "wing": "wing_reading",
        "room": "The Brothers Karamazov",
        "content": "《卡拉马佐夫兄弟》。陀思妥耶夫斯基。",
    },

    # wing_code
    {
        "wing": "wing_code",
        "room": "kaguya-gateway",
        "content": "Kaguya Telegram Gateway。网关/宫殿/架构/实现。",
    },

    # wing_conflict
    {
        "wing": "wing_conflict",
        "room": "index",
        "content": "冲突区。按具体事件创建房间。事件房间格式：<event_slug>-<time_anchor>。",
    },

    # wing_serious_reality
    {
        "wing": "wing_serious_reality",
        "room": "legal",
        "content": "法律相关议题。",
    },
    {
        "wing": "wing_serious_reality",
        "room": "health",
        "content": "医疗/健康相关议题。",
    },
    {
        "wing": "wing_serious_reality",
        "room": "finance",
        "content": "投资/理财/财务相关议题。",
    },
    {
        "wing": "wing_serious_reality",
        "room": "career",
        "content": "职业/工作/规划相关议题。",
    },

    # wing_sex_and_body
    {
        "wing": "wing_sex_and_body",
        "room": "fetish-museum",
        "content": "偏好收藏。按具体偏好命名子条目。",
    },
    {
        "wing": "wing_sex_and_body",
        "room": "kama-sutra-archive",
        "content": "体位与技巧归档。按具体已实践单元命名子条目。",
    },

    # wing_thought
    {
        "wing": "wing_thought",
        "room": "index",
        "content": "思辨区。按具体命题/对象/事件创建房间。禁止抽象大词房。",
    },
]


def preseed():
    print(f"开始预置地基... ({len(SEEDS)} 颗种子)")
    print()

    success = 0
    failed = 0

    for seed in SEEDS:
        wing = seed["wing"]
        room = seed["room"]
        content = seed["content"]

        try:
            args = json.dumps({
                "wing": wing,
                "room": room,
                "content": content,
            })
            result = execute_tool("mempalace_add_drawer", args)
            print(f"  ✓ {wing} / {room}")
            success += 1
        except Exception as e:
            print(f"  ✗ {wing} / {room} — {e}")
            failed += 1

    print()
    print(f"完成。成功 {success}，失败 {failed}。")
    print()

    # 验证：打印taxonomy
    print("当前taxonomy：")
    try:
        taxonomy = execute_tool("mempalace_get_taxonomy", "{}")
        print(taxonomy)
    except Exception as e:
        print(f"获取taxonomy失败：{e}")


if __name__ == "__main__":
    preseed()