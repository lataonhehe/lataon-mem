import json
import asyncpg
from db.models import Note


async def save_note(pool: asyncpg.Pool, note: Note) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO notes (user_id, content, category, tags, summary)
               VALUES ($1, $2, $3, $4::jsonb, $5)
               RETURNING id""",
            note.user_id,
            note.content,
            note.category,
            json.dumps(note.tags, ensure_ascii=False),
            note.summary,
        )
        return row["id"]


async def get_recent_notes(
    pool: asyncpg.Pool, user_id: int, limit: int = 5
) -> list[Note]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM notes WHERE user_id = $1
               ORDER BY created_at DESC LIMIT $2""",
            user_id,
            limit,
        )
    return [_row_to_note(r) for r in rows]


async def search_notes(
    pool: asyncpg.Pool, user_id: int, keyword: str, limit: int = 5
) -> list[Note]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM notes
               WHERE user_id = $1
                 AND (content ILIKE $2 OR summary ILIKE $2 OR category ILIKE $2)
               ORDER BY created_at DESC LIMIT $3""",
            user_id,
            f"%{keyword}%",
            limit,
        )
    return [_row_to_note(r) for r in rows]


def _row_to_note(row) -> Note:
    tags = row["tags"] if isinstance(row["tags"], list) else json.loads(row["tags"])
    return Note(
        id=row["id"],
        user_id=row["user_id"],
        content=row["content"],
        category=row["category"],
        tags=tags,
        summary=row["summary"],
        created_at=row["created_at"],
    )
