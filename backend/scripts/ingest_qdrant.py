"""Qdrant ingestion entry point script."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.vector.ingest import main

if __name__ == "__main__":
    main()
