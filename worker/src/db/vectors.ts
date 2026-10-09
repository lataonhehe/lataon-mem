import type { Note } from "../types";
import { embedBatch, embedText } from "../ai/embedder";

// Vectorize chỉ lưu vector + metadata để lọc; nội dung đọc lại từ D1
function toVector(note: Note, values: number[]): VectorizeVector {
  return {
    id: String(note.id),
    values,
    metadata: { user_id: note.userId, category: note.category },
  };
}

/** Lưu hoặc cập nhật embedding của 1 ghi chú. */
export async function upsertNoteVector(env: Env, note: Note): Promise<void> {
  const values = await embedText(env, note.content);
  await env.VECTORS.upsert([toVector(note, values)]);
}

export async function upsertNoteVectors(env: Env, notes: Note[]): Promise<void> {
  if (notes.length === 0) return;
  const values = await embedBatch(env, notes.map((n) => n.content));
  await env.VECTORS.upsert(notes.map((n, i) => toVector(n, values[i])));
}

export interface SimilarMatch {
  noteId: number;
  score: number; // cosine similarity
}

/** Tìm topK ghi chú tương tự nhất của user. */
export async function querySimilar(
  env: Env,
  userId: number,
  query: string,
  topK = 5,
): Promise<SimilarMatch[]> {
  const values = await embedText(env, query);
  const res = await env.VECTORS.query(values, {
    topK,
    filter: { user_id: userId },
  });
  return res.matches.map((m) => ({ noteId: Number(m.id), score: m.score }));
}

/** Xóa embedding của 1 ghi chú. */
export async function deleteNoteVector(env: Env, noteId: number): Promise<void> {
  await env.VECTORS.deleteByIds([String(noteId)]);
}
