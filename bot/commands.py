from telegram import Update
from telegram.ext import ContextTypes
from db.queries import get_recent_notes, search_notes


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Chào! Mình là bot ghi chú thông minh.\n\n"
        "Chỉ cần nhắn bất kỳ điều bạn học được — mình sẽ tự phân loại và lưu lại.\n\n"
        "Lệnh:\n"
        "  /list — xem 5 ghi chú gần nhất\n"
        "  /search [từ khóa] — tìm kiếm ghi chú\n"
        "  /help — hiện menu này"
    )
    await update.message.reply_text(text)


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pool = context.bot_data["pool"]
    notes = await get_recent_notes(pool, user_id, limit=5)
    if not notes:
        await update.message.reply_text("Chưa có ghi chú nào. Hãy nhắn điều gì đó!")
        return

    lines = []
    for n in notes:
        tags = f" #{' #'.join(n.tags)}" if n.tags else ""
        lines.append(f"[{n.category}]{tags}\n{n.summary}\n")

    await update.message.reply_text("\n".join(lines))


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pool = context.bot_data["pool"]
    keyword = " ".join(context.args)
    if not keyword:
        await update.message.reply_text("Dùng: /search [từ khóa]")
        return

    notes = await search_notes(pool, user_id, keyword)
    if not notes:
        await update.message.reply_text(f"Không tìm thấy ghi chú nào về '{keyword}'.")
        return

    lines = [f"Tìm thấy {len(notes)} ghi chú cho '{keyword}':\n"]
    for n in notes:
        lines.append(f"[{n.category}] {n.summary}")
    await update.message.reply_text("\n".join(lines))
