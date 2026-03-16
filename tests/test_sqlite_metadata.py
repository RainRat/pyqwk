import sqlite3
import logging
from pathlib import Path
import pytest
from pyqwk.core import (
    load_data,
    ProcessingSettings,
    BBSInfo,
    ConferenceMap
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

def test_sqlite_metadata_preservation(tmp_path, baseline_path, logger):
    """Test that BBS info and conference names are preserved in SQLite round-trip."""
    # 1. Create a mock BBSInfo and ConferenceMap
    bbs = BBSInfo(
        name="Test BBS",
        sysop="John Doe",
        bbs_id="TESTBBS",
        packet_at="2023-10-27"
    )
    boards = ConferenceMap({
        1: "General Chat",
        2: "Tech Support",
        3: "Antique Computers"
    })
    boards.bbs_info = bbs

    # 2. Export to SQLite
    db_path = tmp_path / "metadata_test.db"
    settings_export = _make_settings(
        format="sqlite",
        output_mode="file",
        output_path=str(db_path)
    )

    # We need to manually call load_data then write_messages to use our custom metadata
    # Or mock the environment. Easier: use the existing baseline but ensure its metadata is set.
    # Actually, process_file will call load_data which finds messages.dat and (optionally) control.dat.
    # To test OUR metadata, let's write a small helper that uses write_messages directly.

    from pyqwk.core import parse_messages, write_messages

    with open(baseline_path, 'rb') as f:
        file_data = bytearray(f.read())

    messages = list(parse_messages(file_data, None))
    # Tag messages with conference names for export consistency
    for m in messages:
        m.confname = boards.get(m.confnum)

    write_messages(messages, str(db_path), settings_export, bbs, boards)

    assert db_path.exists()

    # 3. Verify tables exist in the database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bbs_info'")
    assert cursor.fetchone() is not None

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conferences'")
    assert cursor.fetchone() is not None

    cursor.execute("SELECT name, sysop, bbs_id FROM bbs_info")
    row = cursor.fetchone()
    assert row[0] == "Test BBS"
    assert row[1] == "John Doe"
    assert row[2] == "TESTBBS"

    cursor.execute("SELECT name FROM conferences WHERE number=3")
    row = cursor.fetchone()
    assert row[0] == "Antique Computers"

    conn.close()

    # 4. Re-import and verify reconstruction
    imported_messages, imported_boards = load_data(str(db_path), logger)

    assert imported_boards.bbs_info.name == "Test BBS"
    assert imported_boards.bbs_info.sysop == "John Doe"
    assert imported_boards[1] == "General Chat"
    assert imported_boards[3] == "Antique Computers"

    # Ensure messages also have the metadata
    assert imported_messages[0].bbs_name == "Test BBS"
    assert imported_messages[0].confname == "Antique Computers" # baseline msg 28 is conf 3

def test_sqlite_backward_compatibility(tmp_path, baseline_path, logger):
    """Test that SQLite files without metadata tables are still readable."""
    db_path = tmp_path / "legacy.db"

    # Create a minimal SQLite file with only messages table
    conn = sqlite3.connect(str(db_path))
    conn.execute('''
        CREATE TABLE messages (
            conference_number INTEGER,
            message_number INTEGER,
            date TEXT,
            author TEXT,
            recipient TEXT,
            subject TEXT,
            status TEXT,
            text TEXT,
            reference_number INTEGER,
            thread_id TEXT,
            depth INTEGER,
            parent_message_number INTEGER,
            conference_name TEXT,
            bbs_name TEXT,
            bbs_id TEXT,
            source_file TEXT,
            attachments TEXT
        )
    ''')
    conn.execute('''
        INSERT INTO messages (conference_number, message_number, author, subject, text)
        VALUES (10, 100, 'Old User', 'Hello', 'Old message body')
    ''')
    conn.commit()
    conn.close()

    # load_data should still work and reconstruct metadata from messages
    messages, board_dict = load_data(str(db_path), logger)

    assert len(messages) == 1
    assert messages[0].header.msgfrom == 'Old User'
    assert board_dict[10] == 'Conference 10' # Default reconstruction
