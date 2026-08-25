"""
Integration test for query orchestrator and context builder.
Requirement from prompt section 20:
"At least one integration test must exercise: 'Compare Norris and Leclerc's race strategies.'
and verify that structured race data is used."
"""
import pytest
from app.agent.orchestrator import orchestrate
from app.rag.context_builder import build_context


def test_strategy_comparison_orchestration():
    query = "Compare Norris and Leclerc's race strategies."
    result = orchestrate(query)

    # Verify intent
    assert result.intent in ("GRAPH", "COMBINED")

    # Verify sources used
    assert len(result.sources_used) > 0

    # Build context
    context = build_context(result, query)
    assert "Strategy Comparison" in context or "Stints" in context or "Race" in context
