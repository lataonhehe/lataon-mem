from openai import AsyncOpenAI
from ai.prompts import SOCRATIC_SYSTEM, DEEP_DIVE_SYSTEM, QUIZ_SYSTEM
from config.settings import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MODEL

client = AsyncOpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


async def generate_question(note_content: str, category: str) -> str:
    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=128,
        messages=[
            {"role": "system", "content": SOCRATIC_SYSTEM},
            {"role": "user", "content": f"[{category}] {note_content}"},
        ],
    )
    return response.choices[0].message.content.strip()


async def continue_deep_dive(original: str, category: str, user_reply: str) -> str:
    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=128,
        messages=[
            {"role": "system", "content": DEEP_DIVE_SYSTEM},
            {"role": "user", "content": f"[{category}] {original}"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": user_reply},
        ],
    )
    return response.choices[0].message.content.strip()


async def deep_dive_topic(topic: str, turn: int, history: list[dict]) -> str:
    """Socratic nhiều lượt về 1 chủ đề tự do, dùng history để không lặp câu."""
    messages = [{"role": "system", "content": DEEP_DIVE_SYSTEM}] + history
    messages.append(
        {"role": "user", "content": topic if turn == 1 else history[-1]["content"]}
    )
    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=128,
        messages=messages,
    )
    return response.choices[0].message.content.strip()


async def generate_quiz(note_content: str, category: str) -> str:
    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=128,
        messages=[
            {"role": "system", "content": QUIZ_SYSTEM},
            {"role": "user", "content": f"[{category}] {note_content}"},
        ],
    )
    return response.choices[0].message.content.strip()


async def generate_summary(notes_text: str) -> str:
    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=512,
        messages=[
            {
                "role": "system",
                "content": "Bạn là trợ lý tổng hợp kiến thức. Hãy tóm tắt những điểm chính từ các ghi chú sau thành 1 đoạn ngắn gọn, súc tích bằng tiếng Việt.",
            },
            {"role": "user", "content": notes_text},
        ],
    )
    return response.choices[0].message.content.strip()
