import io
from datetime import datetime
from telegram import Update
from telegram.helpers import escape_markdown
from telegram.ext import ContextTypes
from db.queries import (
    get_recent_notes, get_today_notes, get_notes_by_category,
    search_notes, get_note_by_id, delete_note, update_note,
    get_random_note, get_stats, save_note,
)
from db.models import Note
from ai.classifier import classify_note
from ai.socratic import generate_quiz, generate_summary, generate_first_question, start_deep_dive
from ai.embedder import embed_text
from db.vector_store import query_similar, delete_note as vector_delete
from bot.state import get_state, set_mode, set_last_note, reset, UserMode, SOCRATIC_MAX_TURNS

VALID_CATEGORIES = ["it", "knowledge", "diary", "book", "idea", "health", "finance", "other"]
MAX_SUMMARY_LEN = 120
DEEP_MAX_TURNS = 5



async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bật/tắt Socratic tự động sau khi lưu ghi chú."""
    user_id = update.effective_user.id
    state = get_state(user_id)

    if context.args and context.args[0].lower() in ("on", "off"):
        state.socratic_enabled = context.args[0].lower() == "on"
    else:
        # Toggle nếu không có arg
        state.socratic_enabled = not state.socratic_enabled

    status = "✅ bật" if state.socratic_enabled else "⏸ tắt"
    await update.message.reply_text(
        f"Socratic tự động: *{status}*\n\n"
        f"{'Sau mỗi ghi chú mình sẽ hỏi đào sâu.' if state.socratic_enabled else 'Mình sẽ chỉ lưu ghi chú, không hỏi thêm. Dùng /deep để đào sâu thủ công.'}",
        parse_mode="Markdown",
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Chào! Mình là bot ghi chú thông minh.\n\n"
        "Nhắn bất kỳ điều gì để lưu ghi chú.\n\n"
        "*Quản lý ghi chú*\n"
        "  /list — 5 ghi chú gần nhất\n"
        "  /today — ghi chú hôm nay\n"
        "  /cat \\[category\\] — lọc theo loại\n"
        "  /search \\[từ khóa\\] — tìm kiếm\n"
        "  /delete \\[id\\] — xóa ghi chú\n"
        "  /edit \\[id\\] \\[nội dung\\] — sửa ghi chú\n\n"
        "*Đào sâu & ôn tập*\n"
        "  /deep \\[chủ đề\\] — Socratic 5 lượt\n"
        "  /review — ôn 1 ghi chú ngẫu nhiên\n"
        "  /quiz — kiểm tra kiến thức\n"
        "  /done — kết thúc luồng đang chạy\n"
        "  /mode — bật/tắt Socratic tự động\n"
        "  /skip — bỏ qua đào sâu hiện tại\n\n"
        "*Thống kê*\n"
        "  /stats — tổng quan học tập\n"
        "  /summary — tóm tắt hôm nay\n"
        "  /export — xuất file Markdown\n"
    )
    escaped_text = escape_markdown(text, version=2)
    await update.message.reply_text(escaped_text, parse_mode="MarkdownV2")

async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = context.bot_data["pool"]
    notes = await get_recent_notes(pool, update.effective_user.id, limit=5)
    if not notes:
        await update.message.reply_text("Chưa có ghi chú nào. Hãy nhắn điều gì đó!")
        return
    lines = []
    for n in notes:
        tags = f" #{' #'.join(n.tags)}" if n.tags else ""
        lines.append(f"`#{n.id}` [{n.category}]{tags}\n{n.summary}")
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = context.bot_data["pool"]
    notes = await get_today_notes(pool, update.effective_user.id)
    if not notes:
        await update.message.reply_text("Hôm nay chưa có ghi chú nào.")
        return
    lines = [f"Hôm nay — {len(notes)} ghi chú:\n"]
    for n in notes:
        tags = f" #{' #'.join(n.tags)}" if n.tags else ""
        lines.append(f"`#{n.id}` [{n.category}]{tags}\n{n.summary}")
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")


async def cmd_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = context.bot_data["pool"]
    if not context.args:
        cats = " · ".join(VALID_CATEGORIES)
        await update.message.reply_text(f"Dùng: /cat [category]\n\nCác loại: {cats}")
        return
    category = context.args[0].lower()
    if category not in VALID_CATEGORIES:
        await update.message.reply_text(f"Category không hợp lệ. Chọn: {', '.join(VALID_CATEGORIES)}")
        return
    notes = await get_notes_by_category(pool, update.effective_user.id, category)
    if not notes:
        await update.message.reply_text(f"Chưa có ghi chú nào trong [{category}].")
        return
    lines = [f"[{category}] — {len(notes)} ghi chú:\n"]
    for n in notes:
        lines.append(f"`#{n.id}` {n.summary}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = context.bot_data["pool"]
    keyword = " ".join(context.args)
    if not keyword:
        await update.message.reply_text("Dùng: /search [từ khóa]")
        return
    notes = await search_notes(pool, update.effective_user.id, keyword)
    if not notes:
        await update.message.reply_text(f"Không tìm thấy ghi chú nào về '{keyword}'.")
        return
    lines = [f"Tìm thấy {len(notes)} kết quả cho '{keyword}':\n"]
    for n in notes:
        lines.append(f"`#{n.id}` [{n.category}] {n.summary}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = context.bot_data["pool"]
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Dùng: /delete [id]")
        return
    note_id = int(context.args[0])
    note = await get_note_by_id(pool, update.effective_user.id, note_id)
    if not note:
        await update.message.reply_text(f"Không tìm thấy ghi chú #{note_id}.")
        return
    await delete_note(pool, update.effective_user.id, note_id)
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, vector_delete, note_id)
    await update.message.reply_text(f"Đã xóa ghi chú #{note_id}.")


async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = context.bot_data["pool"]
    if not context.args or not context.args[0].isdigit() or len(context.args) < 2:
        await update.message.reply_text("Dùng: /edit [id] [nội dung mới]")
        return
    note_id = int(context.args[0])
    new_content = " ".join(context.args[1:])
    note = await get_note_by_id(pool, update.effective_user.id, note_id)
    if not note:
        await update.message.reply_text(f"Không tìm thấy ghi chú #{note_id}.")
        return
    await update_note(pool, update.effective_user.id, note_id, new_content)
    await update.message.reply_text(f"Đã cập nhật ghi chú #{note_id}.")


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kết thúc luồng đang chạy, lưu ghi chú nháp nếu có."""
    user_id = update.effective_user.id
    pool = context.bot_data["pool"]
    state = get_state(user_id)

    if state.mode == UserMode.IDLE:
        await update.message.reply_text("Không có luồng nào đang chạy.")
        return

    pending = state.pending_note_text
    reset(user_id)

    if pending:
        await update.message.chat.send_action("typing")
        classification = await classify_note(pending)
        category = classification.get("category", "other")
        tags = classification.get("tags", [])
        summary = classification.get("summary", pending[:MAX_SUMMARY_LEN])
        note = Note(content=pending, category=category, tags=tags, summary=summary, user_id=user_id)
        note_id = await save_note(pool, note)
        tags_display = " ".join(f"#{t}" for t in tags) if tags else ""
        await update.message.reply_text(
            f"✅ Kết thúc luồng.\n\nĐã lưu ghi chú nháp:\n`#{note_id}` [{category}] {tags_display}\n_{summary}_",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("✅ Kết thúc luồng. Nhắn ghi chú tiếp theo nhé!")


async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bỏ qua đào sâu, lưu ghi chú nháp ngay và về IDLE."""
    user_id = update.effective_user.id
    pool = context.bot_data["pool"]
    state = get_state(user_id)

    if state.mode not in (UserMode.SOCRATIC, UserMode.DEEP_DIVE, UserMode.CONFLICT):
        await update.message.reply_text("Không có luồng nào đang chạy.")
        return

    pending = state.pending_note_text
    reset(user_id)

    if pending:
        await update.message.chat.send_action("typing")
        classification = await classify_note(pending)
        category = classification.get("category", "other")
        tags = classification.get("tags", [])
        summary = classification.get("summary", pending[:MAX_SUMMARY_LEN])
        note = Note(content=pending, category=category, tags=tags, summary=summary, user_id=user_id)
        note_id = await save_note(pool, note)
        tags_display = " ".join(f"#{t}" for t in tags) if tags else ""
        await update.message.reply_text(
            f"Đã lưu `#{note_id}` [{category}] {tags_display}\n_{summary}_",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("Đã bỏ qua đào sâu.")


async def cmd_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lưu nháp và tiếp tục luồng đào sâu."""
    user_id = update.effective_user.id
    pool = context.bot_data["pool"]
    state = get_state(user_id)

    if state.mode != UserMode.CONFLICT or not state.pending_note_text:
        await update.message.reply_text("Không có ghi chú nháp nào.")
        return

    pending = state.pending_note_text
    prev_mode = state.prev_mode or UserMode.IDLE

    await update.message.chat.send_action("typing")
    classification = await classify_note(pending)
    category = classification.get("category", "other")
    tags = classification.get("tags", [])
    summary = classification.get("summary", pending[:MAX_SUMMARY_LEN])
    note = Note(content=pending, category=category, tags=tags, summary=summary, user_id=user_id)
    note_id = await save_note(pool, note)
    tags_display = " ".join(f"#{t}" for t in tags) if tags else ""

    state.pending_note_text = None
    state.mode = prev_mode

    # Gửi confirm + resume câu hỏi cũ
    last_question = ""
    if prev_mode == UserMode.SOCRATIC and state.socratic_history:
        last_question = state.socratic_history[-1].get("content", "")
    elif prev_mode == UserMode.DEEP_DIVE and state.deep_history:
        last_question = state.deep_history[-1].get("content", "")

    msg = f"📌 Đã lưu nháp `#{note_id}` [{category}] {tags_display}\n_{summary}_"
    if last_question:
        msg += f"\n\nTiếp tục đào sâu:\n🤔 {last_question}"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hủy ghi chú nháp, tiếp tục luồng đào sâu."""
    user_id = update.effective_user.id
    state = get_state(user_id)

    if state.mode != UserMode.CONFLICT:
        await update.message.reply_text("Không có gì để hủy.")
        return

    prev_mode = state.prev_mode or UserMode.IDLE
    state.pending_note_text = None
    state.mode = prev_mode

    last_question = ""
    if prev_mode == UserMode.SOCRATIC and state.socratic_history:
        last_question = state.socratic_history[-1].get("content", "")
    elif prev_mode == UserMode.DEEP_DIVE and state.deep_history:
        last_question = state.deep_history[-1].get("content", "")

    msg = "Đã hủy ghi chú nháp."
    if last_question:
        msg += f"\n\nTiếp tục đào sâu:\n🤔 {last_question}"
    await update.message.reply_text(msg)



async def cmd_recall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tìm kiếm ngữ nghĩa bằng embedding."""
    pool = context.bot_data["pool"]
    user_id = update.effective_user.id
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Dùng: /recall [chủ đề hoặc câu hỏi]")
        return

    await update.message.chat.send_action("typing")
    import asyncio
    loop = asyncio.get_event_loop()
    query_embedding = await embed_text(query)
    results = await loop.run_in_executor(
        None, query_similar, query_embedding, user_id, 5
    )

    if not results:
        await update.message.reply_text(
            "Chưa tìm thấy ghi chú nào liên quan.\n"
            "Lưu ý: /recall dùng semantic search, cần có ghi chú đã được lưu."
        )
        return

    lines = [f"🔍 Top {len(results)} ghi chú liên quan đến *{query}*:\n"]
    for r in results:
        score = round((1 - r["distance"]) * 100)
        cat = r["metadata"].get("category", "?")
        preview = r["content"][:120].replace("\n", " ")
        if len(r["content"]) > 120:
            preview += "…"
        lines.append(f"`#{r['note_id']}` [{cat}] _{score}% match_\n{preview}")

    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")


async def cmd_soc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bật Socratic mode."""
    user_id = update.effective_user.id
    state = get_state(user_id)
    state.socratic_enabled = True
    await update.message.reply_text(
        "✅ Socratic bật — bot sẽ hỏi đào sâu sau mỗi ghi chú."
    )


async def cmd_nosoc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tắt Socratic mode."""
    user_id = update.effective_user.id
    state = get_state(user_id)
    state.socratic_enabled = False
    # Nếu đang trong luồng Socratic thì reset luôn
    if state.mode == UserMode.SOCRATIC:
        from bot.state import reset
        reset(user_id)
        state = get_state(user_id)
        state.socratic_enabled = False
    await update.message.reply_text(
        "🔕 Socratic tắt — bot chỉ lưu ghi chú, không hỏi thêm. Dùng /soc để bật lại."
    )

async def cmd_deep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    topic = " ".join(context.args)
    if not topic:
        await update.message.reply_text("Dùng: /deep [chủ đề muốn đào sâu]")
        return
    state = get_state(user_id)
    state.deep_topic = topic
    state.deep_history = []
    state.deep_turns = 0
    question = await start_deep_dive(topic)
    state.deep_history.append({"role": "assistant", "content": question})
    set_mode(user_id, UserMode.DEEP_DIVE)
    await update.message.reply_text(
        f"🔍 *Deep dive: {topic}*\n\n🤔 {question}\n\n_(1/{DEEP_MAX_TURNS} lượt · /done để kết thúc)_",
        parse_mode="Markdown",
    )


async def cmd_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = context.bot_data["pool"]
    note = await get_random_note(pool, update.effective_user.id)
    if not note:
        await update.message.reply_text("Chưa có ghi chú nào để ôn tập.")
        return
    date_str = note.created_at.strftime("%d/%m/%Y") if note.created_at else ""
    tags = f" #{' #'.join(note.tags)}" if note.tags else ""
    await update.message.reply_text(
        f"📖 *Ôn lại #{note.id}* ({date_str})\n[{note.category}]{tags}\n\n{note.content}",
        parse_mode="Markdown",
    )


async def cmd_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = context.bot_data["pool"]
    user_id = update.effective_user.id
    note = await get_random_note(pool, user_id)
    if not note:
        await update.message.reply_text("Chưa có ghi chú nào để quiz.")
        return
    state = get_state(user_id)
    state.quiz_note = note
    question = await generate_quiz(note.content, note.category)
    set_mode(user_id, UserMode.QUIZ)
    await update.message.reply_text(
        f"🧠 *Quiz [{note.category}]*\n\n{question}",
        parse_mode="Markdown",
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = context.bot_data["pool"]
    stats = await get_stats(pool, update.effective_user.id)
    cat_lines = "\n".join(f"  {cat}: {count}" for cat, count in stats["by_category"].items()) or "  (chưa có)"
    await update.message.reply_text(
        f"📊 *Thống kê*\n\n"
        f"Tổng ghi chú: {stats['total']}\n"
        f"Hôm nay: {stats['today']}\n"
        f"Streak: {stats['streak']} ngày\n\n"
        f"*Theo category:*\n{cat_lines}",
        parse_mode="Markdown",
    )


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = context.bot_data["pool"]
    notes = await get_today_notes(pool, update.effective_user.id)
    if not notes:
        await update.message.reply_text("Hôm nay chưa có ghi chú nào.")
        return
    await update.message.chat.send_action("typing")
    notes_text = "\n\n".join(f"[{n.category}] {n.content}" for n in notes)
    summary = await generate_summary(notes_text)
    await update.message.reply_text(
        f"📝 *Tóm tắt hôm nay ({len(notes)} ghi chú):*\n\n{summary}",
        parse_mode="Markdown",
    )


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = context.bot_data["pool"]
    notes = await get_recent_notes(pool, update.effective_user.id, limit=200)
    if not notes:
        await update.message.reply_text("Chưa có ghi chú nào để xuất.")
        return
    lines = [f"# Knowledge Base\n\nXuất lúc: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"]
    current_cat = None
    for n in sorted(notes, key=lambda x: x.category):
        if n.category != current_cat:
            current_cat = n.category
            lines.append(f"\n## {current_cat}\n")
        date_str = n.created_at.strftime("%d/%m/%Y") if n.created_at else ""
        tags = f" · #{' #'.join(n.tags)}" if n.tags else ""
        lines.append(f"### #{n.id} — {date_str}{tags}\n{n.content}\n")
    content = "\n".join(lines)
    file = io.BytesIO(content.encode("utf-8"))
    filename = f"knowledge_{datetime.now().strftime('%Y%m%d')}.md"
    await update.message.reply_document(document=file, filename=filename)