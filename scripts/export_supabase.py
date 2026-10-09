"""
Xuất bảng notes từ Supabase (Postgres) ra file SQL để import vào D1.

    python scripts/export_supabase.py
    cd worker && npx wrangler d1 execute lataon-mem-bot --remote --file ../data/d1_import.sql

Giữ nguyên id để link #id cũ vẫn đúng. Sau khi import, gọi /admin/reindex
để tạo embedding (bge-m3) cho toàn bộ ghi chú.
"""
import asyncio
import json
import os
from datetime import timezone
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

OUT = Path(__file__).resolve().parent.parent / "data" / "d1_import.sql"


def sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def build_search_text(content: str, summary: str, category: str) -> str:
    # Phải khớp với buildSearchText trong worker/src/db/queries.ts
    return "\n".join([content, summary, category]).lower()


async def main():
    load_dotenv()
    conn = await asyncpg.connect(os.environ["DATABASE_URL"], statement_cache_size=0)
    try:
        rows = await conn.fetch("SELECT * FROM notes ORDER BY id")
    finally:
        await conn.close()

    lines = []
    for r in rows:
        tags = r["tags"] if isinstance(r["tags"], list) else json.loads(r["tags"])
        created = r["created_at"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        values = ", ".join([
            str(r["id"]),
            str(r["user_id"]),
            sql_str(r["content"]),
            sql_str(r["category"]),
            sql_str(json.dumps(tags, ensure_ascii=False)),
            sql_str(r["summary"]),
            sql_str(build_search_text(r["content"], r["summary"], r["category"])),
            sql_str(created),
        ])
        lines.append(
            "INSERT INTO notes (id, user_id, content, category, tags, summary, search_text, created_at) "
            f"VALUES ({values});"
        )

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Đã xuất {len(rows)} ghi chú → {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
