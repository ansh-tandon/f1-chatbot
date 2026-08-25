"""
Create all PostgreSQL tables.
Run once before ingestion: python scripts/init_db.py
"""
import sys
import os

# Allow running from backend/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.connection import engine
from app.db.models import Base


def main():
    print("Creating all tables in PostgreSQL...")
    Base.metadata.create_all(bind=engine)
    print("Done. Tables created:")
    for table in Base.metadata.sorted_tables:
        print(f"  ✓ {table.name}")


if __name__ == "__main__":
    main()
