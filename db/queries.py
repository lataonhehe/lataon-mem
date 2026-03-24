import aiosqlite
import json
from typing import Optional
from db.models import Note
from config.settings import DB_PATH


async def save_note(note: Note) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        tags_str = json.dumps(note.tags, ensure_ascii=False)
        cursor = await db.execute(
            """INSERT INTO notes (user_id, content, category, tags, summary)
               VALUES (?, ?, ?, ?, ?)""",
            (note.user_id, note.content, note.category, tags_str, note.summary),
        )
        await db.commit()
        return cursor.lastrowid


async def get_recent_notes(user_id: int, limit: int = 5) -> list[Note]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM notes WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return [_row_to_note(r) for r in rows]


async def search_notes(user_id: int, keyword: str, limit: int = 5) -> list[Note]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        pattern = f"%{keyword}%"
        async with db.execute(
            """SELECT * FROM notes
               WHERE user_id = ?
                 AND (content LIKE ? OR tags LIKE ? OR category LIKE ? OR summary LIKE ?)
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, pattern, pattern, pattern, pattern, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return [_row_to_note(r) for r in rows]


def _row_to_note(row) -> Note:
    import json as _json
    from datetime import datetime

    tags = _json.loads(row["tags"]) if row["tags"] else []
    return Note(
        id=row["id"],
        user_id=row["user_id"],
        content=row["content"],
        category=row["category"],
        tags=tags,
        summary=row["summary"],
        created_at=row["created_at"],
    )
