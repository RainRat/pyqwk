import sys
from pathlib import Path
import pytest
import logging

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyqwk.core import _parse_control_dat, ControlDatFormatError

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

def test_parse_control_dat_populates_bbs_info():
    control_data = [
        b'My BBS',          # 0: name
        b'City, State',     # 1: location
        b'555-1212',        # 2: phone
        b'Sysop Name',      # 3: sysop
        b'1234,MYBBS',      # 4: serial, bbs_id
        b'01-01-90',        # 5: packet_at
        b'User Name',       # 6: user_name
        b'', b'', b'',      # 7, 8, 9
        b'0',               # 10: num_confs - 1
        b'101', b'Conf 1'   # 11, 12
    ]
    board_dict = _parse_control_dat(control_data)

    assert board_dict.bbs_info is not None
    assert board_dict.bbs_info.name == 'My BBS'
    assert board_dict.bbs_info.location == 'City, State'
    assert board_dict.bbs_info.phone == '555-1212'
    assert board_dict.bbs_info.sysop == 'Sysop Name'
    assert board_dict.bbs_info.serial_number == '1234'
    assert board_dict.bbs_info.bbs_id == 'MYBBS'
    assert board_dict.bbs_info.packet_at == '01-01-90'
    assert board_dict.bbs_info.user_name == 'User Name'
    assert board_dict.bbs_info.num_conferences == 1

def test_parse_control_dat_bbs_id_missing():
    # Line 4 with no comma
    control_data = [b'line'] * 4 + [b'1234'] + [b'line'] * 5 + [b'0'] + [b'101', b'Conf 1']
    board_dict = _parse_control_dat(control_data)

    assert board_dict.bbs_info.serial_number == '1234'
    assert board_dict.bbs_info.bbs_id == ''

def test_parse_control_dat_unicode_decode_error_fallback():
    # Provide bytes that are invalid in UTF-8
    invalid_utf8 = b'Board \xff Name'
    # Use utf-8 encoding to force the error in dec()
    control_data = [b'line'] * 10 + [b'0'] + [b'101', invalid_utf8]

    # We pass encoding='utf-8' so that .decode(encoding) fails for b'\xff'
    board_dict = _parse_control_dat(control_data, encoding='utf-8')

    assert 101 in board_dict
    # Fallback is latin1. b'\xff'.decode('latin1') is 'ÿ'
    assert board_dict[101] == 'Board ÿ Name'
