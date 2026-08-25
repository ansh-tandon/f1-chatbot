"""Tests for document parsing and chunking for Qdrant RAG."""
import pytest
from app.vector.ingest import chunk_text


def test_chunk_text():
    sample_text = "A" * 1200
    chunks = chunk_text(sample_text, chunk_size=500, overlap=50)
    assert len(chunks) == 3
    assert len(chunks[0]) == 500
