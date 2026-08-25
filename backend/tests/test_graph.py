"""Tests for Neo4j schema definitions."""
import pytest
from app.graph.schema import CONSTRAINTS


def test_neo4j_constraints():
    assert len(CONSTRAINTS) > 5
    assert any("Driver" in c for c in CONSTRAINTS)
    assert any("Race" in c for c in CONSTRAINTS)
