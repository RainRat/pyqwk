import pytest
import datetime
from pyqwk.cli import _parse_cli_date, _resolve_output_format

def test_parse_cli_date_valid():
    assert _parse_cli_date("2023-01-01") == datetime.datetime(2023, 1, 1)

def test_parse_cli_date_end_of_day():
    dt = _parse_cli_date("2023-01-01", end_of_day=True)
    assert dt == datetime.datetime(2023, 1, 1, 23, 59, 59, 999999)

def test_parse_cli_date_none():
    assert _parse_cli_date(None) is None
    assert _parse_cli_date("") is None

def test_parse_cli_date_invalid():
    with pytest.raises(ValueError, match="Invalid date format"):
        _parse_cli_date("01-01-2023")
    with pytest.raises(ValueError, match="Invalid date format"):
        _parse_cli_date("2023-13-01")

def test_resolve_output_format_explicit():
    assert _resolve_output_format("json", "out.txt", "file") == "json"
    assert _resolve_output_format("text", None, "stdout") == "text"

def test_resolve_output_format_auto_detect():
    assert _resolve_output_format(None, "out.json", "file") == "json"
    assert _resolve_output_format(None, "out.xml", "file") == "xml"
    assert _resolve_output_format(None, "out.html", "file") == "html"
    assert _resolve_output_format(None, "out.csv", "file") == "csv"
    assert _resolve_output_format(None, "out.mbox", "file") == "mbox"
    assert _resolve_output_format(None, "out.md", "file") == "markdown"
    assert _resolve_output_format(None, "out.markdown", "file") == "markdown"
    assert _resolve_output_format(None, "out.sqlite", "file") == "sqlite"
    assert _resolve_output_format(None, "out.db", "file") == "sqlite"

def test_resolve_output_format_default():
    assert _resolve_output_format(None, "out.foo", "file") == "text"
    assert _resolve_output_format(None, None, "stdout") == "text"
    assert _resolve_output_format(None, "somefile", "stdout") == "text"
