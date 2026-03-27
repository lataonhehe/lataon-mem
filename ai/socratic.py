from openai import AsyncOpenAI
from ai.prompts import SOCRATIC_SYSTEM, DEEP_DIVE_SYSTEM
from config.settings import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MODEL

client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
)


async def generate_question(note_content: str, category: str) -> str:
    """Câu hỏi Socratic đầu tiên sau khi lưu ghi chú."""
    prompt = f"[{category}] {note_content}"
    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=128,
        messages=[
            {"role": "system", "content": SOCRATIC_SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()


async def continue_deep_dive(original: str, category: str, user_reply: str) -> str:
    """Tiếp tục đào sâu dựa trên câu trả lời của người dùng."""
    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=128,
        messages=[
            {"role": "system", "content": DEEP_DIVE_SYSTEM},
            {"role": "user", "content": f"[{category}] {original}"},
            {"role": "assistant", "content": "..."},  # placeholder
            {"role": "user", "content": user_reply},
        ],
    )
    return response.choices[0].message.content.strip()
