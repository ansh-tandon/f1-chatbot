"""
Monaco 2024 FastF1 Ingestion Script
====================================
Loads 2024 Monaco Qualifying + Race for LEC and NOR.
Populates PostgreSQL and caches raw Parquet files.

Run from backend/ directory:
    python scripts/ingest_monaco.py
"""
import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Allow imports from app/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
import fastf1
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.connection import db_session
from app.db.models import (
    Team, Driver, Race, RaceSession, DriverResult,
    Lap, Stint, PitStop, Weather, TelemetrySummary
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

settings = get_settings()

# ── Target scope ──────────────────────────────────────────────────────────────
YEAR = 2024
GP_NAME = "Monaco"
DRIVERS = ["LEC", "NOR"]
SESSIONS_TO_LOAD = ["Qualifying", "Race"]

# ── Raw data cache dir ────────────────────────────────────────────────────────
RAW_DIR = Path(__file__).parent.parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

FASTF1_CACHE = Path(settings.fastf1_cache_dir)
FASTF1_CACHE.mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(str(FASTF1_CACHE))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def safe_float(val) -> float | None:
    """Convert timedelta/float to seconds, returning None on error."""
    try:
        if pd.isna(val):
            return None
        if hasattr(val, "total_seconds"):
            return val.total_seconds()
        return float(val)
    except Exception:
        return None


def safe_int(val) -> int | None:
    try:
        if pd.isna(val):
            return None
        return int(val)
    except Exception:
        return None


def safe_bool(val) -> bool | None:
    try:
        if pd.isna(val):
            return None
        return bool(val)
    except Exception:
        return None


def safe_str(val) -> str | None:
    try:
        if pd.isna(val):
            return None
        return str(val).strip()
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Ensure teams and drivers exist
# ─────────────────────────────────────────────────────────────────────────────

TEAM_DATA = {
    "LEC": {"team_name": "Ferrari", "team_short": "FER", "driver_name": "Charles Leclerc", "number": 16},
    "NOR": {"team_name": "McLaren", "team_short": "MCL", "driver_name": "Lando Norris", "number": 4},
}


def upsert_teams_and_drivers(db: Session) -> dict[str, int]:
    """Return mapping of driver_code -> driver.id."""
    driver_ids = {}
    for code, info in TEAM_DATA.items():
        # Team
        team = db.query(Team).filter_by(name=info["team_name"]).first()
        if not team:
            team = Team(name=info["team_name"], short_name=info["team_short"])
            db.add(team)
            db.flush()
        log.info(f"Team: {team.name} (id={team.id})")

        # Driver
        driver = db.query(Driver).filter_by(code=code).first()
        if not driver:
            driver = Driver(
                code=code,
                full_name=info["driver_name"],
                number=info["number"],
                team_id=team.id,
            )
            db.add(driver)
            db.flush()
        log.info(f"Driver: {driver.code} / {driver.full_name} (id={driver.id})")
        driver_ids[code] = driver.id

    return driver_ids


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Upsert Race row
# ─────────────────────────────────────────────────────────────────────────────

def upsert_race(db: Session) -> Race:
    race = db.query(Race).filter_by(season=YEAR, round_number=8).first()  # Monaco is round 8 in 2024
    if not race:
        race = Race(
            season=YEAR,
            round_number=8,
            name="Monaco Grand Prix",
            circuit_name="Circuit de Monaco",
            country="Monaco",
            race_date=datetime(2024, 5, 26).date(),
        )
        db.add(race)
        db.flush()
    log.info(f"Race: {race.name} (id={race.id})")
    return race


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Load a FastF1 session
# ─────────────────────────────────────────────────────────────────────────────

def load_ff1_session(session_type: str) -> fastf1.core.Session:
    log.info(f"Loading FastF1 session: {YEAR} {GP_NAME} {session_type} ...")
    sess = fastf1.get_session(YEAR, GP_NAME, session_type)
    sess.load(
        laps=True,
        telemetry=True,
        weather=True,
        messages=False,
    )
    log.info(f"Session loaded. Drivers present: {list(sess.drivers)}")
    return sess


# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Ingest laps
# ─────────────────────────────────────────────────────────────────────────────

def ingest_laps(db: Session, ff1_sess, pg_session: RaceSession, driver_ids: dict[str, int]):
    for drv_code in DRIVERS:
        try:
            drv_laps = ff1_sess.laps.pick_driver(drv_code)
        except Exception as e:
            log.warning(f"Could not pick laps for {drv_code}: {e}")
            continue

        if drv_laps.empty:
            log.warning(f"No laps found for {drv_code}")
            continue

        driver_id = driver_ids[drv_code]

        # Cache raw laps as Parquet
        parquet_path = RAW_DIR / f"laps_{YEAR}_monaco_{pg_session.session_type.lower()}_{drv_code}.parquet"
        try:
            drv_laps.to_parquet(parquet_path, index=False)
            log.info(f"Cached {len(drv_laps)} laps to {parquet_path}")
        except Exception as e:
            log.warning(f"Could not cache Parquet for {drv_code}: {e}")

        for _, row in drv_laps.iterrows():
            lap_num = safe_int(row.get("LapNumber"))
            if lap_num is None:
                continue

            # Check for existing lap
            existing = db.query(Lap).filter_by(
                session_id=pg_session.id,
                driver_id=driver_id,
                lap_number=lap_num,
            ).first()
            if existing:
                continue

            lap = Lap(
                session_id=pg_session.id,
                driver_id=driver_id,
                lap_number=lap_num,
                lap_time_s=safe_float(row.get("LapTime")),
                sector1_time_s=safe_float(row.get("Sector1Time")),
                sector2_time_s=safe_float(row.get("Sector2Time")),
                sector3_time_s=safe_float(row.get("Sector3Time")),
                speed_trap_kmh=safe_float(row.get("SpeedST")),
                compound=safe_str(row.get("Compound")),
                tyre_life=safe_int(row.get("TyreLife")),
                is_personal_best=safe_bool(row.get("IsPersonalBest")),
                is_accurate=safe_bool(row.get("IsAccurate")),
                track_status=safe_str(row.get("TrackStatus")),
                position=safe_int(row.get("Position")),
            )
            db.add(lap)

        log.info(f"Ingested laps for {drv_code} in {pg_session.session_type}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Ingest stints
# ─────────────────────────────────────────────────────────────────────────────

def ingest_stints(db: Session, ff1_sess, pg_session: RaceSession, driver_ids: dict[str, int]):
    for drv_code in DRIVERS:
        driver_id = driver_ids[drv_code]
        try:
            drv_laps = ff1_sess.laps.pick_driver(drv_code)
            if drv_laps.empty:
                continue
        except Exception as e:
            log.warning(f"Stints: could not pick laps for {drv_code}: {e}")
            continue

        # Group by Stint number
        if "Stint" not in drv_laps.columns:
            log.warning(f"No Stint column for {drv_code}")
            continue

        stint_groups = drv_laps.groupby("Stint")
        for stint_num, stint_laps in stint_groups:
            existing = db.query(Stint).filter_by(
                session_id=pg_session.id,
                driver_id=driver_id,
                stint_number=int(stint_num),
            ).first()
            if existing:
                continue

            lap_times = [
                safe_float(t)
                for t in stint_laps["LapTime"]
                if safe_float(t) is not None
            ]

            compound = safe_str(stint_laps["Compound"].iloc[0]) if "Compound" in stint_laps else None
            tyre_life_start = safe_int(stint_laps["TyreLife"].iloc[0]) if "TyreLife" in stint_laps else None

            stint = Stint(
                session_id=pg_session.id,
                driver_id=driver_id,
                stint_number=int(stint_num),
                compound=compound,
                tyre_life_start=tyre_life_start,
                lap_start=safe_int(stint_laps["LapNumber"].min()),
                lap_end=safe_int(stint_laps["LapNumber"].max()),
                avg_lap_time_s=float(np.mean(lap_times)) if lap_times else None,
                best_lap_time_s=float(np.min(lap_times)) if lap_times else None,
                lap_count=len(stint_laps),
            )
            db.add(stint)

        log.info(f"Ingested stints for {drv_code} in {pg_session.session_type}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 6: Ingest pit stops
# ─────────────────────────────────────────────────────────────────────────────

def ingest_pit_stops(db: Session, ff1_sess, pg_session: RaceSession, driver_ids: dict[str, int]):
    """Derive pit stops from lap data (PitInTime/PitOutTime)."""
    for drv_code in DRIVERS:
        driver_id = driver_ids[drv_code]
        try:
            drv_laps = ff1_sess.laps.pick_driver(drv_code)
            if drv_laps.empty:
                continue
        except Exception as e:
            log.warning(f"Pit stops: could not pick laps for {drv_code}: {e}")
            continue

        if "PitInTime" not in drv_laps.columns or "PitOutTime" not in drv_laps.columns:
            log.warning(f"No PitInTime/PitOutTime for {drv_code}")
            continue

        # Rows where driver pitted (has PitInTime)
        pit_laps = drv_laps[drv_laps["PitInTime"].notna()]
        stop_num = 1

        # Get compound sequence for in/out detection
        compounds = drv_laps[["LapNumber", "Compound", "Stint"]].copy()

        for _, row in pit_laps.iterrows():
            lap_num = safe_int(row.get("LapNumber"))
            if lap_num is None:
                continue

            # Pit duration: PitOutTime (next lap start) - PitInTime
            pit_in = row.get("PitInTime")
            # Find next lap PitOutTime
            next_lap = drv_laps[drv_laps["LapNumber"] == lap_num + 1]
            pit_out = next_lap["PitOutTime"].values[0] if not next_lap.empty and "PitOutTime" in next_lap.columns else None

            pit_duration = None
            if pit_out is not None and not pd.isna(pit_out) and not pd.isna(pit_in):
                try:
                    pit_duration = (pit_out - pit_in).total_seconds()
                except Exception:
                    pass

            # Compound in/out
            current_row = compounds[compounds["LapNumber"] == lap_num]
            next_row = compounds[compounds["LapNumber"] == lap_num + 1]
            compound_in = safe_str(current_row["Compound"].values[0]) if not current_row.empty else None
            compound_out = safe_str(next_row["Compound"].values[0]) if not next_row.empty else None

            existing = db.query(PitStop).filter_by(
                session_id=pg_session.id,
                driver_id=driver_id,
                lap_number=lap_num,
            ).first()
            if existing:
                continue

            ps = PitStop(
                session_id=pg_session.id,
                driver_id=driver_id,
                lap_number=lap_num,
                stop_number=stop_num,
                pit_duration_s=pit_duration,
                compound_in=compound_in,
                compound_out=compound_out,
            )
            db.add(ps)
            stop_num += 1

        log.info(f"Ingested pit stops for {drv_code} in {pg_session.session_type}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 7: Ingest weather
# ─────────────────────────────────────────────────────────────────────────────

def ingest_weather(db: Session, ff1_sess, pg_session: RaceSession):
    try:
        weather_df = ff1_sess.weather_data
        if weather_df is None or weather_df.empty:
            log.warning("No weather data available")
            return
    except Exception as e:
        log.warning(f"Weather data error: {e}")
        return

    for _, row in weather_df.iterrows():
        time_offset = safe_float(row.get("Time"))

        w = Weather(
            session_id=pg_session.id,
            time_offset_s=time_offset,
            air_temp_c=safe_float(row.get("AirTemp")),
            track_temp_c=safe_float(row.get("TrackTemp")),
            humidity_pct=safe_float(row.get("Humidity")),
            pressure_mbar=safe_float(row.get("Pressure")),
            wind_speed_ms=safe_float(row.get("WindSpeed")),
            wind_direction_deg=safe_float(row.get("WindDirection")),
            rainfall=safe_bool(row.get("Rainfall")),
        )
        db.add(w)

    log.info(f"Ingested {len(weather_df)} weather records for {pg_session.session_type}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 8: Ingest driver results
# ─────────────────────────────────────────────────────────────────────────────

def ingest_driver_results(db: Session, ff1_sess, pg_session: RaceSession, driver_ids: dict[str, int]):
    try:
        results = ff1_sess.results
    except Exception as e:
        log.warning(f"Could not load results: {e}")
        return

    if results is None or results.empty:
        log.warning("No results available")
        return

    for drv_code in DRIVERS:
        driver_id = driver_ids[drv_code]
        drv_row = results[results["Abbreviation"] == drv_code]
        if drv_row.empty:
            log.warning(f"No result row for {drv_code}")
            continue

        drv_row = drv_row.iloc[0]

        existing = db.query(DriverResult).filter_by(
            session_id=pg_session.id,
            driver_id=driver_id,
        ).first()
        if existing:
            continue

        result = DriverResult(
            session_id=pg_session.id,
            driver_id=driver_id,
            position=safe_int(drv_row.get("Position")),
            grid_position=safe_int(drv_row.get("GridPosition")),
            points=safe_float(drv_row.get("Points")),
            status=safe_str(drv_row.get("Status")),
        )
        db.add(result)

    log.info(f"Ingested driver results for {pg_session.session_type}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 9: Ingest telemetry summaries (aggregated)
# ─────────────────────────────────────────────────────────────────────────────

def ingest_telemetry_summaries(db: Session, ff1_sess, pg_session: RaceSession, driver_ids: dict[str, int]):
    for drv_code in DRIVERS:
        driver_id = driver_ids[drv_code]
        try:
            drv_laps = ff1_sess.laps.pick_driver(drv_code)
            if drv_laps.empty:
                continue
        except Exception as e:
            log.warning(f"Telemetry summary: could not pick laps for {drv_code}: {e}")
            continue

        # For each lap, compute a telemetry summary
        fast_lap = None
        try:
            fast_lap = drv_laps.pick_fastest()
        except Exception:
            pass

        if fast_lap is None:
            log.warning(f"No fastest lap found for {drv_code}")
            continue

        try:
            tel = fast_lap.get_telemetry()
        except Exception as e:
            log.warning(f"Could not get telemetry for {drv_code} fastest lap: {e}")
            continue

        if tel is None or tel.empty:
            log.warning(f"Empty telemetry for {drv_code}")
            continue

        # Cache telemetry
        tel_path = RAW_DIR / f"telemetry_{YEAR}_monaco_{pg_session.session_type.lower()}_{drv_code}_fastest.parquet"
        try:
            tel.to_parquet(tel_path, index=False)
        except Exception:
            pass

        # Compute aggregates
        avg_speed = safe_float(tel["Speed"].mean()) if "Speed" in tel else None
        max_speed = safe_float(tel["Speed"].max()) if "Speed" in tel else None
        avg_throttle = safe_float(tel["Throttle"].mean()) if "Throttle" in tel else None

        # Brake column is boolean or 0/1
        avg_brake = None
        if "Brake" in tel:
            brake_vals = pd.to_numeric(tel["Brake"], errors="coerce")
            avg_brake = safe_float(brake_vals.mean())

        drs_pct = None
        if "DRS" in tel:
            # DRS > 10 usually means open
            drs_open = (tel["DRS"] > 10).sum()
            drs_pct = safe_float(drs_open / len(tel) * 100) if len(tel) > 0 else None

        full_throttle_pct = None
        if "Throttle" in tel:
            ft = (tel["Throttle"] == 100).sum()
            full_throttle_pct = safe_float(ft / len(tel) * 100)

        lap_num = safe_int(fast_lap.get("LapNumber"))

        existing = db.query(TelemetrySummary).filter_by(
            session_id=pg_session.id,
            driver_id=driver_id,
            lap_number=lap_num,
        ).first()
        if existing:
            continue

        ts = TelemetrySummary(
            session_id=pg_session.id,
            driver_id=driver_id,
            lap_number=lap_num,
            avg_speed_kmh=avg_speed,
            max_speed_kmh=max_speed,
            avg_throttle_pct=avg_throttle,
            avg_brake_pct=avg_brake,
            drs_pct=drs_pct,
            full_throttle_pct=full_throttle_pct,
        )
        db.add(ts)
        log.info(f"Ingested telemetry summary for {drv_code} lap {lap_num}")


# ─────────────────────────────────────────────────────────────────────────────
# Main ingestion flow
# ─────────────────────────────────────────────────────────────────────────────

def ingest_session(session_type: str, race: Race, driver_ids: dict[str, int]):
    log.info(f"\n{'='*60}")
    log.info(f"Ingesting session: {session_type}")
    log.info(f"{'='*60}")

    ff1_sess = load_ff1_session(session_type)

    with db_session() as db:
        # Upsert session row
        pg_session = db.query(RaceSession).filter_by(
            race_id=race.id,
            session_type=session_type,
        ).first()

        if not pg_session:
            pg_session = RaceSession(
                race_id=race.id,
                session_type=session_type,
                session_date=ff1_sess.date if hasattr(ff1_sess, "date") else None,
            )
            db.add(pg_session)
            db.flush()

        ingest_driver_results(db, ff1_sess, pg_session, driver_ids)
        ingest_laps(db, ff1_sess, pg_session, driver_ids)
        ingest_stints(db, ff1_sess, pg_session, driver_ids)
        ingest_pit_stops(db, ff1_sess, pg_session, driver_ids)
        ingest_weather(db, ff1_sess, pg_session)
        ingest_telemetry_summaries(db, ff1_sess, pg_session, driver_ids)

    log.info(f"Session {session_type} ingestion complete.")


def main():
    log.info("Starting Monaco 2024 ingestion for LEC and NOR...")

    with db_session() as db:
        driver_ids = upsert_teams_and_drivers(db)
        race = upsert_race(db)
        race_id = race.id

    # Reload race object for subsequent sessions (avoid detached session issues)
    with db_session() as db:
        race = db.query(Race).filter_by(id=race_id).first()

        for sess_type in SESSIONS_TO_LOAD:
            try:
                ingest_session(sess_type, race, driver_ids)
            except Exception as e:
                log.error(f"Failed to ingest {sess_type}: {e}", exc_info=True)
                log.warning("Continuing with next session...")

    log.info("\n✓ Monaco 2024 ingestion complete.")
    log.info("Run scripts/init_neo4j.py next to populate the Context Graph.")


if __name__ == "__main__":
    main()
