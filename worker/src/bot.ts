import { Bot, Context, GrammyError, InputFile } from "grammy";
import type { Note, UserState } from "./types";
import {
  DEEP_MAX_TURNS,
  MAX_SUMMARY_LEN,
  SOCRATIC_MAX_TURNS,
  VALID_CATEGORIES,
  newState,
} from "./types";
import {
  classifyNote,
  continueDeepDive,
  continueSocratic,
  generateFirstQuestion,
  generateQuiz,
  generateSummary,
  startDeepDive,
} from "./ai/llm";
import {
  deleteNote,
  getNoteById,
  getNotesByCategory,
  getNotesByIds,
  getRandomNote,
  getRecentNotes,
  getStats,
  getTodayNotes,
  saveNote,
  searchNotes,
  updateNote,
} from "./db/queries";
import { deleteNoteVector, querySimilar, upsertNoteVector } from "./db/vectors";

/** State của 1 user — do UserSession (Durable Object) nắm giữ và lưu lại. */
export interface StateHolder {
  state: UserState;
}

const CONFLICT_MSG =
  "Bạn đang trong luồng đào sâu. Chọn:\n\n" +
  "/save — lưu nháp, tiếp tục đào sâu sau\n" +
  "/skip — bỏ đào sâu, lưu ghi chú ngay\n" +
  "/done — kết thúc đào sâu, lưu ghi chú ngay";

const HELP_TEXT =
  "Chào! Mình là bot ghi chú thông minh.\n\n" +
  "Nhắn bất kỳ điều gì để lưu ghi chú.\n\n" +
  "<b>Quản lý ghi chú</b>\n" +
  "  /list — 5 ghi chú gần nhất\n" +
  "  /today — ghi chú hôm nay\n" +
  "  /cat [category] — lọc theo loại\n" +
  "  /search [từ khóa] — tìm kiếm\n" +
  "  /recall [chủ đề] — tìm theo ngữ nghĩa\n" +
  "  /delete [id] — xóa ghi chú\n" +
  "  /edit [id] [nội dung] — sửa ghi chú\n\n" +
  "<b>Đào sâu &amp; ôn tập</b>\n" +
  "  /deep [chủ đề] — Socratic 5 lượt\n" +
  "  /review — ôn 1 ghi chú ngẫu nhiên\n" +
  "  /quiz — kiểm tra kiến thức\n" +
  "  /done — kết thúc luồng đang chạy\n" +
  "  /mode — bật/tắt Socratic tự động\n" +
  "  /skip — bỏ qua đào sâu hiện tại\n\n" +
  "<b>Thống kê</b>\n" +
  "  /stats — tổng quan học tập\n" +
  "  /summary — tóm tắt hôm nay\n" +
  "  /export — xuất file Markdown\n";

export const BOT_COMMANDS = [
  { command: "help", description: "Hướng dẫn" },
  { command: "list", description: "5 ghi chú gần nhất" },
  { command: "today", description: "Ghi chú hôm nay" },
  { command: "cat", description: "Lọc theo loại" },
  { command: "search", description: "Tìm theo từ khóa" },
  { command: "recall", description: "Tìm theo ngữ nghĩa" },
  { command: "deep", description: "Đào sâu 1 chủ đề" },
  { command: "review", description: "Ôn 1 ghi chú ngẫu nhiên" },
  { command: "quiz", description: "Kiểm tra kiến thức" },
  { command: "done", description: "Kết thúc luồng đang chạy" },
  { command: "mode", description: "Bật/tắt Socratic tự động" },
  { command: "stats", description: "Thống kê" },
  { command: "summary", description: "Tóm tắt hôm nay" },
  { command: "export", description: "Xuất file Markdown" },
];

// ── Helpers ─────────────────────────────────────────────

/** Gửi Markdown; nếu nội dung user làm hỏng cú pháp thì gửi lại dạng text thường. */
async function reply(ctx: Context, text: string, markdown = true) {
  if (!markdown) return ctx.reply(text);
  try {
    return await ctx.reply(text, { parse_mode: "Markdown" });
  } catch (e) {
    if (e instanceof GrammyError && e.error_code === 400) return ctx.reply(text);
    throw e;
  }
}

function args(ctx: Context): string[] {
  const match = typeof ctx.match === "string" ? ctx.match : "";
  return match.trim().split(/\s+/).filter(Boolean);
}

function tagsInline(tags: string[]): string {
  return tags.length ? ` #${tags.join(" #")}` : "";
}

/** created_at (UTC) → dd/mm/yyyy theo giờ VN */
function fmtDate(createdAt: string): string {
  const d = new Date(createdAt.replace(" ", "T") + "Z");
  d.setUTCHours(d.getUTCHours() + 7);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getUTCDate())}/${p(d.getUTCMonth() + 1)}/${d.getUTCFullYear()}`;
}

function nowVN(): Date {
  const d = new Date();
  d.setUTCHours(d.getUTCHours() + 7);
  return d;
}

function truncateSummary(summary: string): string {
  if (summary.length <= MAX_SUMMARY_LEN) return summary;
  const cut = summary.slice(0, MAX_SUMMARY_LEN);
  const space = cut.lastIndexOf(" ");
  return (space > 0 ? cut.slice(0, space) : cut) + "…";
}

/** Phân loại + lưu D1 + lưu embedding. */
async function classifyAndSave(env: Env, userId: number, text: string): Promise<Note> {
  const c = await classifyNote(env, text);
  const note = await saveNote(env.DB, {
    userId,
    content: text,
    category: c.category,
    tags: c.tags,
    summary: truncateSummary(c.summary || text),
  });
  try {
    await upsertNoteVector(env, note);
  } catch (e) {
    // Ghi chú đã nằm trong D1; /admin/reindex có thể bù embedding sau
    console.error(`Upsert vector #${note.id} lỗi:`, e);
  }
  return note;
}

function noteLine(n: Note): string {
  return `\`#${n.id}\` [${n.category}]${tagsInline(n.tags)}\n_${n.summary}_`;
}

/**
 * Phát hiện ghi chú mới trong lúc đang Socratic/Deep.
 * Tiêu chí: text đủ dài VÀ ít từ chung với chủ đề đang đào sâu.
 */
function isNewNote(text: string, s: UserState): boolean {
  if (text.length < 40) return false; // quá ngắn → chắc là câu trả lời

  const words = (t: string) =>
    new Set(t.split(/\s+/).filter((w) => w.length > 3).map((w) => w.toLowerCase()));
  const topicWords = words(s.lastNoteContent || s.deepTopic || "");
  if (topicWords.size === 0) return false;

  const textWords = words(text);
  let overlap = 0;
  for (const w of topicWords) if (textWords.has(w)) overlap++;
  return overlap / topicWords.size < 0.15; // ít hơn 15% từ chung → ghi chú mới
}

function lastQuestion(s: UserState): string {
  const history = s.mode === "socratic" ? s.socraticHistory : s.mode === "deep_dive" ? s.deepHistory : [];
  return history.at(-1)?.content ?? "";
}

// ── Bot ─────────────────────────────────────────────────

export function createBot(env: Env, holder: StateHolder): Bot {
  const bot = new Bot(env.TELEGRAM_TOKEN);
  const db = env.DB;

  const reset = () => {
    holder.state = newState(holder.state.socraticEnabled); // giữ lại preference
  };

  bot.command(["start", "help"], (ctx) => ctx.reply(HELP_TEXT, { parse_mode: "HTML" }));

  bot.command("mode", async (ctx) => {
    const s = holder.state;
    const a = args(ctx)[0]?.toLowerCase();
    s.socraticEnabled = a === "on" || a === "off" ? a === "on" : !s.socraticEnabled;
    const status = s.socraticEnabled ? "✅ bật" : "⏸ tắt";
    const detail = s.socraticEnabled
      ? "Sau mỗi ghi chú mình sẽ hỏi đào sâu."
      : "Mình sẽ chỉ lưu ghi chú, không hỏi thêm. Dùng /deep để đào sâu thủ công.";
    await reply(ctx, `Socratic tự động: *${status}*\n\n${detail}`);
  });

  bot.command("soc", async (ctx) => {
    holder.state.socraticEnabled = true;
    await ctx.reply("✅ Socratic bật — bot sẽ hỏi đào sâu sau mỗi ghi chú.");
  });

  bot.command("nosoc", async (ctx) => {
    if (holder.state.mode === "socratic") reset();
    holder.state.socraticEnabled = false;
    await ctx.reply("🔕 Socratic tắt — bot chỉ lưu ghi chú, không hỏi thêm. Dùng /soc để bật lại.");
  });

  bot.command("list", async (ctx) => {
    const notes = await getRecentNotes(db, ctx.from!.id, 5);
    if (!notes.length) return ctx.reply("Chưa có ghi chú nào. Hãy nhắn điều gì đó!");
    await reply(ctx, notes.map(noteLine).join("\n\n"));
  });

  bot.command("today", async (ctx) => {
    const notes = await getTodayNotes(db, ctx.from!.id);
    if (!notes.length) return ctx.reply("Hôm nay chưa có ghi chú nào.");
    await reply(ctx, [`Hôm nay — ${notes.length} ghi chú:`, ...notes.map(noteLine)].join("\n\n"));
  });

  bot.command("cat", async (ctx) => {
    const category = args(ctx)[0]?.toLowerCase();
    if (!category) {
      return ctx.reply(`Dùng: /cat [category]\n\nCác loại: ${VALID_CATEGORIES.join(" · ")}`);
    }
    if (!(VALID_CATEGORIES as readonly string[]).includes(category)) {
      return ctx.reply(`Category không hợp lệ. Chọn: ${VALID_CATEGORIES.join(", ")}`);
    }
    const notes = await getNotesByCategory(db, ctx.from!.id, category);
    if (!notes.length) return ctx.reply(`Chưa có ghi chú nào trong [${category}].`);
    const lines = notes.map((n) => `\`#${n.id}\` ${n.summary}`);
    await reply(ctx, [`[${category}] — ${notes.length} ghi chú:\n`, ...lines].join("\n"));
  });

  bot.command("search", async (ctx) => {
    const keyword = args(ctx).join(" ");
    if (!keyword) return ctx.reply("Dùng: /search [từ khóa]");
    const notes = await searchNotes(db, ctx.from!.id, keyword);
    if (!notes.length) return ctx.reply(`Không tìm thấy ghi chú nào về '${keyword}'.`);
    const lines = notes.map((n) => `\`#${n.id}\` [${n.category}] ${n.summary}`);
    await reply(ctx, [`Tìm thấy ${notes.length} kết quả cho '${keyword}':\n`, ...lines].join("\n"));
  });

  bot.command("recall", async (ctx) => {
    const query = args(ctx).join(" ");
    if (!query) return ctx.reply("Dùng: /recall [chủ đề hoặc câu hỏi]");
    await ctx.replyWithChatAction("typing");

    const userId = ctx.from!.id;
    const matches = await querySimilar(env, userId, query, 5);
    const notes = await getNotesByIds(db, userId, matches.map((m) => m.noteId));
    if (!notes.length) {
      return ctx.reply(
        "Chưa tìm thấy ghi chú nào liên quan.\n" +
          "Lưu ý: /recall dùng semantic search, cần có ghi chú đã được lưu.",
      );
    }

    const scores = new Map(matches.map((m) => [m.noteId, m.score]));
    const lines = [`🔍 Top ${notes.length} ghi chú liên quan đến *${query}*:\n`];
    for (const n of notes) {
      const score = Math.round((scores.get(n.id) ?? 0) * 100);
      let preview = n.content.slice(0, 120).replace(/\n/g, " ");
      if (n.content.length > 120) preview += "…";
      lines.push(`\`#${n.id}\` [${n.category}] _${score}% match_\n${preview}`);
    }
    await reply(ctx, lines.join("\n\n"));
  });

  bot.command("delete", async (ctx) => {
    const a = args(ctx)[0];
    if (!a || !/^\d+$/.test(a)) return ctx.reply("Dùng: /delete [id]");
    const noteId = Number(a);
    if (!(await deleteNote(db, ctx.from!.id, noteId))) {
      return ctx.reply(`Không tìm thấy ghi chú #${noteId}.`);
    }
    await deleteNoteVector(env, noteId);
    await ctx.reply(`Đã xóa ghi chú #${noteId}.`);
  });

  bot.command("edit", async (ctx) => {
    const m = (typeof ctx.match === "string" ? ctx.match : "").trim().match(/^(\d+)\s+([\s\S]+)$/);
    if (!m) return ctx.reply("Dùng: /edit [id] [nội dung mới]");
    const noteId = Number(m[1]);
    const newContent = m[2].trim();
    const note = await getNoteById(db, ctx.from!.id, noteId);
    if (!note) return ctx.reply(`Không tìm thấy ghi chú #${noteId}.`);
    await updateNote(db, note, newContent);
    await upsertNoteVector(env, { ...note, content: newContent });
    await ctx.reply(`Đã cập nhật ghi chú #${noteId}.`);
  });

  bot.command("done", async (ctx) => {
    const s = holder.state;
    if (s.mode === "idle") return ctx.reply("Không có luồng nào đang chạy.");
    const pending = s.pendingNoteText;
    reset();

    if (!pending) return ctx.reply("✅ Kết thúc luồng. Nhắn ghi chú tiếp theo nhé!");
    await ctx.replyWithChatAction("typing");
    const note = await classifyAndSave(env, ctx.from!.id, pending);
    await reply(ctx, `✅ Kết thúc luồng.\n\nĐã lưu ghi chú nháp:\n${noteLine(note)}`);
  });

  bot.command("skip", async (ctx) => {
    const s = holder.state;
    if (!["socratic", "deep_dive", "conflict"].includes(s.mode)) {
      return ctx.reply("Không có luồng nào đang chạy.");
    }
    const pending = s.pendingNoteText;
    reset();

    if (!pending) return ctx.reply("Đã bỏ qua đào sâu.");
    await ctx.replyWithChatAction("typing");
    const note = await classifyAndSave(env, ctx.from!.id, pending);
    await reply(ctx, `Đã lưu ${noteLine(note)}`);
  });

  bot.command("save", async (ctx) => {
    const s = holder.state;
    if (s.mode !== "conflict" || !s.pendingNoteText) return ctx.reply("Không có ghi chú nháp nào.");

    await ctx.replyWithChatAction("typing");
    const note = await classifyAndSave(env, ctx.from!.id, s.pendingNoteText);
    s.pendingNoteText = null;
    s.mode = s.prevMode ?? "idle";

    // Gửi confirm + resume câu hỏi cũ
    let msg = `📌 Đã lưu nháp ${noteLine(note)}`;
    const q = lastQuestion(s);
    if (q) msg += `\n\nTiếp tục đào sâu:\n🤔 ${q}`;
    await reply(ctx, msg);
  });

  bot.command("cancel", async (ctx) => {
    const s = holder.state;
    if (s.mode !== "conflict") return ctx.reply("Không có gì để hủy.");
    s.pendingNoteText = null;
    s.mode = s.prevMode ?? "idle";

    let msg = "Đã hủy ghi chú nháp.";
    const q = lastQuestion(s);
    if (q) msg += `\n\nTiếp tục đào sâu:\n🤔 ${q}`;
    await ctx.reply(msg);
  });

  bot.command("deep", async (ctx) => {
    const topic = args(ctx).join(" ");
    if (!topic) return ctx.reply("Dùng: /deep [chủ đề muốn đào sâu]");
    const s = holder.state;
    const question = await startDeepDive(env, topic);
    s.deepTopic = topic;
    s.deepHistory = [{ role: "assistant", content: question }];
    s.deepTurns = 0;
    s.mode = "deep_dive";
    await reply(
      ctx,
      `🔍 *Deep dive: ${topic}*\n\n🤔 ${question}\n\n_(1/${DEEP_MAX_TURNS} lượt · /done để kết thúc)_`,
    );
  });

  bot.command("review", async (ctx) => {
    const note = await getRandomNote(db, ctx.from!.id);
    if (!note) return ctx.reply("Chưa có ghi chú nào để ôn tập.");
    await reply(
      ctx,
      `📖 *Ôn lại #${note.id}* (${fmtDate(note.createdAt)})\n[${note.category}]${tagsInline(note.tags)}\n\n${note.content}`,
    );
  });

  bot.command("quiz", async (ctx) => {
    const note = await getRandomNote(db, ctx.from!.id);
    if (!note) return ctx.reply("Chưa có ghi chú nào để quiz.");
    const question = await generateQuiz(env, note.content, note.category);
    holder.state.quizNote = note;
    holder.state.mode = "quiz";
    await reply(ctx, `🧠 *Quiz [${note.category}]*\n\n${question}`);
  });

  bot.command("stats", async (ctx) => {
    const st = await getStats(db, ctx.from!.id);
    const catLines =
      st.byCategory.map((c) => `  ${c.category}: ${c.count}`).join("\n") || "  (chưa có)";
    await reply(
      ctx,
      `📊 *Thống kê*\n\n` +
        `Tổng ghi chú: ${st.total}\n` +
        `Hôm nay: ${st.today}\n` +
        `Streak: ${st.streak} ngày\n\n` +
        `*Theo category:*\n${catLines}`,
    );
  });

  bot.command("summary", async (ctx) => {
    const notes = await getTodayNotes(db, ctx.from!.id);
    if (!notes.length) return ctx.reply("Hôm nay chưa có ghi chú nào.");
    await ctx.replyWithChatAction("typing");
    const summary = await generateSummary(
      env,
      notes.map((n) => `[${n.category}] ${n.content}`).join("\n\n"),
    );
    await reply(ctx, `📝 *Tóm tắt hôm nay (${notes.length} ghi chú):*\n\n${summary}`);
  });

  bot.command("export", async (ctx) => {
    const notes = await getRecentNotes(db, ctx.from!.id, 200);
    if (!notes.length) return ctx.reply("Chưa có ghi chú nào để xuất.");

    const now = nowVN();
    const p = (n: number) => String(n).padStart(2, "0");
    const stamp = `${p(now.getUTCDate())}/${p(now.getUTCMonth() + 1)}/${now.getUTCFullYear()} ${p(now.getUTCHours())}:${p(now.getUTCMinutes())}`;
    const lines = [`# Knowledge Base\n\nXuất lúc: ${stamp}\n`];
    let currentCat: string | null = null;
    for (const n of [...notes].sort((a, b) => a.category.localeCompare(b.category))) {
      if (n.category !== currentCat) {
        currentCat = n.category;
        lines.push(`\n## ${currentCat}\n`);
      }
      const tags = n.tags.length ? ` · #${n.tags.join(" #")}` : "";
      lines.push(`### #${n.id} — ${fmtDate(n.createdAt)}${tags}\n${n.content}\n`);
    }
    const filename = `knowledge_${now.getUTCFullYear()}${p(now.getUTCMonth() + 1)}${p(now.getUTCDate())}.md`;
    await ctx.replyWithDocument(new InputFile(new TextEncoder().encode(lines.join("\n")), filename));
  });

  // ── Tin nhắn thường (không phải command) ──────────────
  bot.on("message:text", async (ctx) => {
    if (ctx.message.entities?.[0]?.type === "bot_command" && ctx.message.entities[0].offset === 0) {
      return; // command không tồn tại
    }
    const userId = ctx.from.id;
    const text = ctx.message.text.trim();
    const s = holder.state;

    await ctx.replyWithChatAction("typing");

    // ── QUIZ
    if (s.mode === "quiz") {
      await reply(ctx, `💡 Ghi nhận rồi!\n\nNội dung gốc:\n_${s.quizNote?.summary ?? ""}_`);
      reset();
      return;
    }

    // ── CONFLICT
    if (s.mode === "conflict") {
      await ctx.reply("Vui lòng chọn:\n/save · /skip · /done · /cancel");
      return;
    }

    // ── SOCRATIC
    if (s.mode === "socratic") {
      if (isNewNote(text, s)) {
        s.pendingNoteText = text;
        s.prevMode = "socratic";
        s.mode = "conflict";
        await ctx.reply(CONFLICT_MSG);
        return;
      }

      s.socraticHistory.push({ role: "user", content: text });
      s.socraticTurns += 1;

      if (s.socraticTurns >= SOCRATIC_MAX_TURNS) {
        await ctx.reply("✅ Đã đào sâu xong. Nhắn ghi chú tiếp theo nhé!");
        reset();
        return;
      }

      const question = await continueSocratic(env, s.socraticHistory);
      s.socraticHistory.push({ role: "assistant", content: question });
      await reply(ctx, `🤔 ${question}\n\n_(${s.socraticTurns}/${SOCRATIC_MAX_TURNS} · /done kết thúc)_`);
      return;
    }

    // ── DEEP DIVE
    if (s.mode === "deep_dive") {
      if (isNewNote(text, s)) {
        s.pendingNoteText = text;
        s.prevMode = "deep_dive";
        s.mode = "conflict";
        await ctx.reply(CONFLICT_MSG);
        return;
      }

      s.deepHistory.push({ role: "user", content: text });
      s.deepTurns += 1;

      if (s.deepTurns >= DEEP_MAX_TURNS) {
        await reply(ctx, `✅ Đã đào sâu ${DEEP_MAX_TURNS} lượt về *${s.deepTopic}*.`);
        reset();
        return;
      }

      const question = await continueDeepDive(env, s.deepHistory);
      s.deepHistory.push({ role: "assistant", content: question });
      await reply(ctx, `🤔 ${question}\n\n_(${s.deepTurns}/${DEEP_MAX_TURNS} · /done kết thúc)_`);
      return;
    }

    // ── IDLE: lưu ghi chú mới
    const note = await classifyAndSave(env, userId, text);
    s.lastNoteId = note.id;
    s.lastNoteContent = note.content;
    s.lastCategory = note.category;
    await reply(ctx, `Đã lưu ${noteLine(note)}`);

    // Chỉ hỏi Socratic nếu user bật
    if (s.socraticEnabled) {
      const question = await generateFirstQuestion(env, text, note.category);
      s.socraticHistory = [{ role: "assistant", content: question }];
      s.socraticTurns = 0;
      s.mode = "socratic";
      await reply(ctx, `🤔 ${question}\n\n_(1/${SOCRATIC_MAX_TURNS} · /done kết thúc · /nosoc tắt)_`);
    }
  });

  return bot;
}
