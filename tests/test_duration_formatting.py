from pyqwk.core import format_duration

def test_format_duration_seconds():
    assert format_duration(0) == "0.0s"
    assert format_duration(45.5) == "45.5s"
    assert format_duration(59.9) == "59.9s"

def test_format_duration_minutes():
    assert format_duration(60.0) == "1.0m"
    assert format_duration(125.0) == "2.1m"
    assert format_duration(3599.9) == "60.0m"

def test_format_duration_hours():
    assert format_duration(3600.0) == "1.0h"
    assert format_duration(3660.0) == "1.0h"
    assert format_duration(7200.0) == "2.0h"
    assert format_duration(86399.9) == "24.0h"

def test_format_duration_days():
    assert format_duration(86400.0) == "1.0d"
    assert format_duration(90000.0) == "1.0d"
    assert format_duration(172800.0) == "2.0d"

def test_format_duration_negative():
    assert format_duration(-10) == "-10.0s"
