import sys
from pathlib import Path
import datetime

# Ensure the root directory is in sys.path so we can import pyqwk.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyqwk.core import _parse_qwk_date

class TestDateParsing:
    """Test suite for _parse_qwk_date function."""

    def test_parse_standard_1900s_date(self):
        # 12-31-99 -> Dec 31, 1999
        dt = _parse_qwk_date("12-31-99", "23:59")
        assert dt == datetime.datetime(1999, 12, 31, 23, 59)

    def test_parse_standard_2000s_date(self):
        # 01-01-10 -> Jan 1, 2010
        dt = _parse_qwk_date("01-01-10", "12:00")
        assert dt == datetime.datetime(2010, 1, 1, 12, 0)

    def test_sliding_window_boundary_1900s(self):
        # 80 is the cut-off for 1900s (inclusive)
        dt = _parse_qwk_date("01-01-80", "00:00")
        assert dt.year == 1980

    def test_sliding_window_boundary_2000s(self):
        # 79 is the cut-off for 2000s (inclusive)
        dt = _parse_qwk_date("01-01-79", "00:00")
        assert dt.year == 2079

    def test_parse_four_digit_year(self):
        # If year provided is 4 digits, sliding window logic (year < 100) should be skipped
        dt = _parse_qwk_date("01-01-2023", "10:30")
        assert dt.year == 2023

        dt = _parse_qwk_date("01-01-1990", "10:30")
        assert dt.year == 1990

    def test_parse_slash_separator(self):
        dt = _parse_qwk_date("02/28/95", "14:00")
        assert dt == datetime.datetime(1995, 2, 28, 14, 0)

    def test_invalid_date_format_fallback(self):
        # Malformed date string
        dt = _parse_qwk_date("not-a-date", "00:00")
        assert dt == datetime.datetime(1970, 1, 1, 0, 0)

    def test_invalid_time_format_fallback(self):
        # Malformed time string
        dt = _parse_qwk_date("01-01-90", "not-a-time")
        assert dt == datetime.datetime(1970, 1, 1, 0, 0)

    def test_invalid_values_fallback(self):
        # Month 13 is invalid
        dt = _parse_qwk_date("13-01-90", "12:00")
        assert dt == datetime.datetime(1970, 1, 1, 0, 0)

        # Hour 25 is invalid
        dt = _parse_qwk_date("01-01-90", "25:00")
        assert dt == datetime.datetime(1970, 1, 1, 0, 0)

    def test_missing_time_components_fallback(self):
        # Time string missing minute
        dt = _parse_qwk_date("01-01-90", "12")
        assert dt == datetime.datetime(1970, 1, 1, 0, 0)

    def test_parse_with_seconds(self):
        # Time string with seconds (HH:MM:SS)
        dt = _parse_qwk_date("01-01-90", "12:34:56")
        assert dt == datetime.datetime(1990, 1, 1, 12, 34, 56)
