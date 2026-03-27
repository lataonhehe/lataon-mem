import logging
import chromadb
from chromadb.config import Settings
from ai.embedder import embed_text_sync

logger = logging.getLogger(__name__)

COLLECTION_NAME = "notes"
_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(
            path="data/chroma",
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def upsert_note(note_id: int, content: str, metadata: dict):
    """Lưu hoặc cập nhật embedding của 1 ghi chú."""
    collection = _get_collection()
    embedding = embed_text_sync(content)
    collection.upsert(
        ids=[str(note_id)],
        embeddings=[embedding],
        documents=[content],
        metadatas=[metadata],
    )
    logger.info(f"Upserted note #{note_id} vào ChromaDB")


def query_similar(
    query_embedding: list[float], user_id: int, n_results: int = 5
) -> list[dict]:
    """Tìm n_results ghi chú tương tự nhất theo embedding."""
    collection = _get_collection()
    total = collection.count()
    if total == 0:
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, total),
        where={"user_id": user_id},
    )
    if not results["ids"] or not results["ids"][0]:
        return []

    items = []
    for i, doc_id in enumerate(results["ids"][0]):
        items.append(
            {
                "note_id": int(doc_id),
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            }
        )
    return items


def delete_note(note_id: int):
    """Xóa embedding của 1 ghi chú."""
    collection = _get_collection()
    collection.delete(ids=[str(note_id)])
