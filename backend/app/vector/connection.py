"""Qdrant client connection."""
from qdrant_client import QdrantClient
from app.config import get_settings

_client: QdrantClient | None = None

COLLECTION_NAME = "f1_monaco_2024"
VECTOR_SIZE = 3072  # Google Gemini gemini-embedding-001


def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        settings = get_settings()
        kwargs = {"url": settings.qdrant_url}
        if settings.qdrant_api_key:
            kwargs["api_key"] = settings.qdrant_api_key
        _client = QdrantClient(**kwargs)
    return _client
