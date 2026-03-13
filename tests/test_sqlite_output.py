import sqlite3
import pytest
from pyqwk.core import _write_sqlite, ProcessedMessage, MessageHeader

def test_write_sqlite_creates_valid_db(tmp_path, message_factory):
    db_path = tmp_path / "test.sqlite"

    # Create sample messages
    msg1 = message_factory(
        msgnum=1,
        refnum=None,
        subject="Thread Start",
        confnum=1,
        text="Content 1\r\nLine 2",
        status=" "
    )
    # Update header with date/time for realistic testing
    msg1.header.msgdate = "01-01-90"
    msg1.header.msgtime = "12:00"
    msg1.header.msgfrom = "Alice"
    msg1.header.msgto = "All"

    msg2 = message_factory(
        msgnum=2,
        refnum=1,
        subject="Re: Thread Start",
        confnum=1,
        text="Reply content",
        status="-"
    )
    msg2.header.msgdate = "01-02-90"
    msg2.header.msgtime = "13:30"
    msg2.header.msgfrom = "Bob"
    msg2.header.msgto = "Alice"

    # Populate threading metadata usually done by _order_messages_by_thread
    msg1.thread_id = "1"
    msg1.depth = 0
    msg1.parent_msgnum = None
    msg1.confname = "Main Board"
    msg1.bbs_name = "MyBBS"
    msg1.source_file = "archive.qwk"
    msg1.attachments = ["file1.txt", "file2.jpg"]

    msg2.thread_id = "1"
    msg2.depth = 1
    msg2.parent_msgnum = 1
    msg2.confname = "Main Board"
    msg2.bbs_name = "MyBBS"
    msg2.source_file = "archive.qwk"

    messages = [msg1, msg2]

    _write_sqlite(messages, str(db_path))

    assert db_path.exists()

    # Verify content
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Check table schema
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
    assert cursor.fetchone() is not None

    # Check data
    cursor.execute("SELECT * FROM messages ORDER BY message_number")
    rows = cursor.fetchall()

    assert len(rows) == 2

    # Row 1 (msg1)
    # id, conference_number, message_number, date, author, recipient, subject, status, text,
    # reference_number, thread_id, depth, parent_message_number, conference_name,
    # bbs_name, source_file, attachments
    r1 = rows[0]
    assert r1[1] == 1  # conference_number
    assert r1[2] == 1  # message_number
    # Date validation: 01-01-90 -> 1990-01-01 12:00:00
    assert "1990-01-01T12:00:00" in r1[3]
    assert r1[4] == "Alice" # author
    assert r1[5] == "All"   # recipient
    assert r1[6] == "Thread Start" # subject
    assert r1[7] == " "     # status
    assert r1[8] == "Content 1\r\nLine 2" # text
    assert r1[9] is None    # reference_number
    assert r1[10] == "1"    # thread_id
    assert r1[11] == 0      # depth
    assert r1[12] is None   # parent_message_number
    assert r1[13] == "Main Board"
    assert r1[14] == "MyBBS"
    assert r1[15] is None  # bbs_id
    assert r1[16] == "archive.qwk"
    assert r1[17] == "file1.txt;file2.jpg"

    # Row 2 (msg2)
    r2 = rows[1]
    assert r2[1] == 1  # conference_number
    assert r2[2] == 2  # message_number
    assert "1990-01-02T13:30:00" in r2[3]
    assert r2[4] == "Bob"
    assert r2[5] == "Alice"
    assert r2[6] == "Re: Thread Start"
    assert r2[7] == "-"
    assert r2[8] == "Reply content"
    assert r2[9] == 1       # reference_number
    assert r2[10] == "1"    # thread_id
    assert r2[11] == 1      # depth
    assert r2[12] == 1      # parent_message_number
    assert r2[13] == "Main Board"
    assert r2[14] == "MyBBS"
    assert r2[15] is None  # bbs_id
    assert r2[16] == "archive.qwk"
    assert r2[17] == ""

    conn.close()

def test_write_sqlite_raises_error_no_output_path(message_factory):
    msg = message_factory(1, None, "Test")
    with pytest.raises(ValueError, match="Output path is required"):
        _write_sqlite([msg], None)

def test_write_sqlite_handles_invalid_date(tmp_path, message_factory):
    db_path = tmp_path / "bad_date.sqlite"
    msg = message_factory(1, None, "Bad Date")
    msg.header.msgdate = "INVALID"
    msg.header.msgtime = "TIME"

    _write_sqlite([msg], str(db_path))

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT date FROM messages WHERE message_number=1")
    date_val = cursor.fetchone()[0]
    conn.close()

    # Should fallback to 1970-01-01
    assert "1970-01-01" in date_val
