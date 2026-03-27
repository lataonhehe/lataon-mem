import logging
from telegram import Update
from telegram.ext import ContextTypes
from db.models import Note
from db.queries import save_note
from ai.classifier import classify_note
from ai.socratic import (
    generate_first_question,
    continue_socratic,
    continue_deep_dive,
)
from bot.state import (
    get_state,
    set_last_note,
    set_mode,
    reset,
    UserMode,
    SOCRATIC_MAX_TURNS,
)

logger = logging.getLogger(__name__)
MAX_SUMMARY_LEN = 120
DEEP_MAX_TURNS = 5

CONFLICT_MSG = (
    "Bạn đang trong luồng đào sâu. Chọn:\n\n"
    "/save — lưu nháp, tiếp tục đào sâu sau\n"
    "/skip — bỏ đào sâu, lưu ghi chú ngay\n"
    "/done — kết thúc đào sâu, lưu ghi chú ngay"
)


async def _save_note_flow(
    pool, user_id: int, text: str
) -> tuple[int, str, str, str, str]:
    """Phân loại và lưu ghi chú. Trả về (note_id, category, tags_display, summary, confirm_text)."""
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
    tags_display = " ".join(f"#{t}" for t in tags) if tags else ""
    confirm = f"Đã lưu `#{note_id}` [{category}] {tags_display}\n_{summary}_"
    return note_id, category, tags_display, summary, confirm


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = get_state(user_id)
    pool = context.bot_data["pool"]

    await update.message.chat.send_action("typing")

    # ── QUIZ mode ──────────────────────────────────────────────
    if state.mode == UserMode.QUIZ:
        await update.message.reply_text(
            f"💡 Ghi nhận rồi!\n\nNội dung gốc:\n_{state.quiz_note.summary}_",
            parse_mode="Markdown",
        )
        reset(user_id)
        return

    # ── CONFLICT mode (chờ /save /skip /done) ──────────────────
    if state.mode == UserMode.CONFLICT:
        await update.message.reply_text(
            "Vui lòng chọn:\n/save · /skip · /done\nhoặc /cancel để hủy.",
        )
        return

    # ── SOCRATIC mode ───────────────────────────────────────────
    if state.mode == UserMode.SOCRATIC:
        # Phát hiện ghi chú mới (dài hơn 20 ký tự và không giống câu trả lời ngắn)
        if len(text) > 20 and not _looks_like_answer(text, state):
            state.pending_note_text = text
            state.prev_mode = UserMode.SOCRATIC
            set_mode(user_id, UserMode.CONFLICT)
            await update.message.reply_text(CONFLICT_MSG)
            return

        # Tiếp tục Socratic
        state.socratic_history.append({"role": "user", "content": text})
        state.socratic_turns += 1

        if state.socratic_turns >= SOCRATIC_MAX_TURNS:
            await update.message.reply_text(
                "✅ Đã đào sâu xong. Nhắn ghi chú tiếp theo nhé!"
            )
            reset(user_id)
            return

        question = await continue_socratic(state.socratic_history, text)
        state.socratic_history.append({"role": "assistant", "content": question})
        turns_left = SOCRATIC_MAX_TURNS - state.socratic_turns
        suffix = f"\n\n_({state.socratic_turns}/{SOCRATIC_MAX_TURNS} lượt · /done để kết thúc)_"
        await update.message.reply_text(f"🤔 {question}{suffix}", parse_mode="Markdown")
        return

    # ── DEEP DIVE mode ──────────────────────────────────────────
    if state.mode == UserMode.DEEP_DIVE:
        if len(text) > 20 and not _looks_like_answer(text, state):
            state.pending_note_text = text
            state.prev_mode = UserMode.DEEP_DIVE
            set_mode(user_id, UserMode.CONFLICT)
            await update.message.reply_text(CONFLICT_MSG)
            return

        state.deep_history.append({"role": "user", "content": text})
        state.deep_turns += 1

        if state.deep_turns >= DEEP_MAX_TURNS:
            await update.message.reply_text(
                f"✅ Đã đào sâu {DEEP_MAX_TURNS} lượt về *{state.deep_topic}*. Ghi lại những gì bạn khám phá nhé!",
                parse_mode="Markdown",
            )
            reset(user_id)
            return

        question = await continue_deep_dive(state.deep_history, text)
        state.deep_history.append({"role": "assistant", "content": question})
        suffix = f"\n\n_({state.deep_turns}/{DEEP_MAX_TURNS} lượt · /done để kết thúc)_"
        await update.message.reply_text(f"🤔 {question}{suffix}", parse_mode="Markdown")
        return

    # ── IDLE: ghi chú mới ───────────────────────────────────────
    note_id, category, _, _, confirm = await _save_note_flow(pool, user_id, text)
    set_last_note(user_id, note_id, text, category)
    await update.message.reply_text(confirm, parse_mode="Markdown")

    question = await generate_first_question(text, category)
    state.socratic_history = [{"role": "assistant", "content": question}]
    state.socratic_turns = 0
    set_mode(user_id, UserMode.SOCRATIC)
    suffix = f"\n\n_(1/{SOCRATIC_MAX_TURNS} lượt · /done để kết thúc)_"
    await update.message.reply_text(f"🤔 {question}{suffix}", parse_mode="Markdown")


def _looks_like_answer(text: str, state) -> bool:
    """Heuristic: tin nhắn ngắn hoặc liên quan đến topic đang đào sâu → coi là câu trả lời."""
    if len(text) <= 60:
        return True
    topic = state.last_note_content or state.deep_topic or ""
    # Nếu chia sẻ từ chung với topic đang đào sâu → coi là reply
    topic_words = set(topic.lower().split())
    text_words = set(text.lower().split())
    overlap = topic_words & text_words
    return len(overlap) >= 2
