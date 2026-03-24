import os
import aiosqlite
from config.settings import DB_PATH


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                content     TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT 'general',
                tags        TEXT NOT NULL DEFAULT '',
                summary     TEXT NOT NULL DEFAULT '',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes(user_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_category ON notes(category)
        """)
        await db.commit()
