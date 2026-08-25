"""
F1 Analytics: all numerical computations are done here.
The LLM never calculates numbers itself — it calls these functions.
All functions return Pydantic models.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
import numpy as np
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func

from app.db.connection import db_session
from app.db.models import (
    Lap, Stint, PitStop, TelemetrySummary,
    Driver, RaceSession, Race, DriverResult
)


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic result models
# ─────────────────────────────────────────────────────────────────────────────

class LapStats(BaseModel):
    lap_number: int
    lap_time_s: Optional[float]
    sector1_s: Optional[float]
    sector2_s: Optional[float]
    sector3_s: Optional[float]
    compound: Optional[str]
    tyre_life: Optional[int]
    position: Optional[int]


class LapPaceResult(BaseModel):
    driver: str
    session_type: str
    laps: list[LapStats]
    avg_lap_time_s: Optional[float]
    best_lap_time_s: Optional[float]
    median_lap_time_s: Optional[float]
    valid_lap_count: int


class SectorDelta(BaseModel):
    sector: int
    driver_a_best_s: Optional[float]
    driver_b_best_s: Optional[float]
    delta_s: Optional[float]  # positive means A is faster
    advantage: str  # 'driver_a', 'driver_b', or 'tied'


class SectorComparisonResult(BaseModel):
    driver_a: str
    driver_b: str
    session_type: str
    sector_deltas: list[SectorDelta]
    overall_best_lap_delta_s: Optional[float]  # A best - B best
    overall_advantage: str


class TelemetryComparison(BaseModel):
    driver_a: str
    driver_b: str
    session_type: str
    driver_a_avg_speed: Optional[float]
    driver_b_avg_speed: Optional[float]
    driver_a_max_speed: Optional[float]
    driver_b_max_speed: Optional[float]
    driver_a_avg_throttle: Optional[float]
    driver_b_avg_throttle: Optional[float]
    driver_a_full_throttle_pct: Optional[float]
    driver_b_full_throttle_pct: Optional[float]
    driver_a_avg_brake: Optional[float]
    driver_b_avg_brake: Optional[float]
    driver_a_drs_pct: Optional[float]
    driver_b_drs_pct: Optional[float]
    note: str = "Based on fastest lap telemetry summaries"


class StintInfo(BaseModel):
    stint_number: int
    compound: Optional[str]
    lap_start: Optional[int]
    lap_end: Optional[int]
    lap_count: Optional[int]
    avg_lap_time_s: Optional[float]
    best_lap_time_s: Optional[float]
    tyre_life_start: Optional[int]


class PitStopInfo(BaseModel):
    stop_number: int
    lap_number: int
    duration_s: Optional[float]
    compound_in: Optional[str]
    compound_out: Optional[str]


class RaceStrategyResult(BaseModel):
    driver_a: str
    driver_b: str
    session_type: str
    driver_a_stints: list[StintInfo]
    driver_b_stints: list[StintInfo]
    driver_a_pit_stops: list[PitStopInfo]
    driver_b_pit_stops: list[PitStopInfo]
    driver_a_total_stops: int
    driver_b_total_stops: int
    strategy_summary: str


class TyreDegradationResult(BaseModel):
    driver: str
    session_type: str
    stints: list[StintInfo]
    degradation_rate_s_per_lap: Optional[float]  # seconds lost per lap (positive = getting slower)
    total_deg_estimate_s: Optional[float]
    note: str


class RaceResultInfo(BaseModel):
    driver: str
    position: Optional[int]
    grid_position: Optional[int]
    points: Optional[float]
    status: Optional[str]
    team: Optional[str]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_session_id(db: DBSession, session_type: str) -> int | None:
    race = db.query(Race).filter_by(season=2024, round_number=8).first()
    if not race:
        return None
    sess = db.query(RaceSession).filter_by(race_id=race.id, session_type=session_type).first()
    return sess.id if sess else None


def _get_driver_id(db: DBSession, code: str) -> int | None:
    drv = db.query(Driver).filter_by(code=code).first()
    return drv.id if drv else None


def _valid_laps(laps: list[Lap]) -> list[float]:
    """Return valid lap times in seconds (exclude outliers / in/out laps)."""
    times = [l.lap_time_s for l in laps if l.lap_time_s and l.lap_time_s > 60]
    if not times:
        return []
    # Remove obvious outliers (> 110% of best lap)
    best = min(times)
    return [t for t in times if t <= best * 1.1]


# ─────────────────────────────────────────────────────────────────────────────
# Analytics functions
# ─────────────────────────────────────────────────────────────────────────────

def calculate_lap_pace(driver: str, session_type: str = "Race") -> LapPaceResult:
    """Calculate lap pace statistics for a driver in a given session."""
    with db_session() as db:
        session_id = _get_session_id(db, session_type)
        driver_id = _get_driver_id(db, driver)

        if not session_id or not driver_id:
            return LapPaceResult(
                driver=driver, session_type=session_type,
                laps=[], avg_lap_time_s=None, best_lap_time_s=None,
                median_lap_time_s=None, valid_lap_count=0,
            )

        laps = db.query(Lap).filter_by(session_id=session_id, driver_id=driver_id).order_by(Lap.lap_number).all()
        lap_stats = [
            LapStats(
                lap_number=l.lap_number,
                lap_time_s=l.lap_time_s,
                sector1_s=l.sector1_time_s,
                sector2_s=l.sector2_time_s,
                sector3_s=l.sector3_time_s,
                compound=l.compound,
                tyre_life=l.tyre_life,
                position=l.position,
            )
            for l in laps
        ]

        valid = _valid_laps(laps)
        return LapPaceResult(
            driver=driver,
            session_type=session_type,
            laps=lap_stats,
            avg_lap_time_s=round(float(np.mean(valid)), 3) if valid else None,
            best_lap_time_s=round(float(np.min(valid)), 3) if valid else None,
            median_lap_time_s=round(float(np.median(valid)), 3) if valid else None,
            valid_lap_count=len(valid),
        )


def compare_sector_performance(driver_a: str, driver_b: str, session_type: str = "Qualifying") -> SectorComparisonResult:
    """Compare sector times between two drivers."""
    def best_sector(laps: list[Lap], sector: int) -> float | None:
        col_map = {1: "sector1_time_s", 2: "sector2_time_s", 3: "sector3_time_s"}
        times = [getattr(l, col_map[sector]) for l in laps if getattr(l, col_map[sector])]
        return round(min(times), 3) if times else None

    with db_session() as db:
        sid = _get_session_id(db, session_type)
        did_a = _get_driver_id(db, driver_a)
        did_b = _get_driver_id(db, driver_b)

        if not sid:
            return SectorComparisonResult(
                driver_a=driver_a, driver_b=driver_b, session_type=session_type,
                sector_deltas=[], overall_best_lap_delta_s=None, overall_advantage="unknown",
            )

        laps_a = db.query(Lap).filter_by(session_id=sid, driver_id=did_a).all() if did_a else []
        laps_b = db.query(Lap).filter_by(session_id=sid, driver_id=did_b).all() if did_b else []

        deltas = []
        for s in [1, 2, 3]:
            best_a = best_sector(laps_a, s)
            best_b = best_sector(laps_b, s)
            if best_a is not None and best_b is not None:
                delta = round(best_b - best_a, 3)  # positive = A faster
                advantage = "driver_a" if delta > 0.01 else ("driver_b" if delta < -0.01 else "tied")
            else:
                delta = None
                advantage = "unknown"
            deltas.append(SectorDelta(
                sector=s,
                driver_a_best_s=best_a,
                driver_b_best_s=best_b,
                delta_s=delta,
                advantage=advantage,
            ))

        valid_a = _valid_laps(laps_a)
        valid_b = _valid_laps(laps_b)
        best_a = round(min(valid_a), 3) if valid_a else None
        best_b = round(min(valid_b), 3) if valid_b else None
        overall_delta = round(best_b - best_a, 3) if best_a and best_b else None
        overall_adv = "driver_a" if (overall_delta and overall_delta > 0.01) else (
            "driver_b" if (overall_delta and overall_delta < -0.01) else "tied"
        )

        return SectorComparisonResult(
            driver_a=driver_a,
            driver_b=driver_b,
            session_type=session_type,
            sector_deltas=deltas,
            overall_best_lap_delta_s=overall_delta,
            overall_advantage=overall_adv,
        )


def compare_driver_telemetry(driver_a: str, driver_b: str, session_type: str = "Qualifying") -> TelemetryComparison:
    """Compare telemetry summaries for two drivers (fastest lap)."""
    with db_session() as db:
        sid = _get_session_id(db, session_type)
        did_a = _get_driver_id(db, driver_a)
        did_b = _get_driver_id(db, driver_b)

        def get_summary(did: int | None) -> TelemetrySummary | None:
            if not did or not sid:
                return None
            return db.query(TelemetrySummary).filter_by(session_id=sid, driver_id=did).first()

        ts_a = get_summary(did_a)
        ts_b = get_summary(did_b)

        return TelemetryComparison(
            driver_a=driver_a,
            driver_b=driver_b,
            session_type=session_type,
            driver_a_avg_speed=ts_a.avg_speed_kmh if ts_a else None,
            driver_b_avg_speed=ts_b.avg_speed_kmh if ts_b else None,
            driver_a_max_speed=ts_a.max_speed_kmh if ts_a else None,
            driver_b_max_speed=ts_b.max_speed_kmh if ts_b else None,
            driver_a_avg_throttle=ts_a.avg_throttle_pct if ts_a else None,
            driver_b_avg_throttle=ts_b.avg_throttle_pct if ts_b else None,
            driver_a_full_throttle_pct=ts_a.full_throttle_pct if ts_a else None,
            driver_b_full_throttle_pct=ts_b.full_throttle_pct if ts_b else None,
            driver_a_avg_brake=ts_a.avg_brake_pct if ts_a else None,
            driver_b_avg_brake=ts_b.avg_brake_pct if ts_b else None,
            driver_a_drs_pct=ts_a.drs_pct if ts_a else None,
            driver_b_drs_pct=ts_b.drs_pct if ts_b else None,
        )


def calculate_tyre_degradation(driver: str, session_type: str = "Race") -> TyreDegradationResult:
    """Estimate tyre degradation rate across stints."""
    with db_session() as db:
        sid = _get_session_id(db, session_type)
        did = _get_driver_id(db, driver)

        if not sid or not did:
            return TyreDegradationResult(
                driver=driver, session_type=session_type, stints=[],
                degradation_rate_s_per_lap=None, total_deg_estimate_s=None,
                note="No data available",
            )

        stints = db.query(Stint).filter_by(session_id=sid, driver_id=did).order_by(Stint.stint_number).all()
        laps = db.query(Lap).filter_by(session_id=sid, driver_id=did).order_by(Lap.lap_number).all()

        stint_infos = [
            StintInfo(
                stint_number=s.stint_number,
                compound=s.compound,
                lap_start=s.lap_start,
                lap_end=s.lap_end,
                lap_count=s.lap_count,
                avg_lap_time_s=s.avg_lap_time_s,
                best_lap_time_s=s.best_lap_time_s,
                tyre_life_start=s.tyre_life_start,
            )
            for s in stints
        ]

        # Compute degradation by linear regression within the race stint
        # Group laps by stint, compute time slope
        deg_rates = []
        for stint in stints:
            if not stint.lap_start or not stint.lap_end or stint.lap_count < 4:
                continue
            stint_laps = [
                l for l in laps
                if l.lap_number and stint.lap_start <= l.lap_number <= stint.lap_end
                and l.lap_time_s and l.lap_time_s > 60 and l.lap_time_s < 120
            ]
            if len(stint_laps) < 4:
                continue
            lap_nums = np.array([l.lap_number for l in stint_laps], dtype=float)
            lap_times = np.array([l.lap_time_s for l in stint_laps], dtype=float)
            # Linear regression
            coeffs = np.polyfit(lap_nums - lap_nums[0], lap_times, 1)
            deg_rates.append(coeffs[0])  # seconds per lap

        deg_rate = round(float(np.mean(deg_rates)), 4) if deg_rates else None

        # Estimate total degradation over the race
        valid_times = _valid_laps(laps)
        total_deg = None
        if deg_rate and len(laps) > 10:
            total_deg = round(deg_rate * len(laps), 2)

        note = (
            f"Degradation rate estimated via linear regression on each stint. "
            f"Positive = lap times increasing (tyres degrading). "
            f"Based on {len(stints)} stints in {session_type}."
        )

        return TyreDegradationResult(
            driver=driver,
            session_type=session_type,
            stints=stint_infos,
            degradation_rate_s_per_lap=deg_rate,
            total_deg_estimate_s=total_deg,
            note=note,
        )


def compare_race_strategy(driver_a: str, driver_b: str, session_type: str = "Race") -> RaceStrategyResult:
    """Compare the full race strategy of two drivers."""
    with db_session() as db:
        sid = _get_session_id(db, session_type)
        did_a = _get_driver_id(db, driver_a)
        did_b = _get_driver_id(db, driver_b)

        def get_stints(did: int | None) -> list[StintInfo]:
            if not did or not sid:
                return []
            stints = db.query(Stint).filter_by(session_id=sid, driver_id=did).order_by(Stint.stint_number).all()
            return [
                StintInfo(
                    stint_number=s.stint_number,
                    compound=s.compound,
                    lap_start=s.lap_start,
                    lap_end=s.lap_end,
                    lap_count=s.lap_count,
                    avg_lap_time_s=s.avg_lap_time_s,
                    best_lap_time_s=s.best_lap_time_s,
                    tyre_life_start=s.tyre_life_start,
                )
                for s in stints
            ]

        def get_pit_stops(did: int | None) -> list[PitStopInfo]:
            if not did or not sid:
                return []
            pits = db.query(PitStop).filter_by(session_id=sid, driver_id=did).order_by(PitStop.stop_number).all()
            return [
                PitStopInfo(
                    stop_number=p.stop_number,
                    lap_number=p.lap_number,
                    duration_s=p.pit_duration_s,
                    compound_in=p.compound_in,
                    compound_out=p.compound_out,
                )
                for p in pits
            ]

        stints_a = get_stints(did_a)
        stints_b = get_stints(did_b)
        pits_a = get_pit_stops(did_a)
        pits_b = get_pit_stops(did_b)

        # Build summary
        def fmt_strategy(driver: str, stints: list[StintInfo], pits: list[PitStopInfo]) -> str:
            compounds = " → ".join([s.compound or "?" for s in stints])
            stops = len(pits)
            return f"{driver}: {stops}-stop | Compounds: {compounds}"

        summary = fmt_strategy(driver_a, stints_a, pits_a) + " | " + fmt_strategy(driver_b, stints_b, pits_b)

        return RaceStrategyResult(
            driver_a=driver_a,
            driver_b=driver_b,
            session_type=session_type,
            driver_a_stints=stints_a,
            driver_b_stints=stints_b,
            driver_a_pit_stops=pits_a,
            driver_b_pit_stops=pits_b,
            driver_a_total_stops=len(pits_a),
            driver_b_total_stops=len(pits_b),
            strategy_summary=summary,
        )


def get_race_results(session_type: str = "Race") -> list[RaceResultInfo]:
    """Get race/qualifying results for all available drivers."""
    with db_session() as db:
        sid = _get_session_id(db, session_type)
        if not sid:
            return []

        results = db.query(DriverResult).filter_by(session_id=sid).all()
        out = []
        for r in results:
            drv = db.query(Driver).filter_by(id=r.driver_id).first()
            out.append(RaceResultInfo(
                driver=drv.code if drv else str(r.driver_id),
                position=r.position,
                grid_position=r.grid_position,
                points=r.points,
                status=r.status,
                team=None,
            ))
        return sorted(out, key=lambda x: (x.position or 999))
