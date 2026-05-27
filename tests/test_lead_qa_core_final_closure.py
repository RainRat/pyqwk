import logging
from pyqwk.core import (
    _parse_text_messages,
    _order_messages_by_thread,
    _parse_html_messages,
    ParsedMessage,
    MessageHeader,
)

def test_parse_text_messages_date_variations(tmp_path):
    # Test whitespace-only date header to hit parts-splitting branch
    content = """From: User A
To: User B
Subject: Topic
Date:
---
Body
"""
    f = tmp_path / "whitespace_date.txt"
    f.write_text(content, encoding="utf-8")

    msgs = _parse_text_messages(str(f))
    assert len(msgs) == 1
    assert msgs[0].header.msgdate == "01-01-70"
    assert msgs[0].header.msgtime == "00:00"

    # Test single-part date header
    content2 = """From: User A
To: User B
Subject: Topic
Date: 2024-06-01
---
Body
"""
    f2 = tmp_path / "single_date.txt"
    f2.write_text(content2, encoding="utf-8")

    msgs2 = _parse_text_messages(str(f2))
    assert len(msgs2) == 1
    assert msgs2[0].header.msgdate == "2024-06-01"
    assert msgs2[0].header.msgtime == "00:00"

def test_order_messages_by_thread_duplicate_cycle_reporting(caplog):
    # Provoke duplicate cycle reporting by creating a complex graph
    # even if it's technically a forest, we can try to force multiple visits
    # to nodes in a cycle if possible.

    def make_msg(num, ref):
        h = MessageHeader(" ", num, "01-01-23", "10:00", "All", "From", "Sub", "", ref, 1, " ", 1, 1, "")
        return ParsedMessage(str(num), num, ref, 1, h)

    # Cycle: 0 -> 1 -> 2 -> 0
    # And another branch that hits it? No, but let's try.
    msgs = [
        make_msg(0, 2), # idx 0, ref 2 -> parent idx 2
        make_msg(1, 0), # idx 1, ref 0 -> parent idx 0
        make_msg(2, 1), # idx 2, ref 1 -> parent idx 1
    ]

    with caplog.at_level(logging.WARNING, logger="pyqwk.core"):
        _order_messages_by_thread(msgs)

    # This should at least hit the cycle reporting once.
    assert any("Conversation loop detected" in r.message for r in caplog.records)

def test_parse_html_messages_loose_div(tmp_path):
    # Covers line 1452: if stack: (False branch) in pyqwk/core.py
    # We need a loose closing div before a message block
    html_content = """
    </div>
    <div class="message">
        <div class="header"><strong>Number:</strong> 1</div>
        <pre class="body">Body</pre>
    </div>
    """
    html_file = tmp_path / "loose_div.html"
    html_file.write_text(html_content, encoding="utf-8")

    messages = _parse_html_messages(str(html_file))
    assert len(messages) == 1
    assert messages[0].depth == 0
