import sys
import logging
from pathlib import Path
import json
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pyqwk.core as qwk
from pyqwk.core import ProcessingSettings, ParsedMessage, parse_messages, process_file

@pytest.fixture
def baseline_path() -> Path:
    return Path(__file__).resolve().parents[1] / "testdata" / "messages.dat"

@pytest.fixture
def logger() -> logging.Logger:
    logger = logging.getLogger("pyqwk.tests")
    logger.addHandler(logging.NullHandler())
    return logger

def _make_settings(**overrides) -> ProcessingSettings:
    defaults = dict(
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
        quiet=True,
        headers_only=False,
        conferences=None,
        authors=None,
        subjects=None,
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)

def test_parse_messages_headers_only(baseline_path: Path, logger: logging.Logger) -> None:
    file_data, _ = qwk.load_data(str(baseline_path), logger, encoding='latin1')

    messages = list(parse_messages(file_data, progress_bar=None, encoding='latin1', headers_only=True))

    assert len(messages) == 1
    message = messages[0]
    assert isinstance(message, ParsedMessage)
    # The text body should be empty
    assert message.text == ""
    # But headers should be intact
    assert message.header.msgsubject.strip() == "New User"
    assert message.header.msgto.strip() == "All"

def test_cli_headers_only_text_output(capsys, baseline_path: Path, logger: logging.Logger) -> None:
    # When headers_only=True, process_file should output the formatted header but NO body.
    # The default text output prepends formatted header to body.
    # If body is empty, we just get formatted header.

    process_file(
        str(baseline_path),
        _make_settings(headers_only=True),
        logger=logger,
    )

    captured = capsys.readouterr()

    # Check that we see header info
    assert "Subject:        New User" in captured.out
    assert "From:           GammaO" in captured.out

    # Check that we do NOT see body text
    assert "Hello this is my first day" not in captured.out

def test_cli_headers_only_json_output(tmp_path: Path, baseline_path: Path, logger: logging.Logger) -> None:
    output_path = tmp_path / "metadata.json"
    process_file(
        str(baseline_path),
        _make_settings(headers_only=True, format="json", output_mode="file", output_path=str(output_path)),
        logger=logger,
    )

    with output_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    message = data[0]
    # Header dict should be populated
    assert message["header"]["msgsubject"].strip() == "New User"
    # Text field should be empty
    assert message["text"] == ""

def test_cli_headers_only_csv_output(tmp_path: Path, baseline_path: Path, logger: logging.Logger) -> None:
    output_path = tmp_path / "metadata.csv"
    process_file(
        str(baseline_path),
        _make_settings(headers_only=True, format="csv", output_mode="file", output_path=str(output_path)),
        logger=logger,
    )

    with output_path.open("r", encoding="utf-8") as f:
        content = f.read()

    # Should have header row
    assert "msgsubject" in content
    # Should have data row with subject
    assert "New User" in content
    # But text column (usually huge) should be empty
    # In CSV it looks like ,"", or ,,
    # We can check that the body text isn't there
    assert "Hello this is my first day" not in content

def test_headers_only_and_noheader_results_in_empty_output(capsys, baseline_path: Path, logger: logging.Logger) -> None:
    # If we ask for headers only (empty body) AND no header (don't print header),
    # we should get almost nothing (just separator)

    process_file(
        str(baseline_path),
        _make_settings(headers_only=True, no_header=True),
        logger=logger,
    )

    captured = capsys.readouterr()
    # Separator is still printed by default in text mode
    assert ("-" * 80) in captured.out
    # But no header info
    assert "Subject: New User" not in captured.out
    # And no body
    assert "Hello this is my first day" not in captured.out
