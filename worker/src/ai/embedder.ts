// Workers AI — đa ngôn ngữ, hỗ trợ tiếng Việt
export const EMBEDDING_MODEL = "@cf/baai/bge-m3";
export const EMBEDDING_DIM = 1024;

// bge-m3 nhận tối đa 8192 token; cắt bớt để an toàn với ghi chú rất dài
const MAX_CHARS = 8000;

/** Tạo embedding cho nhiều text cùng lúc. */
export async function embedBatch(env: Env, texts: string[]): Promise<number[][]> {
  if (texts.length === 0) return [];
  const res = (await env.AI.run(EMBEDDING_MODEL, {
    text: texts.map((t) => t.slice(0, MAX_CHARS)),
  })) as { data?: number[][] };
  if (!res.data || res.data.length !== texts.length) {
    throw new Error(`Embedding trả về ${res.data?.length ?? 0}/${texts.length} vector`);
  }
  return res.data;
}

export async function embedText(env: Env, text: string): Promise<number[]> {
  return (await embedBatch(env, [text]))[0];
}
