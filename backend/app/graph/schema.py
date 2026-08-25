"""
Neo4j schema: constraints, indexes, and node/relationship creation helpers.
All writes use MERGE to be idempotent.
"""
from app.graph.connection import get_neo4j_driver


CONSTRAINTS = [
    "CREATE CONSTRAINT season_year IF NOT EXISTS FOR (s:Season) REQUIRE s.year IS UNIQUE",
    "CREATE CONSTRAINT race_id IF NOT EXISTS FOR (r:Race) REQUIRE r.race_id IS UNIQUE",
    "CREATE CONSTRAINT circuit_name IF NOT EXISTS FOR (c:Circuit) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT session_id IF NOT EXISTS FOR (s:Session) REQUIRE s.session_id IS UNIQUE",
    "CREATE CONSTRAINT driver_code IF NOT EXISTS FOR (d:Driver) REQUIRE d.code IS UNIQUE",
    "CREATE CONSTRAINT team_name IF NOT EXISTS FOR (t:Team) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT lap_id IF NOT EXISTS FOR (l:Lap) REQUIRE l.lap_id IS UNIQUE",
    "CREATE CONSTRAINT stint_id IF NOT EXISTS FOR (s:Stint) REQUIRE s.stint_id IS UNIQUE",
    "CREATE CONSTRAINT pitstop_id IF NOT EXISTS FOR (p:PitStop) REQUIRE p.pitstop_id IS UNIQUE",
    "CREATE CONSTRAINT tyre_id IF NOT EXISTS FOR (t:Tyre) REQUIRE t.tyre_id IS UNIQUE",
]


def apply_schema():
    """Apply constraints and indexes. Safe to run multiple times."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        for constraint in CONSTRAINTS:
            try:
                session.run(constraint)
            except Exception as e:
                # Constraint may already exist under a different name syntax
                print(f"  [schema] {e}")
    print("Neo4j schema applied.")
