"""Unit test for FastF1 ingestion helper functions."""
import pytest
from scripts.ingest_monaco import safe_float, safe_int, safe_bool, safe_str


def test_safe_converters():
    assert safe_float(12.34) == 12.34
    assert safe_float(None) is None
    assert safe_int(15) == 15
    assert safe_int("15") == 15
    assert safe_bool(True) is True
    assert safe_bool(0) is False
    assert safe_str(" LEC ") == "LEC"
    assert safe_str(None) is None
