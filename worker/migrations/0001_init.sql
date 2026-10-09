-- created_at lưu theo UTC dạng 'YYYY-MM-DD HH:MM:SS'
-- search_text = lower(content \n summary \n category), dùng cho /search
-- (LIKE của SQLite chỉ không phân biệt hoa thường với ASCII)
CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    content     TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'general',
    tags        TEXT NOT NULL DEFAULT '[]',
    summary     TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_notes_user_created ON notes(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_notes_user_category ON notes(user_id, category);
