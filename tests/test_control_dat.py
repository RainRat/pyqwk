import sys
from pathlib import Path
import pytest
import logging

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qwk import _parse_control_dat, ControlDatFormatError

def test_parse_control_dat_too_short():
    # CONTROL.DAT must have at least 11 lines (indices 0-10) to read the conference count.
    control_data = [b'line'] * 10
    with pytest.raises(ControlDatFormatError) as exc_info:
        _parse_control_dat(control_data)
    assert "too short" in str(exc_info.value)

def test_parse_control_dat_invalid_conference_count():
    # Line 10 (0-indexed) is the conference count minus 1.
    control_data = [b'line'] * 10 + [b'not_an_int'] + [b'extra']
    with pytest.raises(ControlDatFormatError) as exc_info:
        _parse_control_dat(control_data)
    assert "Invalid conference count" in str(exc_info.value)

def test_parse_control_dat_truncated_entries_partial_recovery(caplog):
    # Valid count (says 2 conferences -> indices 11,12 and 13,14)
    # But data only has one conference (indices 11,12)
    # We want it to parse what it can and warn, rather than failing completely.

    # Let's set up data for 2 conferences (count=1), but provide only 1.
    # conference count = int(line[10]) + 1. So for 2 conferences, line[10] should be '1'.

    control_data = [b'line'] * 10 + [b'1'] + [b'100', b'Conf 1']
    # Missing Conf 2 (indices 13, 14)

    with caplog.at_level(logging.WARNING):
        board_dict = _parse_control_dat(control_data)

    assert 100 in board_dict
    assert board_dict[100] == "Conf 1"
    assert "truncated" in caplog.text

def test_parse_control_dat_invalid_conference_number_skips_entry(caplog):
    # One valid conference, one invalid number
    # count = 1 (2 conferences)
    control_data = [b'line'] * 10 + [b'1'] + [b'100', b'Conf 1', b'NaN', b'Conf 2']

    with caplog.at_level(logging.WARNING):
        board_dict = _parse_control_dat(control_data)

    assert 100 in board_dict
    assert "Invalid conference number" in caplog.text
    # Conf 2 should be skipped because its number was invalid
