"""
Query Orchestrator: classifies intent and routes to appropriate tools.
One orchestrator, no multi-agent systems.

Intent types:
- FACTUAL    → PostgreSQL / Neo4j (who won, positions, results)
- GRAPH      → Neo4j Context Graph (relationships, stints, strategies)
- ANALYTICAL → FastF1-derived analytics (sector times, pace, telemetry)
- DOCUMENT   → Qdrant RAG (quotes, reports, analysis)
- COMBINED   → Multiple sources
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Any
import logging

log = logging.getLogger(__name__)


class QueryIntent(str, Enum):
    FACTUAL = "FACTUAL"
    GRAPH = "GRAPH"
    ANALYTICAL = "ANALYTICAL"
    DOCUMENT = "DOCUMENT"
    COMBINED = "COMBINED"


# ─────────────────────────────────────────────────────────────────────────────
# Intent classification (keyword-based, no LLM for routing)
# ─────────────────────────────────────────────────────────────────────────────

FACTUAL_KEYWORDS = [
    "who won", "winner", "podium", "finish", "position", "result",
    "grid", "pole", "points", "championship", "dnf", "classified",
]
GRAPH_KEYWORDS = [
    "strategy", "stint", "tyre", "compound", "pit stop", "pit strategy",
    "soft", "medium", "hard", "used", "laps on", "undercut", "overcut",
]
ANALYTICAL_KEYWORDS = [
    "sector", "pace", "lap time", "fastest lap", "speed", "throttle",
    "brake", "drs", "telemetry", "gap", "delta", "degradation",
    "faster", "slower", "quicker", "performance", "compare", "where did",
    "how much", "advantage", "gain time", "lose time",
]
DOCUMENT_KEYWORDS = [
    "say", "said", "comment", "quote", "reaction", "team said",
    "driver said", "radio", "interview", "report", "analysis",
    "technical", "according to", "explain why", "background",
]


def classify_intent(message: str) -> QueryIntent:
    """Classify query intent from message text."""
    msg = message.lower()

    scores = {
        QueryIntent.FACTUAL: 0,
        QueryIntent.GRAPH: 0,
        QueryIntent.ANALYTICAL: 0,
        QueryIntent.DOCUMENT: 0,
    }

    for kw in FACTUAL_KEYWORDS:
        if kw in msg:
            scores[QueryIntent.FACTUAL] += 1

    for kw in GRAPH_KEYWORDS:
        if kw in msg:
            scores[QueryIntent.GRAPH] += 1

    for kw in ANALYTICAL_KEYWORDS:
        if kw in msg:
            scores[QueryIntent.ANALYTICAL] += 1

    for kw in DOCUMENT_KEYWORDS:
        if kw in msg:
            scores[QueryIntent.DOCUMENT] += 1

    top_score = max(scores.values())
    if top_score == 0:
        return QueryIntent.COMBINED  # default: use everything

    # Count how many categories tied for top
    top_count = sum(1 for v in scores.values() if v == top_score)
    if top_count > 1:
        return QueryIntent.COMBINED

    return max(scores, key=lambda k: scores[k])


def detect_drivers(message: str) -> tuple[str, str]:
    """Detect driver codes mentioned in message. Default to LEC, NOR."""
    msg = message.upper()
    lec = "LEC" if ("LEC" in msg or "LECLERC" in msg or "CHARLES" in msg) else None
    nor = "NOR" if ("NOR" in msg or "NORRIS" in msg or "LANDO" in msg) else None

    # Defaults
    driver_a = lec or "LEC"
    driver_b = nor or "NOR"
    return driver_a, driver_b


def detect_session(message: str) -> str:
    """Detect session type from message. Default to Race."""
    msg = message.lower()
    if "qualifying" in msg or "quali" in msg or "q3" in msg or "q2" in msg or "q1" in msg:
        return "Qualifying"
    return "Race"


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OrchestratorResult:
    intent: QueryIntent
    graph_context: dict[str, Any] = field(default_factory=dict)
    analytics: dict[str, Any] = field(default_factory=dict)
    documents: list[dict[str, Any]] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)
    error: str | None = None


def orchestrate(message: str) -> OrchestratorResult:
    """
    Main orchestration function.
    Classifies intent, routes to relevant tools, and collects structured results.
    """
    from app.agent.tools import (
        tool_get_race_context,
        tool_get_driver_stints,
        tool_get_race_results,
        tool_compare_sector_performance,
        tool_compare_driver_telemetry,
        tool_analyze_tyre_degradation,
        tool_compare_race_strategy,
        tool_search_documents,
        tool_get_weather,
        tool_get_driver_laps,
    )

    intent = classify_intent(message)
    driver_a, driver_b = detect_drivers(message)
    session_type = detect_session(message)

    log.info(f"Intent: {intent} | Drivers: {driver_a}, {driver_b} | Session: {session_type}")

    result = OrchestratorResult(intent=intent)

    try:
        # Always include race-level context
        result.graph_context["race"] = tool_get_race_context()
        result.sources_used.append("Neo4j")

        if intent in (QueryIntent.FACTUAL, QueryIntent.COMBINED):
            try:
                result.analytics["race_results"] = tool_get_race_results(session_type)
                result.sources_used.append("PostgreSQL")
            except Exception as e:
                log.warning(f"Race results failed: {e}")

        if intent in (QueryIntent.GRAPH, QueryIntent.COMBINED):
            try:
                result.graph_context["lec_stints"] = tool_get_driver_stints("LEC", session_type)
                result.graph_context["nor_stints"] = tool_get_driver_stints("NOR", session_type)
                result.sources_used.append("Neo4j-Stints")
            except Exception as e:
                log.warning(f"Stints failed: {e}")

        if intent in (QueryIntent.ANALYTICAL, QueryIntent.COMBINED):
            try:
                result.analytics["sector_comparison"] = tool_compare_sector_performance(
                    driver_a, driver_b, session_type
                )
                result.sources_used.append("Analytics-Sectors")
            except Exception as e:
                log.warning(f"Sector comparison failed: {e}")

            try:
                result.analytics["telemetry_comparison"] = tool_compare_driver_telemetry(
                    driver_a, driver_b, session_type
                )
                result.sources_used.append("Analytics-Telemetry")
            except Exception as e:
                log.warning(f"Telemetry comparison failed: {e}")

            try:
                result.analytics["lec_pace"] = tool_get_driver_laps("LEC", session_type)
                result.analytics["nor_pace"] = tool_get_driver_laps("NOR", session_type)
                result.sources_used.append("Analytics-Pace")
            except Exception as e:
                log.warning(f"Lap pace failed: {e}")

        # Strategy always included for GRAPH and COMBINED
        if intent in (QueryIntent.GRAPH, QueryIntent.COMBINED) and session_type == "Race":
            try:
                result.analytics["strategy_comparison"] = tool_compare_race_strategy(
                    driver_a, driver_b, session_type
                )
                result.sources_used.append("Analytics-Strategy")
            except Exception as e:
                log.warning(f"Strategy comparison failed: {e}")

            try:
                result.analytics["lec_degradation"] = tool_analyze_tyre_degradation("LEC", session_type)
                result.analytics["nor_degradation"] = tool_analyze_tyre_degradation("NOR", session_type)
                result.sources_used.append("Analytics-Degradation")
            except Exception as e:
                log.warning(f"Degradation analysis failed: {e}")

        # Weather for context
        try:
            result.graph_context["weather"] = tool_get_weather(session_type)
        except Exception as e:
            log.warning(f"Weather fetch failed: {e}")

        # Documents always retrieved (top 2 to keep context lightweight)
        try:
            result.documents = tool_search_documents(message, top_k=2)
            result.sources_used.append("Qdrant")
        except Exception as e:
            log.warning(f"Document search failed: {e}")

    except Exception as e:
        log.error(f"Orchestration error: {e}", exc_info=True)
        result.error = str(e)

    # Deduplicate sources
    result.sources_used = list(dict.fromkeys(result.sources_used))
    return result
