from openai import AsyncOpenAI
from ai.prompts import (
    SOCRATIC_SYSTEM,
    SOCRATIC_CONTINUE_SYSTEM,
    DEEP_DIVE_SYSTEM,
    QUIZ_SYSTEM,
)
from config.settings import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MODEL

client = AsyncOpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


async def _ask(system: str, messages: list, max_tokens: int = 128) -> str:
    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}] + messages,
    )
    return response.choices[0].message.content.strip()


async def generate_first_question(note_content: str, category: str) -> str:
    """Câu hỏi Socratic đầu tiên sau khi lưu ghi chú."""
    return await _ask(
        SOCRATIC_SYSTEM,
        [{"role": "user", "content": f"[{category}] {note_content}"}],
    )


async def continue_socratic(history: list, user_reply: str) -> str:
    """Tiếp tục Socratic dựa trên lịch sử hội thoại."""
    msgs = history + [{"role": "user", "content": user_reply}]
    return await _ask(SOCRATIC_CONTINUE_SYSTEM, msgs)


async def start_deep_dive(topic: str) -> str:
    """Câu hỏi đầu tiên cho /deep."""
    return await _ask(
        DEEP_DIVE_SYSTEM,
        [{"role": "user", "content": topic}],
    )


async def continue_deep_dive(history: list, user_reply: str) -> str:
    """Tiếp tục /deep dựa trên history."""
    msgs = history + [{"role": "user", "content": user_reply}]
    return await _ask(DEEP_DIVE_SYSTEM, msgs)


async def generate_quiz(note_content: str, category: str) -> str:
    return await _ask(
        QUIZ_SYSTEM,
        [{"role": "user", "content": f"[{category}] {note_content}"}],
    )


async def generate_summary(notes_text: str) -> str:
    return await _ask(
        "Bạn là trợ lý tổng hợp kiến thức. Tóm tắt các ghi chú sau thành 1 đoạn ngắn gọn, súc tích bằng tiếng Việt.",
        [{"role": "user", "content": notes_text}],
        max_tokens=512,
    )
