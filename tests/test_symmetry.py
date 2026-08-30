import os
import shutil
import tempfile
import logging
import pytest
from pyqwk.core import (
    load_data,
    write_messages,
    ProcessingSettings,
    MessageHeader,
    ParsedMessage,
    BBSInfo,
    parse_messages,
    _serialize_control_dat,
    _write_qwk,
    process_message,
)


def test_qwk_export_symmetry():
    # Setup
    tmpdir = tempfile.mkdtemp()
    try:
        qwk_path = os.path.join(tmpdir, "test.qwk")
        logger = logging.getLogger("test")

        # 1. Create dummy messages
        header1 = MessageHeader(
            status=" ",
            msgnum=1,
            msgdate="01-01-23",
            msgtime="12:00",
            msgto="Alice",
            msgfrom="Bob",
            msgsubject="Hello Symmetry",
            msgpassword="",
            refnum=0,
            numblocks=0,
            msgflag=" ",
            confnum=1,
            lognum=0,
            nettag="",
        )
        msg1 = ParsedMessage(
            text="This is a test message for symmetry.\r\nLine 2.",
            msgnum=1,
            refnum=0,
            confnum=1,
            header=header1,
        )

        messages = [msg1]
        bbs_info = BBSInfo(name="Test BBS", bbs_id="TESTBBS")
        board_dict = {1: "General"}

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
            format="qwk",
            separator="none",
            output_mode="file",
            output_path=qwk_path,
            encoding="cp437",
        )

        # 2. Export to QWK
        write_messages(messages, qwk_path, settings, bbs_info, board_dict)
        assert os.path.exists(qwk_path)

        # 3. Re-import from QWK
        imported_data, imported_board = load_data(qwk_path, logger)
        assert imported_board[1] == "General"
        assert imported_board.bbs_info.name == "Test BBS"

        imported_messages = list(parse_messages(imported_data, None))
        assert len(imported_messages) == 1
        imp_msg = imported_messages[0]

        assert imp_msg.header.msgfrom.strip() == "Bob"
        assert imp_msg.header.msgto.strip() == "Alice"
        assert imp_msg.header.msgsubject.strip() == "Hello Symmetry"

        cleaned_text = process_message(imp_msg.text, False, False, False, False)
        assert "This is a test message for symmetry." in cleaned_text
        assert "Line 2." in cleaned_text

    finally:
        shutil.rmtree(tmpdir)


def test_rep_export_symmetry():
    # Setup
    tmpdir = tempfile.mkdtemp()
    try:
        rep_path = os.path.join(tmpdir, "test.rep")
        logger = logging.getLogger("test")

        header1 = MessageHeader(
            status=" ",
            msgnum=None,
            msgdate="01-01-23",
            msgtime="12:00",
            msgto="Sysop",
            msgfrom="User",
            msgsubject="Reply Test",
            msgpassword="",
            refnum=1,
            numblocks=0,
            msgflag=" ",
            confnum=1,
            lognum=0,
            nettag="",
        )
        msg1 = ParsedMessage(
            text="Reply content.", msgnum=None, refnum=1, confnum=1, header=header1
        )

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
            format="rep",
            separator="none",
            output_mode="file",
            output_path=rep_path,
            encoding="cp437",
        )

        write_messages(
            [msg1], rep_path, settings, BBSInfo(bbs_id="TESTBBS"), {1: "General"}
        )

        imported_data, _ = load_data(rep_path, logger)
        imported_messages = list(parse_messages(imported_data, None))

        assert len(imported_messages) == 1
        assert imported_messages[0].header.msgsubject.strip() == "Reply Test"
        assert imported_messages[0].header.refnum == 1
    finally:
        shutil.rmtree(tmpdir)


def test_control_dat_no_bbs_info():
    # Coverage for board_dict is None/empty
    lines = _serialize_control_dat(None, None)
    assert lines[10] == b"-1"


def test_write_qwk_no_output_path():
    # Coverage for output_path is None
    with pytest.raises(ValueError, match="Output path is required"):
        _write_qwk([], None)


def test_json_thread_metadata_symmetry():
    tmpdir = tempfile.mkdtemp()
    try:
        json_path = os.path.join(tmpdir, "test.json")
        jsonl_path = os.path.join(tmpdir, "test.jsonl")
        logger = logging.getLogger("test")

        header1 = MessageHeader(
            status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
            msgto="Alice", msgfrom="Bob", msgsubject="Thread Parent",
            msgpassword="", refnum=0, numblocks=0, msgflag=" ", confnum=1, lognum=0, nettag=""
        )
        msg1 = ParsedMessage(
            text="Root thread message.", msgnum=1, refnum=0, confnum=1, header=header1,
            reply_count=3, thread_size=4
        )

        settings_json = ProcessingSettings(
            verbose=False, private=True, no_header=False, truncate_signatures=False,
            cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
            redact_pii=False, format="json", separator="none", output_mode="file",
            output_path=json_path, encoding="utf-8"
        )
        write_messages([msg1], json_path, settings_json)

        imported_json_msgs, _ = load_data(json_path, logger)
        assert len(imported_json_msgs) == 1
        assert imported_json_msgs[0].reply_count == 3
        assert imported_json_msgs[0].thread_size == 4

        settings_jsonl = ProcessingSettings(
            verbose=False, private=True, no_header=False, truncate_signatures=False,
            cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
            redact_pii=False, format="jsonl", separator="none", output_mode="file",
            output_path=jsonl_path, encoding="utf-8"
        )
        write_messages([msg1], jsonl_path, settings_jsonl)

        imported_jsonl_msgs, _ = load_data(jsonl_path, logger)
        assert len(imported_jsonl_msgs) == 1
        assert imported_jsonl_msgs[0].reply_count == 3
        assert imported_jsonl_msgs[0].thread_size == 4
    finally:
        shutil.rmtree(tmpdir)


def test_csv_thread_metadata_symmetry():
    tmpdir = tempfile.mkdtemp()
    try:
        csv_path = os.path.join(tmpdir, "test.csv")
        logger = logging.getLogger("test")

        header1 = MessageHeader(
            status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
            msgto="Alice", msgfrom="Bob", msgsubject="CSV Thread",
            msgpassword="", refnum=0, numblocks=0, msgflag=" ", confnum=1, lognum=0, nettag=""
        )
        msg1 = ParsedMessage(
            text="CSV message text.", msgnum=1, refnum=0, confnum=1, header=header1,
            reply_count=5, thread_size=6
        )

        settings = ProcessingSettings(
            verbose=False, private=True, no_header=False, truncate_signatures=False,
            cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
            redact_pii=False, format="csv", separator="none", output_mode="file",
            output_path=csv_path, encoding="utf-8"
        )
        write_messages([msg1], csv_path, settings)

        imported_csv_msgs, _ = load_data(csv_path, logger)
        assert len(imported_csv_msgs) == 1
        assert imported_csv_msgs[0].reply_count == 5
        assert imported_csv_msgs[0].thread_size == 6
    finally:
        shutil.rmtree(tmpdir)


def test_sqlite_thread_metadata_symmetry():
    import sqlite3
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmpdir, "test.sqlite")
        legacy_db_path = os.path.join(tmpdir, "legacy.sqlite")
        logger = logging.getLogger("test")

        header1 = MessageHeader(
            status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
            msgto="Alice", msgfrom="Bob", msgsubject="SQLite Thread",
            msgpassword="", refnum=0, numblocks=0, msgflag=" ", confnum=1, lognum=0, nettag=""
        )
        msg1 = ParsedMessage(
            text="SQLite message text.", msgnum=1, refnum=0, confnum=1, header=header1,
            reply_count=2, thread_size=3
        )

        settings = ProcessingSettings(
            verbose=False, private=True, no_header=False, truncate_signatures=False,
            cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
            redact_pii=False, format="sqlite", separator="none", output_mode="file",
            output_path=db_path, encoding="utf-8"
        )
        write_messages([msg1], db_path, settings)

        imported_db_msgs, _ = load_data(db_path, logger)
        assert len(imported_db_msgs) == 1
        assert imported_db_msgs[0].reply_count == 2
        assert imported_db_msgs[0].thread_size == 3

        # Test legacy database without reply_count / thread_size columns
        conn = sqlite3.connect(legacy_db_path)
        conn.execute("""
            CREATE TABLE messages (
                conference_number INTEGER, message_number INTEGER, date TEXT,
                author TEXT, recipient TEXT, subject TEXT, status TEXT, text TEXT,
                reference_number INTEGER, thread_id TEXT, depth INTEGER,
                parent_message_number INTEGER, conference_name TEXT, bbs_name TEXT,
                bbs_id TEXT, source_file TEXT, attachments TEXT
            )
        """)
        conn.execute("""
            INSERT INTO messages (
                conference_number, message_number, date, author, recipient,
                subject, status, text, reference_number, depth, conference_name
            ) VALUES (1, 1, '2023-01-01T12:00:00', 'Bob', 'Alice', 'Legacy', ' ', 'Text', 0, 0, 'General')
        """)
        conn.commit()
        conn.close()

        legacy_msgs, _ = load_data(legacy_db_path, logger)
        assert len(legacy_msgs) == 1
        assert legacy_msgs[0].reply_count == 0
        assert legacy_msgs[0].thread_size == 1
    finally:
        shutil.rmtree(tmpdir)
