import sys
import logging
from io import StringIO
from unittest.mock import patch, MagicMock
import pytest

from pyqwk.cli import main
from pyqwk.core import ProcessingSettings, process_merged_files


def test_cli_count_only_basic(capsys):
    """Test running CLI with --count-only on test1_qwk.zip."""
    test_qwk = "testdata/test1_qwk.zip"

    # Run the CLI main with --count-only
    with patch("sys.argv", ["qwk", test_qwk, "--count-only"]):
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit with code 0
        assert exc_info.value.code == 0

    # Capture stdout and parse the printed count
    captured = capsys.readouterr()
    assert captured.out.strip().isdigit()
    count = int(captured.out.strip())
    # Standard count for test1_qwk.zip is usually 6 or similar
    assert count > 0


def test_cli_count_only_with_filters(capsys):
    """Test running CLI with --count-only and a filter to verify that filters are respected."""
    test_qwk = "testdata/test1_qwk.zip"

    # Get the unfiltered count
    with patch("sys.argv", ["qwk", test_qwk, "--count-only"]):
        with pytest.raises(SystemExit):
            main()
    unfiltered_count = int(capsys.readouterr().out.strip())

    # Get count with a search filter that matches nothing
    with patch("sys.argv", ["qwk", test_qwk, "--count-only", "--search", "NONEXISTENT_STUFF_12345"]):
        with pytest.raises(SystemExit):
            main()
    filtered_count = int(capsys.readouterr().out.strip())

    assert filtered_count == 0
    assert filtered_count < unfiltered_count


def test_process_merged_files_count_only_quiet_progress(capsys):
    """Test that setting count_only correctly mutes the progress bar and prints only the count."""
    test_qwk = "testdata/test1_qwk.zip"
    logger = logging.getLogger("test_logger")

    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        count_only=True,
        quiet=False,  # Should be forced to True internally
    )

    process_merged_files([test_qwk], settings, logger)

    captured = capsys.readouterr()
    # It should have printed only the count
    assert captured.out.strip().isdigit()
    # No progress bar or other outputs in stdout/stderr
    assert captured.err == ""


def test_cli_count_only_multiple_archives(capsys):
    """Test CLI count-only with multiple files specified."""
    test_qwk1 = "testdata/test1_qwk.zip"
    test_qwk2 = "testdata/test2_qwk.zip"

    # Run with both files
    with patch("sys.argv", ["qwk", test_qwk1, test_qwk2, "--count-only"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    count = int(capsys.readouterr().out.strip())
    assert count > 0


def test_cli_count_only_exception_handling(caplog):
    """Test that CLI exits with code 1 if an exception occurs during count-only processing."""
    test_qwk = "testdata/test1_qwk.zip"

    with patch("sys.argv", ["qwk", test_qwk, "--count-only"]):
        # Mock process_merged_files to raise an IOError
        with patch("pyqwk.cli.process_merged_files", side_effect=IOError("Simulated file error")):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    # Should log the error
    assert any("Simulated file error" in record.message for record in caplog.records)
