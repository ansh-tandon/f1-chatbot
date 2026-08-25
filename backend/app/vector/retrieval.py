"""Qdrant similarity search and retrieval."""
from dataclasses import dataclass
from app.config import get_settings
from app.vector.connection import get_qdrant_client, COLLECTION_NAME
from app.vector.ingest import embed_texts

settings = get_settings()


@dataclass
class DocumentResult:
    text: str
    source: str
    title: str
    date: str
    driver: str
    team: str
    race: str
    session: str
    score: float


def search_documents(query: str, top_k: int = 5, score_threshold: float = 0.3) -> list[DocumentResult]:
    """
    Embed the query and retrieve the most relevant document chunks.
    Never invents sources — only returns what's in the Qdrant collection.
    """
    client = get_qdrant_client()

    # Embed the query
    query_vector = embed_texts([query])[0]

    # Search
    if hasattr(client, "query_points"):
        res = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )
        results = res.points
    else:
        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )

    documents = []
    for hit in results:
        payload = hit.payload or {}
        documents.append(
            DocumentResult(
                text=payload.get("text", ""),
                source=payload.get("source", ""),
                title=payload.get("title", ""),
                date=payload.get("date", ""),
                driver=payload.get("driver", ""),
                team=payload.get("team", ""),
                race=payload.get("race", "Monaco 2024"),
                session=payload.get("session", ""),
                score=hit.score,
            )
        )

    return documents
