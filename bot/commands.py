import io
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from db.queries import (
    get_recent_notes,
    get_today_notes,
    get_notes_by_category,
    search_notes,
    get_note_by_id,
    delete_note,
    update_note,
    get_random_note,
    get_stats,
)
from ai.socratic import deep_dive_topic, generate_quiz, generate_summary
from bot.state import get_state, set_mode, UserMode

VALID_CATEGORIES = [
    "it",
    "knowledge",
    "diary",
    "book",
    "idea",
    "health",
    "finance",
    "other",
]


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Chào! Mình là bot ghi chú thông minh.\n\n"
        "Nhắn bất kỳ điều gì để lưu ghi chú.\n\n"
        "*Quản lý ghi chú*\n"
        "  /list — 5 ghi chú gần nhất\n"
        "  /today — ghi chú hôm nay\n"
        "  /cat [category] — lọc theo loại\n"
        "  /search [từ khóa] — tìm kiếm\n"
        "  /delete [id] — xóa ghi chú\n"
        "  /edit [id] [nội dung] — sửa ghi chú\n\n"
        "*Đào sâu & ôn tập*\n"
        "  /deep [chủ đề] — Socratic 5 lượt\n"
        "  /review — ôn 1 ghi chú ngẫu nhiên\n"
        "  /quiz — kiểm tra kiến thức\n\n"
        "*Thống kê*\n"
        "  /stats — tổng quan học tập\n"
        "  /summary — tóm tắt hôm nay\n"
        "  /export — xuất file Markdown\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


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
        await update.message.reply_text(
            f"Category không hợp lệ. Chọn: {', '.join(VALID_CATEGORIES)}"
        )
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
    deleted = await delete_note(pool, update.effective_user.id, note_id)
    if deleted:
        await update.message.reply_text(f"Đã xóa ghi chú #{note_id}.")
    else:
        await update.message.reply_text("Xóa thất bại, thử lại.")


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
    updated = await update_note(pool, update.effective_user.id, note_id, new_content)
    if updated:
        await update.message.reply_text(f"Đã cập nhật ghi chú #{note_id}.")
    else:
        await update.message.reply_text("Cập nhật thất bại, thử lại.")


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
    question = await deep_dive_topic(topic, turn=1, history=[])
    state.deep_history.append({"role": "assistant", "content": question})
    state.deep_turns = 1
    set_mode(user_id, UserMode.DEEP_DIVE)
    await update.message.reply_text(
        f"🔍 *Deep dive: {topic}*\n\n🤔 {question}", parse_mode="Markdown"
    )


async def cmd_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = context.bot_data["pool"]
    note = await get_random_note(pool, update.effective_user.id)
    if not note:
        await update.message.reply_text("Chưa có ghi chú nào để ôn tập.")
        return
    date_str = note.created_at.strftime("%d/%m/%Y") if note.created_at else ""
    tags = f" #{' #'.join(note.tags)}" if note.tags else ""
    text = (
        f"📖 *Ôn lại ghi chú #{note.id}* ({date_str})\n"
        f"[{note.category}]{tags}\n\n"
        f"{note.content}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


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
        f"🧠 *Quiz [{note.category}]*\n\n{question}", parse_mode="Markdown"
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = context.bot_data["pool"]
    stats = await get_stats(pool, update.effective_user.id)
    cat_lines = (
        "\n".join(f"  {cat}: {count}" for cat, count in stats["by_category"].items())
        or "  (chưa có)"
    )
    text = (
        f"📊 *Thống kê của bạn*\n\n"
        f"Tổng ghi chú: {stats['total']}\n"
        f"Hôm nay: {stats['today']}\n"
        f"Streak: {stats['streak']} ngày\n\n"
        f"*Theo category:*\n{cat_lines}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


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
    lines = [
        f"# Knowledge Base\n\nXuất lúc: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
    ]
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
    file.name = f"knowledge_{datetime.now().strftime('%Y%m%d')}.md"
    await update.message.reply_document(document=file, filename=file.name)
