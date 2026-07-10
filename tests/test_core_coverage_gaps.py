import logging
from pyqwk.core import (
    _parse_text_messages,
    _render_info_html,
    _render_info_markdown,
    _compute_stats_from_messages,
    _order_messages_by_thread,
    _serialize_rfc822,
    ParsedMessage,
    MessageHeader
)

def test_parse_text_messages_empty_date_parts(tmp_path):
    # 1730->1732: date_str exists but split() is empty (e.g. whitespace only)
    content = "From: Alice\nTo: Bob\nSubject: Hello\nDate:    \n\nBody"
    path = tmp_path / "empty_date.txt"
    path.write_text(content)

    msgs = _parse_text_messages(str(path))
    assert len(msgs) == 1
    assert msgs[0].header.msgdate == "01-01-70"
    assert msgs[0].header.msgtime == "00:00"

def test_render_info_missing_bbs_name():
    # 5889->5893, 5943->5945: missing BBS name in HTML/MD rendering
    info = [{
        "file": "test.qwk",
        "total_messages": 1,
        "conferences": [],
        "bbs_info": {
            "name": "",  # Trigger False branch
            "sysop": "SysOp",
            "location": "Loc",
            "bbs_id": "ID",
            "packet_at": "Date",
            "user_name": "User"
        }
    }]

    html = "".join(_render_info_html(info))
    assert "BBS Name:" not in html
    assert "SysOp:" in html

    md = "".join(_render_info_markdown(info))
    assert "**BBS Name:**" not in md
    assert "**SysOp:**" in md

def test_compute_stats_edge_cases():
    # 6165->6169: msgnum is None
    h1 = MessageHeader(status=" ", msgnum=None, msgdate="01-01-24", msgtime="12:00", msgto="B", msgfrom="A", msgsubject="S", msgpassword="", refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" ")
    m1 = ParsedMessage(text="B1", msgnum=None, refnum=None, confnum=1, header=h1)

    # 6177->6183: parent_key not in msg_timestamps (reply to external msg)
    h2 = MessageHeader(status=" ", msgnum=2, msgdate="01-01-24", msgtime="12:01", msgto="B", msgfrom="A", msgsubject="Re: S", msgpassword="", refnum=999, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" ")
    m2 = ParsedMessage(text="B2", msgnum=2, refnum=999, confnum=1, header=h2)

    # 6179->6183: delta < 0 (child date before parent date)
    h3 = MessageHeader(status=" ", msgnum=3, msgdate="01-01-24", msgtime="11:59", msgto="B", msgfrom="A", msgsubject="Re: S", msgpassword="", refnum=2, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" ")
    m3 = ParsedMessage(text="B3", msgnum=3, refnum=2, confnum=1, header=h3)

    stats = _compute_stats_from_messages(iter([m1, m2, m3]))
    assert stats["total_messages"] == 3
    assert stats["reply_count"] == 2

def test_threading_cycle_re_reporting(caplog):
    # 6849->6857: cycle already reported suppression
    # m1 -> m2 -> m3 -> m1 (Cycle)
    # m4 -> m1 (External entry into cycle)
    h1 = MessageHeader(status=" ", msgnum=1, msgdate="D", msgtime="T", msgto="B", msgfrom="A", msgsubject="L", msgpassword="", refnum=3, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" ")
    h2 = MessageHeader(status=" ", msgnum=2, msgdate="D", msgtime="T", msgto="C", msgfrom="B", msgsubject="L", msgpassword="", refnum=1, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" ")
    h3 = MessageHeader(status=" ", msgnum=3, msgdate="D", msgtime="T", msgto="A", msgfrom="C", msgsubject="L", msgpassword="", refnum=2, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" ")
    h4 = MessageHeader(status=" ", msgnum=4, msgdate="D", msgtime="T", msgto="A", msgfrom="D", msgsubject="L", msgpassword="", refnum=1, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" ")

    m1 = ParsedMessage(text="B1", msgnum=1, refnum=3, confnum=1, header=h1)
    m2 = ParsedMessage(text="B2", msgnum=2, refnum=1, confnum=1, header=h2)
    m3 = ParsedMessage(text="B3", msgnum=3, refnum=2, confnum=1, header=h3)
    m4 = ParsedMessage(text="B4", msgnum=4, refnum=1, confnum=1, header=h4)

    with caplog.at_level(logging.WARNING):
        _order_messages_by_thread([m4, m1, m2, m3])

    assert "Conversation loop detected" in caplog.text

def test_serialize_rfc822_mbox_fallback():
    # 4968->4970: sender address lacks '@', triggering fallback
    header = MessageHeader(status=" ", msgnum=1, msgdate="01-01-24", msgtime="12:00", msgto="Recipient", msgfrom="Name Without At", msgsubject="S", msgpassword="", refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" ")
    msg = ParsedMessage(text="Body", msgnum=1, refnum=None, confnum=1, header=header)

    output = _serialize_rfc822(msg, include_mbox_header=True)
    assert "From Name.Without.At@example.com" in output
