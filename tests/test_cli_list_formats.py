import sys
import pytest
from unittest.mock import patch, MagicMock
from io import StringIO
from pyqwk.cli import main, ListFormatsAction, FORMATS_INFO


def test_cli_list_formats_no_color():
    """Verify that --list-formats outputs correct text and exits with status 0 (no color)."""
    mock_stdout = StringIO()

    with patch.object(sys, "argv", ["qwk", "--list-formats"]):
        with patch("sys.stdout", mock_stdout):
            with pytest.raises(SystemExit) as excinfo:
                main()

    assert excinfo.value.code == 0
    output = mock_stdout.getvalue()

    assert "Supported Export Formats:" in output
    for fmt, info in FORMATS_INFO.items():
        assert fmt in output
        assert info["ext"] in output
        assert info["type"] in output
        assert info["desc"] in output

    # Ensure no ANSI escape codes are present in non-tty output
    assert "\033[" not in output


def test_cli_list_formats_with_color():
    """Verify that --list-formats includes ANSI color codes when stdout is a terminal."""
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

    # Verify content remains present
    assert "Supported Export Formats:" in output
    assert "html" in output
    assert "json" in output
    assert "sqlite" in output


def test_cli_help_includes_list_formats():
    """Verify that qwk --help includes --list-formats in formatting group."""
    mock_stdout = StringIO()

    with patch.object(sys, "argv", ["qwk", "--help"]):
        with patch("sys.stdout", mock_stdout):
            with pytest.raises(SystemExit) as excinfo:
                main()

    assert excinfo.value.code == 0
    output = mock_stdout.getvalue()
    assert "--list-formats" in output


def test_cli_missing_args_help_includes_list_formats():
    """Verify that qwk without arguments mentions --list-formats in stderr usage error."""
    mock_stderr = StringIO()

    with patch.object(sys, "argv", ["qwk"]):
        with patch("sys.stderr", mock_stderr):
            with pytest.raises(SystemExit) as excinfo:
                main()

    assert excinfo.value.code == 2
    output = mock_stderr.getvalue()
    assert "--list-formats" in output
