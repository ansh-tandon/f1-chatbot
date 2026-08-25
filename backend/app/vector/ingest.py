"""
Qdrant document ingestion.
Reads .txt files from data/documents/, chunks them, embeds with OpenAI, stores in Qdrant.

Run: python scripts/ingest_qdrant.py
"""
import sys
import os
import logging
import uuid
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qdrant_client.models import Distance, VectorParams, PointStruct

from app.config import get_settings
from app.vector.connection import get_qdrant_client, COLLECTION_NAME, VECTOR_SIZE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

settings = get_settings()

DOCUMENTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "documents"
CHUNK_SIZE = 500  # characters
CHUNK_OVERLAP = 50
EMBED_MODEL = "gemini-embedding-001"


def parse_document(filepath: Path) -> dict:
    """Parse a document file and extract metadata from headers."""
    text = filepath.read_text(encoding="utf-8")
    lines = text.strip().split("\n")

    metadata = {
        "source": filepath.name,
        "title": "",
        "date": "",
        "driver": "",
        "team": "",
        "race": "Monaco 2024",
        "session": "",
    }

    body_lines = []
    in_header = True

    for line in lines:
        if in_header and ": " in line and not line.startswith(" "):
            key, _, val = line.partition(": ")
            key = key.strip().upper()
            val = val.strip()
            mapping = {
                "SOURCE": "source",
                "TITLE": "title",
                "DATE": "date",
                "DRIVER": "driver",
                "TEAM": "team",
                "RACE": "race",
                "SESSION": "session",
            }
            if key in mapping:
                metadata[mapping[key]] = val
                continue
        in_header = False
        body_lines.append(line)

    body = "\n".join(body_lines).strip()
    return {"text": body, "metadata": metadata}


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using Google Gemini embeddings (or OpenAI fallback)."""
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        import google.genai as genai
        client = genai.Client(api_key=api_key)
        res = client.models.embed_content(
            model=EMBED_MODEL,
            contents=texts,
        )
        return [e.values for e in res.embeddings]
    elif settings.openai_api_key:
        from openai import OpenAI
        openai_client = OpenAI(api_key=settings.openai_api_key)
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in response.data]
    else:
        raise ValueError("Neither GEMINI_API_KEY nor OPENAI_API_KEY is configured in .env.")


def ensure_collection():
    """Create Qdrant collection if it doesn't exist, or recreate if vector size changed."""
    client = get_qdrant_client()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        info = client.get_collection(COLLECTION_NAME)
        current_size = getattr(info.config.params.vectors, "size", None)
        if current_size and current_size != VECTOR_SIZE:
            log.info(f"Recreating collection '{COLLECTION_NAME}' (vector size changed: {current_size} -> {VECTOR_SIZE})")
            client.delete_collection(COLLECTION_NAME)
            existing.remove(COLLECTION_NAME)

    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        log.info(f"Created Qdrant collection: {COLLECTION_NAME} (size: {VECTOR_SIZE})")
    else:
        log.info(f"Collection already exists: {COLLECTION_NAME}")


def ingest_documents():
    """Ingest all documents from the documents directory."""
    ensure_collection()
    client = get_qdrant_client()

    doc_files = sorted(DOCUMENTS_DIR.glob("*.txt"))
    if not doc_files:
        log.warning(f"No .txt files found in {DOCUMENTS_DIR}")
        return

    log.info(f"Found {len(doc_files)} documents to ingest")

    all_points = []

    for filepath in doc_files:
        log.info(f"Processing: {filepath.name}")
        doc = parse_document(filepath)
        chunks = chunk_text(doc["text"])
        log.info(f"  {len(chunks)} chunks")

        if not chunks:
            continue

        # Embed all chunks in one batch request
        embeddings = embed_texts(chunks)

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "text": chunk,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    **doc["metadata"],
                },
            )
            all_points.append(point)

    if all_points:
        client.upsert(collection_name=COLLECTION_NAME, points=all_points)
        log.info(f"Ingested {len(all_points)} chunks into Qdrant collection '{COLLECTION_NAME}'")
    else:
        log.warning("No chunks to ingest")


def main():
    ingest_documents()
    log.info("✓ Qdrant ingestion complete.")


if __name__ == "__main__":
    main()
