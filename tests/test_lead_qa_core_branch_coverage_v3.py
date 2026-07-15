import logging
import io
import os
import re
from unittest.mock import MagicMock
import pyqwk.core as qwk
from pyqwk.core import ProcessingSettings, _compute_stats_from_messages, ParsedMessage, MessageHeader, _order_messages_by_thread, _render_info_html, _render_info_markdown

def test_manual_parse_text_date_empty_parts(tmp_path):
    # Date line exists but has no content after 'Date:'
    # to trigger len(parts) < 1 (branch 1730->1732)
    text = "From: Alice\nTo: Bob\nSubject: Hello\nDate:\nBBS: MyBBS\n\nBody1"

    from pyqwk.core import _parse_text_messages
    p = tmp_path / "test_empty_date.txt"
    p.write_text(text)

    messages = _parse_text_messages(str(p))
    assert len(messages) == 1
    # Line 1730 False path hit because parts is []
    assert messages[0].header.msgdate == "01-01-70"
    assert messages[0].header.msgtime == "00:00"

def test_compute_stats_comprehensive_timing():
    def make_h(msgnum, refnum, time):
        return MessageHeader(
            status=" ", msgnum=msgnum, msgdate="01-01-23", msgtime=time,
            msgto="All", msgfrom="User", msgsubject="Subj",
            msgpassword="", refnum=refnum, numblocks=1, msgflag=" ",
            confnum=1, lognum=1, nettag=""
        )

    msgs = [
        ParsedMessage(text="M1", msgnum=1, refnum=None, confnum=1, header=make_h(1, None, "12:00")),
        ParsedMessage(text="M2", msgnum=2, refnum=1, confnum=1, header=make_h(2, 1, "12:05")),
        ParsedMessage(text="M3", msgnum=3, refnum=1, confnum=1, header=make_h(3, 1, "11:55")),
        ParsedMessage(text="M4", msgnum=4, refnum=999, confnum=1, header=make_h(4, 999, "12:10")),
        ParsedMessage(text="M5", msgnum=None, refnum=None, confnum=1, header=make_h(None, None, "12:00")),
    ]

    stats = _compute_stats_from_messages(iter(msgs), "test.qwk")
    assert stats["matching_messages"] == 5

def test_order_messages_by_thread_multi_loop():
    # Covers cycle_reported branch (6849->6857 False path)
    # We need a node to be in 'path' and already in 'cycle_reported'
    def make_msg(m, r):
        h = MessageHeader(
            status=" ", msgnum=m, msgdate="01-01-23", msgtime="12:00",
            msgto="All", msgfrom="User", msgsubject="Subj",
            msgpassword="", refnum=r, numblocks=1, msgflag=" ",
            confnum=1, lognum=1, nettag=""
        )
        return ParsedMessage(text="T", msgnum=m, refnum=r, confnum=1, header=h)

    # index 0: 10 -> None (root)
    # index 1: 11 -> 10
    # index 2: 12 -> 11
    # index 3: 11 -> 12 (Loop 1: 11-12. 11 will be reported)
    # index 4: 13 -> 11
    # index 5: 11 -> 13 (Loop 2: 11-13. 11 is already in cycle_reported!)

    m0 = make_msg(10, None)
    m1 = make_msg(11, 10)
    m2 = make_msg(12, 11)
    m3 = make_msg(11, 12)
    m4 = make_msg(13, 11)
    m5 = make_msg(11, 13)

    messages = [m0, m1, m2, m3, m4, m5]
    ordered = _order_messages_by_thread(messages)
    assert len(ordered) == 6

def test_render_info_bbs_missing_fields():
    info = {
        "file": "test.qwk",
        "bbs_info": {"sysop": "Dave"}, # No 'name'
        "total_messages": 10,
        "matching_messages": 5,
        "conferences": [{"number": 1, "name": "General", "message_count": 5}],
        "authors": [],
        "recipients": []
    }

    html = _render_info_html([info])
    assert any("Dave" in part for part in html)

    md = _render_info_markdown([info])
    assert any("Dave" in part for part in md)
