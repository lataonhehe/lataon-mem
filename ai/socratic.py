from openai import AsyncOpenAI
from ai.prompts import SOCRATIC_SYSTEM
from config.settings import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MODEL

client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
)


async def generate_question(note_content: str, category: str) -> str:
    """Tạo câu hỏi Socratic dựa trên nội dung ghi chú."""
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
