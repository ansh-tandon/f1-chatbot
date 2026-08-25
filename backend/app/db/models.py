"""SQLAlchemy ORM models for F1 structured data."""
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Date, Text,
    ForeignKey, UniqueConstraint, Index, Numeric
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(20))
    nationality: Mapped[Optional[str]] = mapped_column(String(50))

    drivers: Mapped[list["Driver"]] = relationship("Driver", back_populates="team")


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)  # e.g. LEC
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    number: Mapped[Optional[int]] = mapped_column(Integer)
    nationality: Mapped[Optional[str]] = mapped_column(String(50))
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"))

    team: Mapped[Optional["Team"]] = relationship("Team", back_populates="drivers")
    laps: Mapped[list["Lap"]] = relationship("Lap", back_populates="driver")
    stints: Mapped[list["Stint"]] = relationship("Stint", back_populates="driver")
    pit_stops: Mapped[list["PitStop"]] = relationship("PitStop", back_populates="driver")


class Race(Base):
    __tablename__ = "races"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    circuit_name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(100))
    race_date: Mapped[Optional[date]] = mapped_column(Date)

    __table_args__ = (UniqueConstraint("season", "round_number", name="uq_race_season_round"),)

    sessions: Mapped[list["RaceSession"]] = relationship("RaceSession", back_populates="race")


class RaceSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), nullable=False)
    session_type: Mapped[str] = mapped_column(String(50), nullable=False)  # Qualifying / Race
    session_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    total_laps: Mapped[Optional[int]] = mapped_column(Integer)

    __table_args__ = (UniqueConstraint("race_id", "session_type", name="uq_session_race_type"),)

    race: Mapped["Race"] = relationship("Race", back_populates="sessions")
    laps: Mapped[list["Lap"]] = relationship("Lap", back_populates="session")
    stints: Mapped[list["Stint"]] = relationship("Stint", back_populates="session")
    pit_stops: Mapped[list["PitStop"]] = relationship("PitStop", back_populates="session")
    weather_records: Mapped[list["Weather"]] = relationship("Weather", back_populates="session")
    driver_results: Mapped[list["DriverResult"]] = relationship("DriverResult", back_populates="session")


class DriverResult(Base):
    """Per-driver result for a session (qualifying position, race finish, etc.)."""
    __tablename__ = "driver_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    position: Mapped[Optional[int]] = mapped_column(Integer)
    grid_position: Mapped[Optional[int]] = mapped_column(Integer)
    points: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[Optional[str]] = mapped_column(String(100))  # Finished, DNF, etc.
    best_lap_time_s: Mapped[Optional[float]] = mapped_column(Float)  # seconds
    gap_to_leader_s: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (UniqueConstraint("session_id", "driver_id", name="uq_result_session_driver"),)

    session: Mapped["RaceSession"] = relationship("RaceSession", back_populates="driver_results")
    driver: Mapped["Driver"] = relationship("Driver")


class Lap(Base):
    __tablename__ = "laps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    lap_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lap_time_s: Mapped[Optional[float]] = mapped_column(Float)        # seconds
    sector1_time_s: Mapped[Optional[float]] = mapped_column(Float)
    sector2_time_s: Mapped[Optional[float]] = mapped_column(Float)
    sector3_time_s: Mapped[Optional[float]] = mapped_column(Float)
    speed_trap_kmh: Mapped[Optional[float]] = mapped_column(Float)
    compound: Mapped[Optional[str]] = mapped_column(String(20))       # SOFT/MEDIUM/HARD
    tyre_life: Mapped[Optional[int]] = mapped_column(Integer)         # laps on this set
    is_personal_best: Mapped[Optional[bool]] = mapped_column(Boolean)
    is_accurate: Mapped[Optional[bool]] = mapped_column(Boolean)
    track_status: Mapped[Optional[str]] = mapped_column(String(10))
    position: Mapped[Optional[int]] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("session_id", "driver_id", "lap_number", name="uq_lap_session_driver_num"),
        Index("ix_laps_session_driver", "session_id", "driver_id"),
    )

    session: Mapped["RaceSession"] = relationship("RaceSession", back_populates="laps")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="laps")


class Stint(Base):
    __tablename__ = "stints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    stint_number: Mapped[int] = mapped_column(Integer, nullable=False)
    compound: Mapped[Optional[str]] = mapped_column(String(20))
    tyre_life_start: Mapped[Optional[int]] = mapped_column(Integer)
    lap_start: Mapped[Optional[int]] = mapped_column(Integer)
    lap_end: Mapped[Optional[int]] = mapped_column(Integer)
    avg_lap_time_s: Mapped[Optional[float]] = mapped_column(Float)
    best_lap_time_s: Mapped[Optional[float]] = mapped_column(Float)
    lap_count: Mapped[Optional[int]] = mapped_column(Integer)

    session: Mapped["RaceSession"] = relationship("RaceSession", back_populates="stints")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="stints")


class PitStop(Base):
    __tablename__ = "pit_stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    lap_number: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pit_duration_s: Mapped[Optional[float]] = mapped_column(Float)
    compound_in: Mapped[Optional[str]] = mapped_column(String(20))
    compound_out: Mapped[Optional[str]] = mapped_column(String(20))

    session: Mapped["RaceSession"] = relationship("RaceSession", back_populates="pit_stops")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="pit_stops")


class Weather(Base):
    __tablename__ = "weather"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    time_offset_s: Mapped[Optional[float]] = mapped_column(Float)  # seconds into session
    air_temp_c: Mapped[Optional[float]] = mapped_column(Float)
    track_temp_c: Mapped[Optional[float]] = mapped_column(Float)
    humidity_pct: Mapped[Optional[float]] = mapped_column(Float)
    pressure_mbar: Mapped[Optional[float]] = mapped_column(Float)
    wind_speed_ms: Mapped[Optional[float]] = mapped_column(Float)
    wind_direction_deg: Mapped[Optional[float]] = mapped_column(Float)
    rainfall: Mapped[Optional[bool]] = mapped_column(Boolean)

    session: Mapped["RaceSession"] = relationship("RaceSession", back_populates="weather_records")


class TelemetrySummary(Base):
    """Aggregated telemetry statistics per driver per session (NOT raw per-sample data)."""
    __tablename__ = "telemetry_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    lap_number: Mapped[Optional[int]] = mapped_column(Integer)  # None = session aggregate
    avg_speed_kmh: Mapped[Optional[float]] = mapped_column(Float)
    max_speed_kmh: Mapped[Optional[float]] = mapped_column(Float)
    avg_throttle_pct: Mapped[Optional[float]] = mapped_column(Float)
    avg_brake_pct: Mapped[Optional[float]] = mapped_column(Float)
    drs_pct: Mapped[Optional[float]] = mapped_column(Float)          # % of lap with DRS open
    full_throttle_pct: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("session_id", "driver_id", "lap_number", name="uq_telem_session_driver_lap"),
    )

    session: Mapped["RaceSession"] = relationship("RaceSession")
    driver: Mapped["Driver"] = relationship("Driver")
