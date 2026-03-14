import json
import logging
from pathlib import Path
import pytest
from pyqwk.core import (
    load_data,
    process_file,
    ProcessingSettings,
    ParsedMessage
)

@pytest.fixture
def baseline_path() -> Path:
    return Path(__file__).resolve().parents[1] / "testdata" / "messages.dat"

@pytest.fixture
def logger():
    logger = logging.getLogger("pyqwk.tests")
    logger.addHandler(logging.NullHandler())
    return logger

def _make_settings(**overrides):
    defaults = dict(
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
        encoding="latin1",
        quiet=True,
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)

def test_json_export_reimport_symmetry(tmp_path, baseline_path, logger):
    """Test that messages exported to JSON can be re-imported and processed."""
    # 1. Export baseline to JSON
    json_path = tmp_path / "archive.json"
    settings_export = _make_settings(
        format="json",
        output_mode="file",
        output_path=str(json_path)
    )
    process_file(str(baseline_path), settings_export, logger)

    assert json_path.exists()

    # 2. Re-import from JSON
    messages, board_dict = load_data(str(json_path), logger)

    assert isinstance(messages, list)
    assert len(messages) > 0
    assert isinstance(messages[0], ParsedMessage)

    # Check that header data was preserved
    # The first message in baseline is msgnum 28
    assert messages[0].msgnum == 28
    assert messages[0].header.msgnum == 28
    assert messages[0].header.msgfrom.strip() == "GammaO #571 @0*1"

    # 3. Process re-imported data (e.g., convert to HTML)
    html_path = tmp_path / "archive.html"
    settings_html = _make_settings(
        format="html",
        output_mode="file",
        output_path=str(html_path)
    )

    # We can use process_file on the json path directly now
    process_file(str(json_path), settings_html, logger)

    assert html_path.exists()
    html_content = html_path.read_text(encoding="utf-8")
    assert "GammaO #571 @0*1" in html_content
    assert "New User" in html_content # Subject

def test_json_import_with_missing_fields(tmp_path, logger):
    """Test JSON import handles missing or malformed fields gracefully."""
    json_data = [
        {
            "header": {
                "msgfrom": "Test User",
                "confnum": "100" # String instead of int
            },
            "text": "Hello world",
            "conference": "Test Conf"
        }
    ]
    json_path = tmp_path / "partial.json"
    json_path.write_text(json.dumps(json_data), encoding="utf-8")

    messages, board_dict = load_data(str(json_path), logger)

    assert len(messages) == 1
    assert messages[0].header.msgfrom == "Test User"
    assert messages[0].confnum == 100
    assert messages[0].text == "Hello world"
    assert 100 in board_dict
    assert board_dict[100] == "Test Conf"
