import logging
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

def test_show_info_not_messages_dat(capsys, mock_logger, default_settings):
    # Mock load_data to return data with wrong header
    with patch('pyqwk.core.load_data') as mock_load:
        # Return enough bytes but wrong header
        bad_data = bytearray(b'X' * 128)
        mock_load.return_value = (bad_data, {})

        show_info(['fake.zip'], default_settings, mock_logger)

        captured = capsys.readouterr()
        assert "Not a valid QWK messages.dat file" in captured.out


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
