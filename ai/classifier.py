import json
import logging
import re
from openai import AsyncOpenAI
from ai.prompts import CLASSIFIER_SYSTEM
from config.settings import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MODEL

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
)

VALID_CATEGORIES = {
    "it",
    "knowledge",
    "diary",
    "book",
    "idea",
    "health",
    "finance",
    "other",
}


async def classify_note(content: str) -> dict:
    """Phân loại ghi chú, trả về {category, tags, summary}."""
    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=256,
        messages=[
            {"role": "system", "content": CLASSIFIER_SYSTEM},
            {"role": "user", "content": content},
        ],
    )
    raw = response.choices[0].message.content.strip()
    logger.info(f"Classifier raw response: {raw}")

    # Strip markdown code fences nếu model trả về ```json ... ```
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    try:
        result = json.loads(cleaned)
        # Validate category hợp lệ
        if result.get("category") not in VALID_CATEGORIES:
            logger.warning(
                f"Invalid category '{result.get('category')}', defaulting to 'other'"
            )
            result["category"] = "other"
        return result
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e} | raw: {raw}")
        return {"category": "other", "tags": [], "summary": content[:80]}
