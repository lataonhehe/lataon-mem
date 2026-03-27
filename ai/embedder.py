import logging
from openai import AsyncOpenAI
from config.settings import OPENROUTER_API_KEY, OPENROUTER_BASE_URL

logger = logging.getLogger(__name__)

# ChromaDB cần embedding synchronous — dùng client riêng cho embedding
from openai import OpenAI as SyncOpenAI

_async_client = AsyncOpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
_sync_client = SyncOpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)

EMBEDDING_MODEL = "openai/text-embedding-3-small"
EMBEDDING_DIM = 1536


async def embed_text(text: str) -> list[float]:
    """Tạo embedding vector cho 1 đoạn text (async)."""
    response = await _async_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def embed_text_sync(text: str) -> list[float]:
    """Tạo embedding vector cho 1 đoạn text (sync — dùng cho ChromaDB)."""
    response = _sync_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Tạo embedding cho nhiều text cùng lúc."""
    if not texts:
        return []
    response = await _async_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
