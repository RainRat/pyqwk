import sqlite3
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
        verbose=True,
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

def test_sqlite_export_reimport_symmetry(tmp_path, baseline_path, logger):
    """Test that messages exported to SQLite can be re-imported and processed."""
    # 1. Export baseline to SQLite
    db_path = tmp_path / "archive.db"
    settings_export = _make_settings(
        format="sqlite",
        output_mode="file",
        output_path=str(db_path)
    )
    process_file(str(baseline_path), settings_export, logger)

    assert db_path.exists()

    # 2. Re-import from SQLite
    messages, board_dict = load_data(str(db_path), logger)

    assert isinstance(messages, list)
    assert len(messages) > 0
    assert isinstance(messages[0], ParsedMessage)

    # Check that header data was preserved
    # The first message in baseline is msgnum 28, conference 3
    msg = messages[0]
    assert msg.msgnum == 28
    assert msg.header.msgnum == 28
    assert msg.header.msgfrom.strip() == "GammaO #571 @0*1"
    assert msg.confnum == 3
    # Note: baseline messages.dat doesn't have an accompanying CONTROL.DAT,
    # so conference name will be based on the number if not provided.
    # But load_data in test_json_import.py says 384 bytes, let's see.

    # Verify board_dict reconstruction
    assert 3 in board_dict

    # 3. Process re-imported data (e.g., convert to HTML)
    html_path = tmp_path / "archive.html"
    settings_html = _make_settings(
        format="html",
        output_mode="file",
        output_path=str(html_path)
    )

    # We can use process_file on the db path directly now
    process_file(str(db_path), settings_html, logger)

    assert html_path.exists()
    html_content = html_path.read_text(encoding="utf-8")
    assert "GammaO #571 @0*1" in html_content
    assert "New User" in html_content # Subject

def test_sqlite_import_handles_missing_table(tmp_path, logger):
    """Test SQLite import fails gracefully if the messages table is missing."""
    db_path = tmp_path / "empty.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE wrong_table (id INTEGER)")
    conn.close()

    with pytest.raises(ValueError, match="missing the 'messages' table"):
        load_data(str(db_path), logger)
