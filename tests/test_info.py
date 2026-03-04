import logging
from dataclasses import replace
from unittest.mock import MagicMock, patch
import pytest
from pyqwk.core import show_info, ProcessingSettings

@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)

@pytest.fixture
def default_settings():
    return ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        quiet=True,
        format='text',
        separator='auto',
        output_mode='stdout',
        output_path=None,
        encoding='cp437',
        conferences=None
    )

def test_show_info_with_valid_file(capsys, mock_logger, default_settings):
    # We use the existing testdata file
    input_path = 'testdata/test1_qwk.zip'

    show_info([input_path], default_settings, mock_logger)

    captured = capsys.readouterr()
    output = captured.out

    assert f"File: {input_path}" in output
    assert "Total Messages: 1" in output
    assert "4: Pnw.Tech (1 messages)" in output

def test_show_info_with_multiple_files(capsys, mock_logger, default_settings):
    input_paths = ['testdata/test1_qwk.zip', 'testdata/test2_qwk.zip']

    show_info(input_paths, default_settings, mock_logger)

    captured = capsys.readouterr()
    output = captured.out

    assert "File: testdata/test1_qwk.zip" in output
    assert "4: Pnw.Tech (1 messages)" in output
    assert "File: testdata/test2_qwk.zip" in output
    assert "3: Net140.Tech (2 messages)" in output

def test_show_info_invalid_file(capsys, mock_logger, default_settings):
    # Mock load_data to return invalid data
    with patch('pyqwk.core.load_data') as mock_load:
        # Return tiny file
        mock_load.return_value = (bytearray(b'too_short'), {})

        show_info(['fake.zip'], default_settings, mock_logger)

        captured = capsys.readouterr()
        assert "Invalid or empty file" in captured.out



def test_show_info_colors_enabled(capsys, mock_logger, default_settings):
    """Test that ANSI colors are applied when stdout is a TTY."""
    input_path = 'testdata/test1_qwk.zip'

    # Mock sys.stdout.isatty to return True
    with patch('sys.stdout.isatty', return_value=True):
        show_info([input_path], default_settings, mock_logger)

    captured = capsys.readouterr()
    output = captured.out

    # Check for ANSI codes
    # BOLD = "1", CYAN = "36"
    assert "\033[36m" in output  # File path color
    assert "\033[1m" in output   # Bold headers
    assert "\033[0m" in output   # Reset
    assert f"File: \033[36m{input_path}\033[0m" in output
    assert "\033[1mTotal Messages:\033[0m" in output


def test_show_info_bbs_metadata(capsys, mock_logger, default_settings):
    """Test that BBS metadata is correctly displayed in info output."""
    input_path = 'testdata/test1_qwk.zip'
    show_info([input_path], default_settings, mock_logger)

    captured = capsys.readouterr()
    output = captured.out

    assert "BBS Name: Benden Weyr, Pern, Sagittarius Sector" in output
    assert "SysOp:    Ken Read" in output
    assert "BBS ID:   Benden" in output
    assert "Packet At: 09-04-1994,19:25:58" in output


def test_show_info_json_format(capsys, mock_logger, default_settings):
    """Test that info output can be formatted as JSON."""
    input_path = 'testdata/test1_qwk.zip'
    json_settings = replace(default_settings, format='json')

    show_info([input_path], json_settings, mock_logger)

    captured = capsys.readouterr()
    output = captured.out

    import json
    data = json.loads(output)

    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["file"] == input_path
    assert data[0]["total_messages"] == 1
    assert data[0]["bbs_info"]["name"] == "Benden Weyr, Pern, Sagittarius Sector"
    assert data[0]["bbs_info"]["sysop"] == "Ken Read"
    assert len(data[0]["conferences"]) == 1
    assert data[0]["conferences"][0]["number"] == 4

def test_show_info_truncated_messages_dat(capsys, mock_logger, default_settings):
    """Test handling of truncated messages.dat in show_info."""
    import struct
    with patch('pyqwk.core.load_data') as mock_load:
        # First block: Produced header
        # Second block: Valid message header that claims to have 5 blocks, but no body blocks follow
        header = struct.pack(
            '<c7s8s5s25s25s25s12s8s6scHHc',
            b' ', b"1".ljust(7, b' '), b"01-01-90", b"12:00",
            b"To".ljust(25, b' '), b"From".ljust(25, b' '), b"Subj".ljust(25, b' '),
            b"".ljust(12, b' '), b"0".ljust(8, b' '),
            b"5".ljust(6, b' '), # Claims 5 blocks
            b' ', 1, 1, b' '
        )
        bad_data = bytearray(b'Produced ' + b'X' * (128 - 9) + header)
        mock_load.return_value = (bad_data, {})

        show_info(['truncated.zip'], default_settings, mock_logger)

        captured = capsys.readouterr()
        # Should not crash and should print the file path
        assert "File: truncated.zip" in captured.out
