"""
Neo4j ingestion: populate Context Graph from PostgreSQL data.
Run after ingest_monaco.py has populated PostgreSQL.

    python scripts/init_neo4j.py
"""
import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.connection import db_session
from app.db.models import (
    Race, RaceSession, Driver, Team, Lap, Stint, PitStop, Weather, DriverResult
)
from app.graph.connection import get_neo4j_driver
from app.graph.schema import apply_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def run_cypher(tx, query: str, **params):
    tx.run(query, **params)


def ingest_graph():
    driver = get_neo4j_driver()

    with db_session() as db:
        races = db.query(Race).all()

        for race in races:
            log.info(f"Building graph for: {race.name}")
            sessions = db.query(RaceSession).filter_by(race_id=race.id).all()

            for session in sessions:
                laps = db.query(Lap).filter_by(session_id=session.id).all()
                stints = db.query(Stint).filter_by(session_id=session.id).all()
                pit_stops = db.query(PitStop).filter_by(session_id=session.id).all()
                weather_list = db.query(Weather).filter_by(session_id=session.id).all()
                results = db.query(DriverResult).filter_by(session_id=session.id).all()
                drivers = db.query(Driver).filter(Driver.code.in_(["LEC", "NOR"])).all()
                teams = {d.team_id: db.query(Team).filter_by(id=d.team_id).first() for d in drivers}

                # Build weather summary
                if weather_list:
                    temps = [w.air_temp_c for w in weather_list if w.air_temp_c is not None]
                    track_temps = [w.track_temp_c for w in weather_list if w.track_temp_c is not None]
                    rainfall = any(w.rainfall for w in weather_list if w.rainfall is not None)
                    weather_summary = {
                        "avg_air_temp": round(sum(temps) / len(temps), 1) if temps else None,
                        "avg_track_temp": round(sum(track_temps) / len(track_temps), 1) if track_temps else None,
                        "rainfall": rainfall,
                    }
                else:
                    weather_summary = {"avg_air_temp": None, "avg_track_temp": None, "rainfall": False}

                with driver.session() as neo_sess:
                    neo_sess.execute_write(_write_race_graph, race, session, drivers, teams, laps, stints, pit_stops, weather_summary, results)

            log.info(f"Graph complete for {race.name}")


def _write_race_graph(tx, race, session, drivers, teams, laps, stints, pit_stops, weather_summary, results):
    # ── Season ────────────────────────────────────────────────────────────────
    tx.run(
        "MERGE (s:Season {year: $year}) SET s.name = $name",
        year=race.season, name=str(race.season),
    )

    # ── Circuit ───────────────────────────────────────────────────────────────
    tx.run(
        "MERGE (c:Circuit {name: $name}) SET c.country = $country",
        name=race.circuit_name, country=race.country or "",
    )

    # ── Race ──────────────────────────────────────────────────────────────────
    tx.run(
        """
        MERGE (r:Race {race_id: $race_id})
        SET r.name = $name, r.season = $season, r.round = $round,
            r.date = $date, r.circuit = $circuit
        """,
        race_id=race.id, name=race.name, season=race.season,
        round=race.round_number,
        date=str(race.race_date) if race.race_date else "",
        circuit=race.circuit_name,
    )

    # Season → Race
    tx.run(
        """
        MATCH (s:Season {year: $year}), (r:Race {race_id: $race_id})
        MERGE (s)-[:HAS_RACE]->(r)
        """,
        year=race.season, race_id=race.id,
    )

    # Race → Circuit
    tx.run(
        """
        MATCH (r:Race {race_id: $race_id}), (c:Circuit {name: $circuit})
        MERGE (r)-[:HELD_AT]->(c)
        """,
        race_id=race.id, circuit=race.circuit_name,
    )

    # ── Session ───────────────────────────────────────────────────────────────
    tx.run(
        """
        MERGE (sess:Session {session_id: $session_id})
        SET sess.type = $type, sess.race_id = $race_id
        """,
        session_id=session.id, type=session.session_type, race_id=race.id,
    )

    tx.run(
        """
        MATCH (r:Race {race_id: $race_id}), (sess:Session {session_id: $session_id})
        MERGE (r)-[:HAS_SESSION]->(sess)
        """,
        race_id=race.id, session_id=session.id,
    )

    # ── Weather (as session property node) ───────────────────────────────────
    tx.run(
        """
        MERGE (w:Weather {session_id: $session_id})
        SET w.avg_air_temp = $air_temp,
            w.avg_track_temp = $track_temp,
            w.rainfall = $rainfall
        """,
        session_id=session.id,
        air_temp=weather_summary["avg_air_temp"],
        track_temp=weather_summary["avg_track_temp"],
        rainfall=weather_summary["rainfall"],
    )

    tx.run(
        """
        MATCH (sess:Session {session_id: $session_id}), (w:Weather {session_id: $session_id})
        MERGE (sess)-[:HAS_WEATHER]->(w)
        """,
        session_id=session.id,
    )

    # ── Teams and Drivers ─────────────────────────────────────────────────────
    for driver in drivers:
        team = teams.get(driver.team_id)
        if team:
            tx.run(
                "MERGE (t:Team {name: $name}) SET t.short_name = $short",
                name=team.name, short=team.short_name or "",
            )

        tx.run(
            """
            MERGE (d:Driver {code: $code})
            SET d.full_name = $full_name, d.number = $number
            """,
            code=driver.code, full_name=driver.full_name, number=driver.number or 0,
        )

        if team:
            tx.run(
                """
                MATCH (d:Driver {code: $code}), (t:Team {name: $team_name})
                MERGE (d)-[:DRIVES_FOR]->(t)
                """,
                code=driver.code, team_name=team.name,
            )

        tx.run(
            """
            MATCH (d:Driver {code: $code}), (sess:Session {session_id: $session_id})
            MERGE (d)-[:PARTICIPATED_IN]->(sess)
            """,
            code=driver.code, session_id=session.id,
        )

    # ── Laps ──────────────────────────────────────────────────────────────────
    # Group laps by driver
    lap_by_driver: dict[int, list] = {}
    for lap in laps:
        lap_by_driver.setdefault(lap.driver_id, []).append(lap)

    for driver in drivers:
        drv_laps = lap_by_driver.get(driver.id, [])
        for lap in drv_laps:
            lap_id = f"{session.id}_{driver.id}_{lap.lap_number}"
            tx.run(
                """
                MERGE (l:Lap {lap_id: $lap_id})
                SET l.lap_number = $lap_num,
                    l.lap_time_s = $lap_time,
                    l.sector1_s = $s1, l.sector2_s = $s2, l.sector3_s = $s3,
                    l.compound = $compound,
                    l.tyre_life = $tyre_life,
                    l.position = $position,
                    l.driver_code = $driver_code,
                    l.session_id = $session_id
                """,
                lap_id=lap_id,
                lap_num=lap.lap_number,
                lap_time=lap.lap_time_s,
                s1=lap.sector1_time_s,
                s2=lap.sector2_time_s,
                s3=lap.sector3_time_s,
                compound=lap.compound or "",
                tyre_life=lap.tyre_life,
                position=lap.position,
                driver_code=driver.code,
                session_id=session.id,
            )

            tx.run(
                """
                MATCH (d:Driver {code: $code}), (l:Lap {lap_id: $lap_id})
                MERGE (d)-[:COMPLETED]->(l)
                """,
                code=driver.code, lap_id=lap_id,
            )

            tx.run(
                """
                MATCH (l:Lap {lap_id: $lap_id}), (sess:Session {session_id: $session_id})
                MERGE (l)-[:PART_OF]->(sess)
                """,
                lap_id=lap_id, session_id=session.id,
            )

    # ── Stints and Tyres ──────────────────────────────────────────────────────
    for stint in stints:
        # Find driver code
        driver_code = next((d.code for d in drivers if d.id == stint.driver_id), None)
        if not driver_code:
            continue

        stint_id = f"{session.id}_{stint.driver_id}_{stint.stint_number}"
        tyre_id = f"{stint.compound}_{stint.tyre_life_start}"

        tx.run(
            """
            MERGE (s:Stint {stint_id: $stint_id})
            SET s.stint_number = $num,
                s.compound = $compound,
                s.lap_start = $lap_start,
                s.lap_end = $lap_end,
                s.avg_lap_time_s = $avg,
                s.best_lap_time_s = $best,
                s.lap_count = $count,
                s.driver_code = $driver_code,
                s.session_id = $session_id
            """,
            stint_id=stint_id,
            num=stint.stint_number,
            compound=stint.compound or "",
            lap_start=stint.lap_start,
            lap_end=stint.lap_end,
            avg=stint.avg_lap_time_s,
            best=stint.best_lap_time_s,
            count=stint.lap_count,
            driver_code=driver_code,
            session_id=session.id,
        )

        # Tyre node
        tx.run(
            """
            MERGE (t:Tyre {tyre_id: $tyre_id})
            SET t.compound = $compound, t.life_at_start = $life
            """,
            tyre_id=tyre_id,
            compound=stint.compound or "",
            life=stint.tyre_life_start,
        )

        # Stint → Tyre
        tx.run(
            """
            MATCH (s:Stint {stint_id: $stint_id}), (t:Tyre {tyre_id: $tyre_id})
            MERGE (s)-[:USED]->(t)
            """,
            stint_id=stint_id, tyre_id=tyre_id,
        )

        # Driver → Stint via laps
        for lap in laps:
            if lap.driver_id != stint.driver_id:
                continue
            if stint.lap_start and stint.lap_end and stint.lap_start <= lap.lap_number <= stint.lap_end:
                lap_id = f"{session.id}_{lap.driver_id}_{lap.lap_number}"
                tx.run(
                    """
                    MATCH (l:Lap {lap_id: $lap_id}), (s:Stint {stint_id: $stint_id})
                    MERGE (l)-[:PART_OF_STINT]->(s)
                    """,
                    lap_id=lap_id, stint_id=stint_id,
                )

    # ── Pit Stops ─────────────────────────────────────────────────────────────
    for ps in pit_stops:
        driver_code = next((d.code for d in drivers if d.id == ps.driver_id), None)
        if not driver_code:
            continue

        ps_id = f"{session.id}_{ps.driver_id}_{ps.stop_number}"
        tx.run(
            """
            MERGE (p:PitStop {pitstop_id: $ps_id})
            SET p.lap_number = $lap,
                p.stop_number = $stop_num,
                p.duration_s = $duration,
                p.compound_in = $c_in,
                p.compound_out = $c_out,
                p.driver_code = $driver_code,
                p.session_id = $session_id
            """,
            ps_id=ps_id,
            lap=ps.lap_number,
            stop_num=ps.stop_number,
            duration=ps.pit_duration_s,
            c_in=ps.compound_in or "",
            c_out=ps.compound_out or "",
            driver_code=driver_code,
            session_id=session.id,
        )

        tx.run(
            """
            MATCH (d:Driver {code: $code}), (p:PitStop {pitstop_id: $ps_id})
            MERGE (d)-[:MADE]->(p)
            """,
            code=driver_code, ps_id=ps_id,
        )


def main():
    log.info("Applying Neo4j schema...")
    apply_schema()
    log.info("Ingesting graph from PostgreSQL data...")
    ingest_graph()
    log.info("\n✓ Neo4j graph population complete.")


if __name__ == "__main__":
    main()
