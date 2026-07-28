import pytest
import sys
import os
from pathlib import Path
from pyqwk.core import process_merged_files, ProcessingSettings
from pyqwk.cli import main
import logging

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def baseline_path() -> Path:
    return Path(__file__).resolve().parents[1] / "testdata" / "messages.dat"


@pytest.fixture
def logger() -> logging.Logger:
    logger = logging.getLogger("pyqwk.tests")
    logger.addHandler(logging.NullHandler())
    return logger


def test_process_merged_files_count_only_prints_integer(capsys, baseline_path, logger):
    settings = ProcessingSettings(
        verbose=False,
        private=False,
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
        encoding="latin1",
        count_only=True,
    )

    process_merged_files([str(baseline_path)], settings, logger)

    captured = capsys.readouterr()
    # Since there's 1 message in messages.dat:
    assert captured.out.strip() == "1"
    # Ensure no summaries or headers are printed
    assert "--- Dry Run Summary ---" not in captured.out
    assert "Successfully processed" not in captured.out
    assert "Subject:" not in captured.out


def test_process_merged_files_count_only_no_files_written(tmp_path, baseline_path, logger):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    output_path = output_dir / "out.txt"

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="auto",
        output_mode="file",
        output_path=str(output_path),
        encoding="latin1",
        count_only=True,
    )

    process_merged_files([str(baseline_path)], settings, logger)

    # Ensure no output file is actually created, even though output_path was provided
    assert not output_path.exists()


def test_cli_count_only_flag_works(monkeypatch, baseline_path, capsys):
    monkeypatch.setattr(sys, "argv", ["qwk", str(baseline_path), "--count-only"])

    try:
        main()
    except SystemExit as e:
        assert e.code == 0

    captured = capsys.readouterr()
    assert captured.out.strip() == "1"
    # No logs or informational messages on stdout
    assert "Successfully processed" not in captured.out


def test_cli_count_only_with_filters(monkeypatch, baseline_path, capsys):
    # Search for a term that doesn't exist (should yield 0)
    monkeypatch.setattr(
        sys, "argv", ["qwk", str(baseline_path), "--count-only", "--search", "NONEXISTENT_TERM_XYZ"]
    )

    try:
        main()
    except SystemExit as e:
        assert e.code == 0

    captured = capsys.readouterr()
    assert captured.out.strip() == "0"


def test_cli_count_only_multiple_inputs_suppresses_merge_info(monkeypatch, baseline_path, capsys):
    # Provide multiple files (repeating baseline_path) and count them
    monkeypatch.setattr(
        sys, "argv", ["qwk", str(baseline_path), str(baseline_path), "--count-only"]
    )

    try:
        main()
    except SystemExit as e:
        assert e.code == 0

    captured = capsys.readouterr()
    assert captured.out.strip() == "2"
    # Ensure no "Merging results to the screen." is in captured stdout/stderr
    assert "Merging results to the screen" not in captured.out
    assert "Merging results to the screen" not in captured.err
