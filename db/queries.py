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
            "SELECT * FROM notes WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            user_id,
            limit,
        )
    return [_row_to_note(r) for r in rows]


async def get_today_notes(pool: asyncpg.Pool, user_id: int) -> list[Note]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM notes
               WHERE user_id = $1
                 AND created_at >= CURRENT_DATE
                 AND created_at < CURRENT_DATE + INTERVAL '1 day'
               ORDER BY created_at DESC""",
            user_id,
        )
    return [_row_to_note(r) for r in rows]


async def get_notes_by_category(
    pool: asyncpg.Pool, user_id: int, category: str, limit: int = 10
) -> list[Note]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM notes WHERE user_id = $1 AND category = $2
               ORDER BY created_at DESC LIMIT $3""",
            user_id,
            category,
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


async def get_note_by_id(pool: asyncpg.Pool, user_id: int, note_id: int) -> Note | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM notes WHERE id = $1 AND user_id = $2",
            note_id,
            user_id,
        )
    return _row_to_note(row) if row else None


async def delete_note(pool: asyncpg.Pool, user_id: int, note_id: int) -> bool:
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM notes WHERE id = $1 AND user_id = $2",
            note_id,
            user_id,
        )
    return result == "DELETE 1"


async def update_note(
    pool: asyncpg.Pool, user_id: int, note_id: int, content: str
) -> bool:
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notes SET content = $1 WHERE id = $2 AND user_id = $3",
            content,
            note_id,
            user_id,
        )
    return result == "UPDATE 1"


async def get_random_note(pool: asyncpg.Pool, user_id: int) -> Note | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM notes WHERE user_id = $1 ORDER BY RANDOM() LIMIT 1",
            user_id,
        )
    return _row_to_note(row) if row else None


async def get_stats(pool: asyncpg.Pool, user_id: int) -> dict:
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM notes WHERE user_id = $1", user_id
        )
        today = await conn.fetchval(
            """SELECT COUNT(*) FROM notes
               WHERE user_id = $1
                 AND created_at >= CURRENT_DATE
                 AND created_at < CURRENT_DATE + INTERVAL '1 day'""",
            user_id,
        )
        by_category = await conn.fetch(
            """SELECT category, COUNT(*) as count FROM notes
               WHERE user_id = $1 GROUP BY category ORDER BY count DESC""",
            user_id,
        )
        streak = await conn.fetchval(
            """WITH daily AS (
                 SELECT DISTINCT created_at::date AS day
                 FROM notes WHERE user_id = $1
               ),
               consecutive AS (
                 SELECT day,
                        day - (ROW_NUMBER() OVER (ORDER BY day))::int AS grp
                 FROM daily
               )
               SELECT COUNT(*) FROM consecutive
               WHERE grp = (SELECT grp FROM consecutive ORDER BY day DESC LIMIT 1)""",
            user_id,
        )
    return {
        "total": total,
        "today": today,
        "by_category": {r["category"]: r["count"] for r in by_category},
        "streak": streak or 0,
    }


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
