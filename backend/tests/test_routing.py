"""Tests for query intent classification and entity extraction."""
import pytest
from app.agent.orchestrator import classify_intent, detect_drivers, detect_session, QueryIntent


def test_classify_intent_factual():
    intent = classify_intent("Who won Monaco 2024?")
    assert intent == QueryIntent.FACTUAL


def test_classify_intent_graph():
    intent = classify_intent("What tyres did Norris use during his stints?")
    assert intent == QueryIntent.GRAPH


def test_classify_intent_analytical():
    intent = classify_intent("Compare their sector performance and telemetry pace")
    assert intent == QueryIntent.ANALYTICAL


def test_classify_intent_document():
    intent = classify_intent("What did the driver say in post race interview?")
    assert intent == QueryIntent.DOCUMENT


def test_detect_drivers():
    da, db = detect_drivers("Why was Leclerc faster than Norris?")
    assert da == "LEC"
    assert db == "NOR"


def test_detect_session():
    assert detect_session("qualifying results") == "Qualifying"
    assert detect_session("race pace") == "Race"
