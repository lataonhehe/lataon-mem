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
from db.vector_store import upsert_note, delete_note as vector_delete
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


async def _save_and_embed(pool, user_id: int, text: str, classification: dict) -> tuple:
    """Lưu vào Postgres + upsert embedding vào ChromaDB."""
    category = classification.get("category", "other")
    tags = classification.get("tags", [])
    summary = classification.get("summary", text[:MAX_SUMMARY_LEN])
    if len(summary) > MAX_SUMMARY_LEN:
        summary = summary[:MAX_SUMMARY_LEN].rsplit(" ", 1)[0] + "…"

    note = Note(
        content=text, category=category, tags=tags, summary=summary, user_id=user_id
    )
    note_id = await save_note(pool, note)

    # Upsert embedding (chạy trong executor vì sync)
    import asyncio

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        upsert_note,
        note_id,
        text,
        {"user_id": user_id, "category": category, "tags": ",".join(tags)},
    )

    tags_display = " ".join(f"#{t}" for t in tags) if tags else ""
    confirm = f"Đã lưu `#{note_id}` [{category}] {tags_display}\n_{summary}_"
    return note_id, category, summary, confirm


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = get_state(user_id)
    pool = context.bot_data["pool"]

    await update.message.chat.send_action("typing")

    # ── QUIZ ──────────────────────────────────────────
    if state.mode == UserMode.QUIZ:
        await update.message.reply_text(
            f"💡 Ghi nhận rồi!\n\nNội dung gốc:\n_{state.quiz_note.summary}_",
            parse_mode="Markdown",
        )
        reset(user_id)
        return

    # ── CONFLICT ──────────────────────────────────────
    if state.mode == UserMode.CONFLICT:
        await update.message.reply_text(
            "Vui lòng chọn:\n/save · /skip · /done · /cancel"
        )
        return

    # ── SOCRATIC ──────────────────────────────────────
    if state.mode == UserMode.SOCRATIC:
        if len(text) > 20 and not _looks_like_answer(text, state):
            state.pending_note_text = text
            state.prev_mode = UserMode.SOCRATIC
            set_mode(user_id, UserMode.CONFLICT)
            await update.message.reply_text(CONFLICT_MSG)
            return

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
        suffix = f"\n\n_({state.socratic_turns}/{SOCRATIC_MAX_TURNS} lượt · /done để kết thúc)_"
        await update.message.reply_text(f"🤔 {question}{suffix}", parse_mode="Markdown")
        return

    # ── DEEP DIVE ─────────────────────────────────────
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
                f"✅ Đã đào sâu {DEEP_MAX_TURNS} lượt về *{state.deep_topic}*.",
                parse_mode="Markdown",
            )
            reset(user_id)
            return

        question = await continue_deep_dive(state.deep_history, text)
        state.deep_history.append({"role": "assistant", "content": question})
        suffix = f"\n\n_({state.deep_turns}/{DEEP_MAX_TURNS} lượt · /done để kết thúc)_"
        await update.message.reply_text(f"🤔 {question}{suffix}", parse_mode="Markdown")
        return

    # ── IDLE: ghi chú mới ─────────────────────────────
    classification = await classify_note(text)
    note_id, category, _, confirm = await _save_and_embed(
        pool, user_id, text, classification
    )
    set_last_note(user_id, note_id, text, category)
    await update.message.reply_text(confirm, parse_mode="Markdown")

    question = await generate_first_question(text, category)
    state.socratic_history = [{"role": "assistant", "content": question}]
    state.socratic_turns = 0
    set_mode(user_id, UserMode.SOCRATIC)
    suffix = f"\n\n_(1/{SOCRATIC_MAX_TURNS} lượt · /done để kết thúc)_"
    await update.message.reply_text(f"🤔 {question}{suffix}", parse_mode="Markdown")


def _looks_like_answer(text: str, state) -> bool:
    if len(text) <= 60:
        return True
    topic = state.last_note_content or state.deep_topic or ""
    topic_words = set(topic.lower().split())
    text_words = set(text.lower().split())
    return len(topic_words & text_words) >= 2
