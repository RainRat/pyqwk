import pytest
import sys
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

def test_process_merged_files_dry_run_no_files_created(tmp_path, baseline_path, logger):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="auto",
        output_mode="file",
        output_path=str(output_dir),
        encoding="latin1",
        dry_run=True
    )

    process_merged_files([str(baseline_path)], settings, logger)

    # Check that no files were created in the output directory
    assert len(list(output_dir.iterdir())) == 0

def test_process_merged_files_dry_run_summary_printed(capsys, baseline_path, logger):
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
        dry_run=True,
        quiet=True
    )

    process_merged_files([str(baseline_path)], settings, logger)

    captured = capsys.readouterr()
    assert "--- Dry Run Summary ---" in captured.out
    assert "Archives processed: 1" in captured.out
    assert "Matching messages:  1" in captured.out
    assert "No changes were made to the disk." in captured.out
    # Should not print the actual message
    assert "Subject:" not in captured.out

def test_cli_dry_run_flag_works(monkeypatch, baseline_path, capsys):
    monkeypatch.setattr(sys, "argv", ["qwk", str(baseline_path), "--dry-run"])

    # Run main and catch potential SystemExit
    try:
        main()
    except SystemExit as e:
        assert e.code == 0

    captured = capsys.readouterr()
    assert "--- Dry Run Summary ---" in captured.out
    assert "No changes were made to the disk." in captured.out
