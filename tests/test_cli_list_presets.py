import sys
import pytest
from unittest.mock import patch, MagicMock
from io import StringIO
from pyqwk.cli import main, ListPresetsAction


def test_cli_list_presets_no_color():
    """Verify that --list-presets outputs correct text and exits with status 0 (no color)."""
    # Mock sys.stdout to be a StringIO, which doesn't support tty (isatty is False by default)
    mock_stdout = StringIO()

    with patch.object(sys, "argv", ["qwk", "--list-presets"]):
        with patch("sys.stdout", mock_stdout):
            with pytest.raises(SystemExit) as excinfo:
                main()

    assert excinfo.value.code == 0
    output = mock_stdout.getvalue()

    assert "Available Workflow Presets:" in output
    assert "blog" in output
    assert "Save messages as clean, threaded individual Markdown files." in output
    assert "--format markdown --clean --threaded --individual-files" in output
    assert "email" in output
    assert "Save messages as individual EML files." in output
    assert "--format eml --individual-files" in output
    assert "backup" in output
    assert "Create a complete SQLite backup with private and unique messages." in output
    assert "--format sqlite --private --unique" in output
    assert "digest" in output
    assert "Save a single clean, threaded HTML file with a table of contents." in output
    assert "--format html --threaded --clean --toc" in output
    assert "text-archive" in output
    assert "Save clean text without headers." in output
    assert "--format text --clean --noheader" in output

    # Ensure no ANSI escape codes are present in non-tty output
    assert "\033[" not in output


def test_cli_list_presets_with_color():
    """Verify that --list-presets includes ANSI color codes when stdout is a terminal."""
    mock_stdout = StringIO()
    # Mock isatty to return True so colors are enabled
    mock_stdout.isatty = MagicMock(return_value=True)

    with patch.object(sys, "argv", ["qwk", "--list-presets"]):
        with patch("sys.stdout", mock_stdout):
            with pytest.raises(SystemExit) as excinfo:
                main()

    assert excinfo.value.code == 0
    output = mock_stdout.getvalue()

    # ANSI code for Bold Cyan (header), Bold Green (presets), and Dim (equivalents)
    assert "\033[1;36m" in output  # Bold Cyan
    assert "\033[1;32m" in output  # Bold Green
    assert "\033[2m" in output      # Dim
    assert "\033[0m" in output      # Reset

    # Verify content remains present
    assert "Available Workflow Presets:" in output
    assert "blog" in output
    assert "email" in output
    assert "backup" in output
    assert "digest" in output
    assert "text-archive" in output
