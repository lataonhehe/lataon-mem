from telegram import Update
from telegram.ext import ContextTypes
from db.models import Note
from db.queries import save_note
from ai.classifier import classify_note
from ai.socratic import generate_question
from bot.state import get_state, set_last_note, UserMode


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = get_state(user_id)

    await update.message.chat.send_action("typing")

    # 1. Phân loại ghi chú bằng Claude
    classification = await classify_note(text)
    category = classification.get("category", "other")
    tags = classification.get("tags", [])
    summary = classification.get("summary", text[:80])

    # 2. Lưu vào DB
    note = Note(
        content=text,
        category=category,
        tags=tags,
        summary=summary,
        user_id=user_id,
    )
    note_id = await save_note(note)
    set_last_note(user_id, note_id, text)

    # 3. Xác nhận lưu
    tags_display = " ".join(f"#{t}" for t in tags) if tags else ""
    confirm = f"Đã lưu [{category}] {tags_display}\n_{summary}_"
    await update.message.reply_text(confirm, parse_mode="Markdown")

    # 4. Gửi câu hỏi Socratic
    question = await generate_question(text, category)
    await update.message.reply_text(f"🤔 {question}")
