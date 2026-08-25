"""
Populate Neo4j Context Graph from PostgreSQL data.
Run after ingest_monaco.py: python scripts/init_neo4j.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.graph.ingest import main

if __name__ == "__main__":
    main()
