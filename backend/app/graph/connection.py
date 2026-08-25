"""Neo4j driver connection."""
from neo4j import GraphDatabase, Driver
from app.config import get_settings

_driver: Driver | None = None


def get_neo4j_driver() -> Driver:
    global _driver
    if _driver is None:
        settings = get_settings()
        uri = settings.neo4j_uri
        if uri.startswith("neo4j+s://"):
            uri = uri.replace("neo4j+s://", "neo4j+ssc://", 1)
        _driver = GraphDatabase.driver(
            uri,
            auth=(settings.active_neo4j_user, settings.neo4j_password),
        )
    return _driver


def close_neo4j_driver():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def verify_connectivity():
    driver = get_neo4j_driver()
    driver.verify_connectivity()
    return True
