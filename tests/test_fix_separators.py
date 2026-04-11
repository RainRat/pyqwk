import logging
import sqlite3
import pytest
from pathlib import Path
from pyqwk.core import process_merged_files, ProcessingSettings

@pytest.fixture
def logger():
    logger = logging.getLogger("pyqwk.tests")
    logger.addHandler(logging.NullHandler())
    return logger

def test_sqlite_no_separator_by_default(tmp_path, logger):
    input_path = Path(__file__).resolve().parents[1] / "testdata" / "messages.dat"
    db_path = tmp_path / "test.sqlite"

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
        format="sqlite",
        separator="auto",
        output_mode="file",
        output_path=str(db_path),
        encoding="latin1"
    )

    process_merged_files([str(input_path)], settings, logger)

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT text FROM messages LIMIT 1")
    text = c.fetchone()[0]
    conn.close()

    assert not text.startswith("-" * 80)
    # It should NOT start with the text header in structured formats even if no_header is False
    assert not text.startswith("Date:")
    assert text == "Hello this is my first day in the wonderful world of BBSing and I need some\r\nhelp.\r\n"

def test_mbox_no_separator_by_default(tmp_path, logger):
    input_path = Path(__file__).resolve().parents[1] / "testdata" / "messages.dat"
    mbox_path = tmp_path / "test.mbox"

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
        format="mbox",
        separator="auto",
        output_mode="file",
        output_path=str(mbox_path),
        encoding="latin1"
    )

    process_merged_files([str(input_path)], settings, logger)

    content = mbox_path.read_text(encoding='utf-8')
    # In mbox, the separator should NOT be there.
    # The body is separated from mbox headers by a blank line.
    # The formatted header is at the start of the body.
    assert ("-" * 80) not in content
