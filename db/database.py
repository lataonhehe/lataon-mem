import asyncpg
from config.settings import DATABASE_URL


async def get_pool() -> asyncpg.Pool:
    """Tạo connection pool, gọi 1 lần khi khởi động."""
    return await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)


async def init_db(pool: asyncpg.Pool):
    """Tạo bảng nếu chưa có."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id          SERIAL PRIMARY KEY,
                user_id     BIGINT NOT NULL,
                content     TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT 'general',
                tags        JSONB NOT NULL DEFAULT '[]',
                summary     TEXT NOT NULL DEFAULT '',
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes(user_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_category ON notes(category)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_content ON notes
            USING gin(to_tsvector('simple', content || ' ' || summary))
        """)
