"""
Tools: structured data access functions.
The LLM calls these tools rather than directly accessing databases.
All tools return structured (JSON-serializable) data.
"""
from typing import Any
from app.f1.analytics import (
    calculate_lap_pace,
    compare_sector_performance,
    compare_driver_telemetry,
    calculate_tyre_degradation,
    compare_race_strategy,
    get_race_results,
)
from app.graph.queries import (
    get_race_context,
    get_driver_stints,
    get_driver_pit_stops,
    get_driver_laps_graph,
    get_driver_info,
    get_weather_context,
    compare_drivers_graph,
)
from app.vector.retrieval import search_documents


def tool_get_race_context() -> dict[str, Any]:
    """Get high-level race and circuit context for Monaco 2024."""
    return get_race_context()


def tool_get_driver_laps(driver: str, session_type: str = "Race") -> dict[str, Any]:
    """Get lap-by-lap data for a driver."""
    pace = calculate_lap_pace(driver, session_type)
    return pace.model_dump()


def tool_get_driver_stints(driver: str, session_type: str = "Race") -> dict[str, Any]:
    """Get stint breakdown for a driver."""
    stints = get_driver_stints(driver, session_type)
    pits = get_driver_pit_stops(driver, session_type)
    info = get_driver_info(driver)
    return {
        "driver": driver,
        "driver_info": info,
        "session_type": session_type,
        "stints": stints,
        "pit_stops": pits,
    }


def tool_compare_sector_performance(
    driver_a: str, driver_b: str, session_type: str = "Qualifying"
) -> dict[str, Any]:
    """Compare sector times between two drivers."""
    result = compare_sector_performance(driver_a, driver_b, session_type)
    return result.model_dump()


def tool_compare_driver_telemetry(
    driver_a: str, driver_b: str, session_type: str = "Qualifying"
) -> dict[str, Any]:
    """Compare telemetry (speed, throttle, brake, DRS) between two drivers."""
    result = compare_driver_telemetry(driver_a, driver_b, session_type)
    return result.model_dump()


def tool_analyze_tyre_degradation(driver: str, session_type: str = "Race") -> dict[str, Any]:
    """Analyze tyre degradation for a driver."""
    result = calculate_tyre_degradation(driver, session_type)
    return result.model_dump()


def tool_compare_race_strategy(
    driver_a: str, driver_b: str, session_type: str = "Race"
) -> dict[str, Any]:
    """Compare full race strategy (compounds, stops, pit timing) between two drivers."""
    result = compare_race_strategy(driver_a, driver_b, session_type)
    return result.model_dump()


def tool_search_documents(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search race documents for relevant context."""
    results = search_documents(query, top_k=top_k)
    return [
        {
            "text": r.text,
            "source": r.source,
            "title": r.title,
            "date": r.date,
            "driver": r.driver,
            "team": r.team,
            "race": r.race,
            "session": r.session,
            "score": round(r.score, 4),
        }
        for r in results
    ]


def tool_get_race_results(session_type: str = "Race") -> list[dict[str, Any]]:
    """Get race/qualifying results."""
    results = get_race_results(session_type)
    return [r.model_dump() for r in results]


def tool_get_weather(session_type: str = "Race") -> dict[str, Any]:
    """Get weather conditions for a session."""
    return get_weather_context(session_type)
