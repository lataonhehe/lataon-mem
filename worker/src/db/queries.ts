import type { Note } from "../types";

// "Hôm nay" và ngày hiển thị tính theo giờ Việt Nam
export const TZ_MODIFIER = "+7 hours";

const COLS = "id, user_id, content, category, tags, summary, created_at";

interface NoteRow {
  id: number;
  user_id: number;
  content: string;
  category: string;
  tags: string;
  summary: string;
  created_at: string;
}

function rowToNote(r: NoteRow): Note {
  return {
    id: r.id,
    userId: r.user_id,
    content: r.content,
    category: r.category,
    tags: JSON.parse(r.tags) as string[],
    summary: r.summary,
    createdAt: r.created_at,
  };
}

/** Phải khớp với scripts/export_supabase.py */
export function buildSearchText(content: string, summary: string, category: string): string {
  return [content, summary, category].join("\n").toLowerCase();
}

export async function saveNote(
  db: D1Database,
  n: Omit<Note, "id" | "createdAt">,
): Promise<Note> {
  const row = await db
    .prepare(
      `INSERT INTO notes (user_id, content, category, tags, summary, search_text)
       VALUES (?, ?, ?, ?, ?, ?)
       RETURNING ${COLS}`,
    )
    .bind(
      n.userId,
      n.content,
      n.category,
      JSON.stringify(n.tags),
      n.summary,
      buildSearchText(n.content, n.summary, n.category),
    )
    .first<NoteRow>();
  return rowToNote(row!);
}

export async function getRecentNotes(db: D1Database, userId: number, limit = 5): Promise<Note[]> {
  const { results } = await db
    .prepare(`SELECT ${COLS} FROM notes WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT ?`)
    .bind(userId, limit)
    .all<NoteRow>();
  return results.map(rowToNote);
}

export async function getTodayNotes(db: D1Database, userId: number): Promise<Note[]> {
  const { results } = await db
    .prepare(
      `SELECT ${COLS} FROM notes
       WHERE user_id = ?1
         AND date(created_at, ?2) = date('now', ?2)
       ORDER BY created_at DESC, id DESC`,
    )
    .bind(userId, TZ_MODIFIER)
    .all<NoteRow>();
  return results.map(rowToNote);
}

export async function getNotesByCategory(
  db: D1Database,
  userId: number,
  category: string,
  limit = 10,
): Promise<Note[]> {
  const { results } = await db
    .prepare(
      `SELECT ${COLS} FROM notes WHERE user_id = ? AND category = ?
       ORDER BY created_at DESC, id DESC LIMIT ?`,
    )
    .bind(userId, category, limit)
    .all<NoteRow>();
  return results.map(rowToNote);
}

export async function searchNotes(
  db: D1Database,
  userId: number,
  keyword: string,
  limit = 5,
): Promise<Note[]> {
  // search_text đã lowercase (Unicode) — LIKE của SQLite chỉ bỏ qua hoa/thường với ASCII
  const escaped = keyword.toLowerCase().replace(/[!%_]/g, (c) => "!" + c);
  const { results } = await db
    .prepare(
      `SELECT ${COLS} FROM notes
       WHERE user_id = ? AND search_text LIKE ? ESCAPE '!'
       ORDER BY created_at DESC, id DESC LIMIT ?`,
    )
    .bind(userId, `%${escaped}%`, limit)
    .all<NoteRow>();
  return results.map(rowToNote);
}

export async function getNoteById(db: D1Database, userId: number, noteId: number): Promise<Note | null> {
  const row = await db
    .prepare(`SELECT ${COLS} FROM notes WHERE id = ? AND user_id = ?`)
    .bind(noteId, userId)
    .first<NoteRow>();
  return row ? rowToNote(row) : null;
}

/** Lấy nhiều ghi chú theo id, giữ đúng thứ tự ids truyền vào. */
export async function getNotesByIds(db: D1Database, userId: number, ids: number[]): Promise<Note[]> {
  if (ids.length === 0) return [];
  const { results } = await db
    .prepare(
      `SELECT ${COLS} FROM notes WHERE user_id = ? AND id IN (${ids.map(() => "?").join(",")})`,
    )
    .bind(userId, ...ids)
    .all<NoteRow>();
  const byId = new Map(results.map((r) => [r.id, rowToNote(r)]));
  return ids.flatMap((id) => byId.get(id) ?? []);
}

export async function deleteNote(db: D1Database, userId: number, noteId: number): Promise<boolean> {
  const res = await db
    .prepare("DELETE FROM notes WHERE id = ? AND user_id = ?")
    .bind(noteId, userId)
    .run();
  return res.meta.changes > 0;
}

export async function updateNote(db: D1Database, note: Note, content: string): Promise<boolean> {
  const res = await db
    .prepare("UPDATE notes SET content = ?, search_text = ? WHERE id = ? AND user_id = ?")
    .bind(content, buildSearchText(content, note.summary, note.category), note.id, note.userId)
    .run();
  return res.meta.changes > 0;
}

export async function getRandomNote(db: D1Database, userId: number): Promise<Note | null> {
  const row = await db
    .prepare(`SELECT ${COLS} FROM notes WHERE user_id = ? ORDER BY RANDOM() LIMIT 1`)
    .bind(userId)
    .first<NoteRow>();
  return row ? rowToNote(row) : null;
}

export interface Stats {
  total: number;
  today: number;
  byCategory: { category: string; count: number }[];
  streak: number;
}

export async function getStats(db: D1Database, userId: number): Promise<Stats> {
  const [total, today, byCategory, streak] = await db.batch<Record<string, unknown>>([
    db.prepare("SELECT COUNT(*) AS n FROM notes WHERE user_id = ?").bind(userId),
    db
      .prepare(
        `SELECT COUNT(*) AS n FROM notes
         WHERE user_id = ?1 AND date(created_at, ?2) = date('now', ?2)`,
      )
      .bind(userId, TZ_MODIFIER),
    db
      .prepare(
        `SELECT category, COUNT(*) AS count FROM notes
         WHERE user_id = ? GROUP BY category ORDER BY count DESC`,
      )
      .bind(userId),
    db
      .prepare(
        `WITH daily AS (
           SELECT DISTINCT date(created_at, ?2) AS day
           FROM notes WHERE user_id = ?1
         ),
         consecutive AS (
           SELECT day,
                  julianday(day) - ROW_NUMBER() OVER (ORDER BY day) AS grp
           FROM daily
         )
         SELECT COUNT(*) AS n FROM consecutive
         WHERE grp = (SELECT grp FROM consecutive ORDER BY day DESC LIMIT 1)`,
      )
      .bind(userId, TZ_MODIFIER),
  ]);
  return {
    total: Number(total.results[0]?.n ?? 0),
    today: Number(today.results[0]?.n ?? 0),
    byCategory: byCategory.results as { category: string; count: number }[],
    streak: Number(streak.results[0]?.n ?? 0),
  };
}

/** Dùng cho /admin/reindex — duyệt toàn bộ ghi chú theo id. */
export async function getNotesAfterId(db: D1Database, afterId: number, limit: number): Promise<Note[]> {
  const { results } = await db
    .prepare(`SELECT ${COLS} FROM notes WHERE id > ? ORDER BY id LIMIT ?`)
    .bind(afterId, limit)
    .all<NoteRow>();
  return results.map(rowToNote);
}
