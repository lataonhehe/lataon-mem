import logging
from telegram import Update
from telegram.ext import ContextTypes
from db.models import Note
from db.queries import save_note
from ai.classifier import classify_note
from ai.socratic import generate_question, continue_deep_dive
from bot.state import get_state, set_last_note, set_mode, UserMode

logger = logging.getLogger(__name__)

MAX_SUMMARY_LEN = 120


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = get_state(user_id)
    pool = context.bot_data["pool"]

    await update.message.chat.send_action("typing")

    # Nếu đang chờ trả lời Socratic → đào sâu tiếp, không lưu ghi chú
    if state.mode == UserMode.AWAITING_REPLY:
        follow_up = await continue_deep_dive(
            original=state.last_note_content,
            category=state.last_category,
            user_reply=text,
        )
        await update.message.reply_text(f"🤔 {follow_up}")
        set_mode(user_id, UserMode.IDLE)
        return

    # 1. Phân loại
    classification = await classify_note(text)
    category = classification.get("category", "other")
    tags = classification.get("tags", [])
    summary = classification.get("summary", text[:MAX_SUMMARY_LEN])

    if len(summary) > MAX_SUMMARY_LEN:
        summary = summary[:MAX_SUMMARY_LEN].rsplit(" ", 1)[0] + "…"

    # 2. Lưu DB
    note = Note(
        content=text,
        category=category,
        tags=tags,
        summary=summary,
        user_id=user_id,
    )
    note_id = await save_note(pool, note)
    set_last_note(user_id, note_id, text, category)

    # 3. Xác nhận
    tags_display = " ".join(f"#{t}" for t in tags) if tags else ""
    confirm = f"Đã lưu [{category}] {tags_display}\n_{summary}_"
    await update.message.reply_text(confirm, parse_mode="Markdown")

    # 4. Hỏi Socratic
    question = await generate_question(text, category)
    await update.message.reply_text(f"🤔 {question}")
    set_mode(user_id, UserMode.AWAITING_REPLY)
