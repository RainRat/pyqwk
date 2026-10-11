import sys
import pytest
from unittest.mock import patch, MagicMock
from io import StringIO
from pyqwk.cli import main, ListFormatsAction, FORMATS_INFO


def test_cli_list_formats_no_color():
    """Verify that --list-formats outputs correct plain text and exits with status 0 (no color)."""
    mock_stdout = StringIO()

    with patch.object(sys, "argv", ["qwk", "--list-formats"]):
        with patch("sys.stdout", mock_stdout):
            with pytest.raises(SystemExit) as excinfo:
                main()

    assert excinfo.value.code == 0
    output = mock_stdout.getvalue()

    assert "Supported Output Formats:" in output
    for fmt_name, details in FORMATS_INFO.items():
        assert fmt_name in output
        assert details["ext"] in output
        assert details["type"] in output
        assert details["desc"] in output

    # Ensure no ANSI escape codes are present in non-tty output
    assert "\033[" not in output


def test_cli_list_formats_with_color():
    """Verify that --list-formats includes ANSI color codes when stdout is a terminal (TTY)."""
    mock_stdout = StringIO()
    mock_stdout.isatty = MagicMock(return_value=True)

    with patch.object(sys, "argv", ["qwk", "--list-formats"]):
        with patch("sys.stdout", mock_stdout):
            with pytest.raises(SystemExit) as excinfo:
                main()

    assert excinfo.value.code == 0
    output = mock_stdout.getvalue()

    # ANSI code for Bold Cyan (header), Bold Green (formats), and Dim Cyan (extensions)
    assert "\033[1;36m" in output  # Bold Cyan
    assert "\033[1;32m" in output  # Bold Green
    assert "\033[2;36m" in output  # Dim Cyan
    assert "\033[0m" in output     # Reset

    # Verify key content is present
    assert "Supported Output Formats:" in output
    assert "text" in output
    assert "json" in output
    assert "html" in output
    assert "sqlite" in output
