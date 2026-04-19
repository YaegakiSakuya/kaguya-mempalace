#!/usr/bin/env python3
"""迁移4对裸wing的drawer到规范wing，完成后删除原件。"""
import sys
from pathlib import Path

sys.path.insert(0, "/home/ubuntu/apps/kaguya-gateway")

import chromadb
from mempalace.mcp_server import TOOLS

MIGRATIONS = [
    ("thought", "wing_thought"),
    ("code", "wing_code"),
    ("sex_and_body", "wing_sex_and_body"),
    ("daily", "wing_daily"),
]

palace_path = None
for p in [Path("runtime/palace"), Path("runtime/mempalace"), Path(".mempalace")]:
    if p.exists():
        palace_path = p
        break
if not palace_path:
    print("ERROR: 找不到palace目录")
    sys.exit(1)
print(f"Using palace: {palace_path}")

client = chromadb.PersistentClient(path=str(palace_path))
cols = client.list_collections()
if not cols:
    print("ERROR: 没有collection")
    sys.exit(1)
col = cols[0]
print(f"Using collection: {col.name}")

add = TOOLS["mempalace_add_drawer"]["handler"]
delete = TOOLS["mempalace_delete_drawer"]["handler"]

total_migrated = 0
total_skipped = 0
total_failed = 0

for old_wing, new_wing in MIGRATIONS:
    result = col.get(
        where={"wing": old_wing},
        include=["metadatas", "documents"],
    )
    ids = result["ids"]
    metas = result["metadatas"]
    docs = result["documents"]

    print(f"\n=== {old_wing} -> {new_wing} : {len(ids)}条 ===")

    for drawer_id, meta, doc in zip(ids, metas, docs):
        room = meta.get("room", "untitled")
        short_id = drawer_id[-16:]
        try:
            add_result = add(
                wing=new_wing,
                room=room,
                content=doc,
                added_by="kaguya-migration-2026-04-18",
            )
            result_str = str(add_result).lower()
            is_error = "error" in result_str or "failed" in result_str
            is_dup = "duplicate" in result_str or "already" in result_str or "exists" in result_str

            if is_error:
                print(f"  X add failed, keeping original: {short_id}")
                total_failed += 1
                continue

            if is_dup:
                print(f"  ~ dup: {room} / {short_id}  (already in {new_wing})")
                total_skipped += 1
            else:
                print(f"  + add: {room} / {short_id}  -> {new_wing}")
                total_migrated += 1

            delete(drawer_id=drawer_id)
            print(f"    - del old: {short_id}")

        except Exception as e:
            print(f"  X EXCEPTION: {short_id} -- {e}")
            total_failed += 1

print(f"\n===== 总计 =====")
print(f"新加: {total_migrated}")
print(f"去重跳过(原件已删): {total_skipped}")
print(f"失败: {total_failed}")
