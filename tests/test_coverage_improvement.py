import sys
import logging
import pytest
import datetime
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock
from pyqwk.cli import main
from pyqwk.core import (
    _parse_qwk_date,
    ParsedMessage,
    MessageHeader,
    _order_messages_by_thread,
    load_data,
)


@pytest.fixture
def testdata_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "testdata"


@pytest.fixture
def logger():
    return logging.getLogger("pyqwk.tests.improvement")


def test_oneline_individual_files_conflict(monkeypatch, testdata_dir, capsys):
    input_file = testdata_dir / "messages.dat"
    monkeypatch.setattr(
        sys,
        "argv",
        ["qwk", str(input_file), "--oneline", "--individual-files", "-o", "dummy"],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    stderr = capsys.readouterr().err
    assert "You cannot use --oneline and --individual-files at the same time." in stderr


def test_organize_by_bbs_cli_execution(monkeypatch, testdata_dir):
    input_file = testdata_dir / "messages.dat"
    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "--organize-by-bbs"])

    import pyqwk.cli as cli

    with monkeypatch.context() as m:
        m.setattr(cli, "organize_by_bbs", lambda *args: None)
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0


def test_parse_qwk_date_iso8601():
    # Coverage for line 2253
    iso_date = "2023-10-27T12:34:56"
    dt = _parse_qwk_date(iso_date, "")
    assert dt == datetime.datetime(2023, 10, 27, 12, 34, 56)


def test_single_file_mode_error(monkeypatch, testdata_dir, caplog):
    # Coverage for line 544 in cli.py (error handling branch in main)
    input_file = testdata_dir / "messages.dat"
    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file)])

    import pyqwk.cli as cli
    from pyqwk.core import MessagesDatFormatError

    with monkeypatch.context() as m:
        m.setattr(
            cli,
            "process_merged_files",
            MagicMock(side_effect=MessagesDatFormatError("Single file failure")),
        )
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1
            assert "Single file failure" in caplog.text


def test_threading_circular_reference_logging(message_factory, caplog, logger):
    # Coverage for line 3230
    h1 = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="A",
        msgfrom="B",
        msgsubject="S",
        msgpassword="",
        refnum=2,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )
    h2 = MessageHeader(
        status=" ",
        msgnum=2,
        msgdate="01-01-23",
        msgtime="12:01",
        msgto="A",
        msgfrom="B",
        msgsubject="S",
        msgpassword="",
        refnum=1,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=2,
        nettag="",
    )

    m1 = ParsedMessage(text="M1", msgnum=1, refnum=2, confnum=1, header=h1)
    m2 = ParsedMessage(text="M2", msgnum=2, refnum=1, confnum=1, header=h2)

    with caplog.at_level(logging.WARNING):
        _order_messages_by_thread([m1, m2])
        assert "Conversation loop detected" in caplog.text


def test_load_data_sqlite_bbs_name(tmp_path, logger):
    # Coverage for line 845
    db_path = tmp_path / "test_bbs.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            source_file TEXT,
            attachments TEXT
        )
    """)
    conn.execute("""
        INSERT INTO messages (
            conference_number, message_number, date, author, recipient,
            subject, status, text, bbs_name
        ) VALUES (1, 100, '2023-01-01T12:00:00', 'From', 'To', 'Subj', ' ', 'Body', 'My SQLite BBS')
    """)
    conn.commit()
    conn.close()

    _, board_dict = load_data(str(db_path), logger)
    assert board_dict.bbs_info.name == "My SQLite BBS"
