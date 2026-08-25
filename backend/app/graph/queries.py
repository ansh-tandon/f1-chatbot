"""
Predefined, safe Cypher query functions for the Context Graph.
The LLM never generates arbitrary Cypher — it only calls these functions.
"""
from typing import Optional
from app.graph.connection import get_neo4j_driver


def get_race_context(race_name: str = "Monaco Grand Prix", season: int = 2024) -> dict:
    """Return high-level race/circuit/session context."""
    driver = get_neo4j_driver()
    query = """
    MATCH (s:Season {year: $season})-[:HAS_RACE]->(r:Race)-[:HELD_AT]->(c:Circuit)
    WHERE r.name CONTAINS $race_name
    OPTIONAL MATCH (r)-[:HAS_SESSION]->(sess:Session)
    OPTIONAL MATCH (sess)-[:HAS_WEATHER]->(w:Weather)
    RETURN r.name AS race, r.date AS date, c.name AS circuit, c.country AS country,
           collect({type: sess.type, session_id: sess.session_id}) AS sessions,
           collect({air_temp: w.avg_air_temp, track_temp: w.avg_track_temp, rainfall: w.rainfall}) AS weather
    """
    with driver.session() as neo_sess:
        result = neo_sess.run(query, season=season, race_name=race_name)
        record = result.single()
        if not record:
            return {}
        return dict(record)


def get_driver_stints(driver_code: str, session_type: str = "Race") -> list[dict]:
    """Return all stints for a driver in a given session type."""
    driver = get_neo4j_driver()
    query = """
    MATCH (d:Driver {code: $code})-[:PARTICIPATED_IN]->(sess:Session {type: $session_type})
    MATCH (d)-[:COMPLETED]->(l:Lap)-[:PART_OF_STINT]->(s:Stint)-[:USED]->(t:Tyre)
    WHERE s.session_id = sess.session_id
    RETURN s.stint_number AS stint_number,
           t.compound AS compound,
           s.lap_start AS lap_start,
           s.lap_end AS lap_end,
           s.lap_count AS lap_count,
           s.avg_lap_time_s AS avg_lap_time_s,
           s.best_lap_time_s AS best_lap_time_s
    ORDER BY s.stint_number
    """
    with driver.session() as neo_sess:
        result = neo_sess.run(query, code=driver_code, session_type=session_type)
        return [dict(r) for r in result]


def get_driver_pit_stops(driver_code: str, session_type: str = "Race") -> list[dict]:
    """Return all pit stops for a driver."""
    driver = get_neo4j_driver()
    query = """
    MATCH (d:Driver {code: $code})-[:PARTICIPATED_IN]->(sess:Session {type: $session_type})
    MATCH (d)-[:MADE]->(p:PitStop)
    WHERE p.session_id = sess.session_id
    RETURN p.stop_number AS stop_number,
           p.lap_number AS lap_number,
           p.duration_s AS duration_s,
           p.compound_in AS compound_in,
           p.compound_out AS compound_out
    ORDER BY p.stop_number
    """
    with driver.session() as neo_sess:
        result = neo_sess.run(query, code=driver_code, session_type=session_type)
        return [dict(r) for r in result]


def compare_drivers_graph(driver_a: str, driver_b: str, session_type: str = "Race") -> dict:
    """Compare two drivers' graph-level context: stints, pit stops, tyre strategy."""
    return {
        "driver_a": {
            "code": driver_a,
            "stints": get_driver_stints(driver_a, session_type),
            "pit_stops": get_driver_pit_stops(driver_a, session_type),
        },
        "driver_b": {
            "code": driver_b,
            "stints": get_driver_stints(driver_b, session_type),
            "pit_stops": get_driver_pit_stops(driver_b, session_type),
        },
    }


def get_driver_laps_graph(driver_code: str, session_type: str = "Race") -> list[dict]:
    """Return lap-level data from graph for a driver."""
    driver = get_neo4j_driver()
    query = """
    MATCH (d:Driver {code: $code})-[:COMPLETED]->(l:Lap)-[:PART_OF]->(sess:Session {type: $session_type})
    RETURN l.lap_number AS lap_number,
           l.lap_time_s AS lap_time_s,
           l.sector1_s AS sector1_s,
           l.sector2_s AS sector2_s,
           l.sector3_s AS sector3_s,
           l.compound AS compound,
           l.tyre_life AS tyre_life,
           l.position AS position
    ORDER BY l.lap_number
    """
    with driver.session() as neo_sess:
        result = neo_sess.run(query, code=driver_code, session_type=session_type)
        return [dict(r) for r in result]


def get_driver_info(driver_code: str) -> dict:
    """Return driver + team info from graph."""
    driver = get_neo4j_driver()
    query = """
    MATCH (d:Driver {code: $code})
    OPTIONAL MATCH (d)-[:DRIVES_FOR]->(t:Team)
    RETURN d.code AS code, d.full_name AS full_name, d.number AS number,
           t.name AS team, t.short_name AS team_short
    """
    with driver.session() as neo_sess:
        result = neo_sess.run(query, code=driver_code)
        record = result.single()
        return dict(record) if record else {}


def get_weather_context(session_type: str = "Race") -> dict:
    """Return weather summary for a given session type."""
    driver = get_neo4j_driver()
    query = """
    MATCH (sess:Session {type: $session_type})-[:HAS_WEATHER]->(w:Weather)
    RETURN w.avg_air_temp AS air_temp_c,
           w.avg_track_temp AS track_temp_c,
           w.rainfall AS rainfall
    LIMIT 1
    """
    with driver.session() as neo_sess:
        result = neo_sess.run(query, session_type=session_type)
        record = result.single()
        return dict(record) if record else {}
