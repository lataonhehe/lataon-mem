import logging
from telegram import Update
from telegram.ext import ContextTypes
from db.models import Note
from db.queries import save_note
from ai.classifier import classify_note
from ai.socratic import generate_question, continue_deep_dive, deep_dive_topic
from bot.state import get_state, set_last_note, set_mode, reset, UserMode

logger = logging.getLogger(__name__)
MAX_SUMMARY_LEN = 120
MAX_DEEP_TURNS = 5


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = get_state(user_id)
    pool = context.bot_data["pool"]

    await update.message.chat.send_action("typing")

    # --- DEEP DIVE mode ---
    if state.mode == UserMode.DEEP_DIVE:
        state.deep_history.append({"role": "user", "content": text})
        if state.deep_turns >= MAX_DEEP_TURNS:
            await update.message.reply_text(
                "✅ Đã đào sâu 5 lượt. Ghi lại những gì bạn vừa khám phá nhé!"
            )
            reset(user_id)
            return
        question = await deep_dive_topic(
            state.deep_topic, state.deep_turns + 1, state.deep_history
        )
        state.deep_history.append({"role": "assistant", "content": question})
        state.deep_turns += 1
        suffix = (
            f"\n\n_(lượt {state.deep_turns}/{MAX_DEEP_TURNS})_"
            if state.deep_turns < MAX_DEEP_TURNS
            else "\n\n_(lượt cuối)_"
        )
        await update.message.reply_text(f"🤔 {question}{suffix}", parse_mode="Markdown")
        return

    # --- QUIZ mode ---
    if state.mode == UserMode.QUIZ:
        await update.message.reply_text(
            f"💡 Câu trả lời của bạn đã được ghi nhận.\n\n"
            f"Nội dung gốc:\n_{state.quiz_note.summary}_",
            parse_mode="Markdown",
        )
        reset(user_id)
        return

    # --- AWAITING_REPLY mode (Socratic follow-up) ---
    if state.mode == UserMode.AWAITING_REPLY:
        follow_up = await continue_deep_dive(
            original=state.last_note_content,
            category=state.last_category,
            user_reply=text,
        )
        await update.message.reply_text(f"🤔 {follow_up}")
        set_mode(user_id, UserMode.IDLE)
        return

    # --- IDLE: ghi chú mới ---
    classification = await classify_note(text)
    category = classification.get("category", "other")
    tags = classification.get("tags", [])
    summary = classification.get("summary", text[:MAX_SUMMARY_LEN])

    if len(summary) > MAX_SUMMARY_LEN:
        summary = summary[:MAX_SUMMARY_LEN].rsplit(" ", 1)[0] + "…"

    note = Note(
        content=text, category=category, tags=tags, summary=summary, user_id=user_id
    )
    note_id = await save_note(pool, note)
    set_last_note(user_id, note_id, text, category)

    tags_display = " ".join(f"#{t}" for t in tags) if tags else ""
    confirm = f"Đã lưu `#{note_id}` [{category}] {tags_display}\n_{summary}_"
    await update.message.reply_text(confirm, parse_mode="Markdown")

    question = await generate_question(text, category)
    await update.message.reply_text(f"🤔 {question}")
    set_mode(user_id, UserMode.AWAITING_REPLY)
