import sqlite3
import pytest
from pyqwk.core import _parse_json_messages, _parse_sqlite_messages, ParsedMessage, MessageHeader

def test_parse_json_messages_with_null_depth_extra():
    data = [
        {
            "header": {"msgnum": 1, "confnum": 1, "msgfrom": "A", "msgto": "B", "msgsubject": "S"},
            "text": "Hello",
            "depth": None
        }
    ]
    messages = _parse_json_messages(data)
    assert len(messages) == 1
    assert isinstance(messages[0].depth, int)
    assert messages[0].depth == 0

def test_parse_sqlite_messages_with_null_depth_extra(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE messages (conference_number, message_number, date, author, recipient, subject, status, reference_number, attachments, text, depth, thread_id, parent_message_number, conference_name, bbs_name, bbs_id, source_file)")
    conn.execute("""
        INSERT INTO messages (conference_number, message_number, date, author, recipient, subject, text, depth)
        VALUES (1, 1, '2023-01-01', 'A', 'B', 'S', 'Hello', NULL)
    """)
    conn.commit()
    conn.close()

    messages, _ = _parse_sqlite_messages(db_path)
    assert len(messages) == 1
    assert isinstance(messages[0].depth, int)
    assert messages[0].depth == 0
