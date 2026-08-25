"""Tests for PostgreSQL ORM models structure and connection string."""
import pytest
from app.config import get_settings
from app.db.models import Team, Driver, Race, RaceSession, Lap, Stint, PitStop, Weather, TelemetrySummary


def test_config_postgres_dsn():
    settings = get_settings()
    dsn = settings.postgres_dsn
    assert "postgresql+psycopg2://" in dsn
    assert settings.postgres_db in dsn


def test_models_tablename():
    assert Team.__tablename__ == "teams"
    assert Driver.__tablename__ == "drivers"
    assert Race.__tablename__ == "races"
    assert RaceSession.__tablename__ == "sessions"
    assert Lap.__tablename__ == "laps"
    assert Stint.__tablename__ == "stints"
    assert PitStop.__tablename__ == "pit_stops"
    assert Weather.__tablename__ == "weather"
    assert TelemetrySummary.__tablename__ == "telemetry_summaries"
