"""Tests for Pydantic models in analytics module."""
import pytest
from app.f1.analytics import SectorDelta, SectorComparisonResult, TelemetryComparison


def test_sector_delta():
    sd = SectorDelta(
        sector=1,
        driver_a_best_s=18.5,
        driver_b_best_s=18.7,
        delta_s=0.2,
        advantage="driver_a",
    )
    assert sd.sector == 1
    assert sd.delta_s == 0.2
    assert sd.advantage == "driver_a"


def test_telemetry_comparison_defaults():
    tc = TelemetryComparison(
        driver_a="LEC",
        driver_b="NOR",
        session_type="Qualifying",
        driver_a_avg_speed=215.4,
        driver_b_avg_speed=212.1,
        driver_a_max_speed=290.0,
        driver_b_max_speed=288.5,
        driver_a_avg_throttle=75.0,
        driver_b_avg_throttle=72.0,
        driver_a_full_throttle_pct=60.0,
        driver_b_full_throttle_pct=58.0,
        driver_a_avg_brake=10.0,
        driver_b_avg_brake=12.0,
        driver_a_drs_pct=15.0,
        driver_b_drs_pct=14.0,
    )
    assert tc.driver_a == "LEC"
    assert tc.driver_b_max_speed == 288.5
