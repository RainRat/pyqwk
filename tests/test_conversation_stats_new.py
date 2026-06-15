import pytest
import datetime
from pyqwk.core import (
    _compute_stats_from_messages,
    ParsedMessage,
    MessageHeader,
    render_stats_as_text,
    _render_stats_html,
    _render_stats_markdown,
)

def _make_msg(confnum, msgnum, refnum, date_str, time_str, author="Author"):
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate=date_str,
        msgtime=time_str,
        msgto="To",
        msgfrom=author,
        msgsubject="Subj",
        msgpassword="",
        refnum=refnum,
        numblocks=2,
        msgflag=" ",
        confnum=confnum,
        lognum=0,
        nettag=" ",
    )
    return ParsedMessage(
        text="Body",
        msgnum=msgnum,
        refnum=refnum,
        confnum=confnum,
        header=header,
    )

def test_conversation_stats_logic():
    # Scenario:
    # 1. Root (10:00:00)
    # 2. Reply to 1 (10:01:00) -> 60s delta
    # 3. Reply to 2 (10:03:00) -> 120s delta
    # 4. Another Root (11:00:00)
    # 5. Reply to 4 (11:00:05) -> 5s delta

    msgs = [
        _make_msg(1, 1, 0, "01-01-23", "10:00:00", author="A"),
        _make_msg(1, 2, 1, "01-01-23", "10:01:00", author="B"),
        _make_msg(1, 3, 2, "01-01-23", "10:03:00", author="C"),
        _make_msg(1, 4, 0, "01-01-23", "11:00:00", author="D"),
        _make_msg(1, 5, 4, "01-01-23", "11:00:05", author="E"),
    ]

    stats = _compute_stats_from_messages(iter(msgs))
    conv = stats["conversation"]

    # Deltas: 60, 120, 5
    assert conv["thread_count"] == 2
    assert conv["avg_thread_length"] == 2.5 # (3 + 2) / 2
    assert conv["max_thread_length"] == 3
    assert conv["min_response_time"] == 5.0
    assert conv["max_response_time"] == 120.0
    assert conv["avg_response_time"] == pytest.approx(61.6666, 0.01)

def test_author_responsiveness():
    # Author B has two replies with different speeds
    msgs = [
        _make_msg(1, 1, 0, "01-01-23", "10:00:00", author="A"),
        _make_msg(1, 2, 1, "01-01-23", "10:00:10", author="B"), # 10s
        _make_msg(1, 3, 0, "01-01-23", "11:00:00", author="A"),
        _make_msg(1, 4, 3, "01-01-23", "11:00:20", author="B"), # 20s
        _make_msg(1, 5, 0, "01-01-23", "12:00:00", author="A"),
        _make_msg(1, 6, 5, "01-01-23", "12:00:05", author="C"), # 5s (only 1 reply, should be excluded from top responders)
    ]

    stats = _compute_stats_from_messages(iter(msgs))
    responders = stats["conversation"]["top_responders"]

    # B has 2 replies, avg 15s. C has 1 reply, avg 5s.
    # Logic excludes authors with < 2 replies.
    assert len(responders) == 1
    assert responders[0]["name"] == "B"
    assert responders[0]["avg_speed"] == 15.0

def test_rendering_smoke():
    msgs = [
        _make_msg(1, 1, 0, "01-01-23", "10:00:00", author="A"),
        _make_msg(1, 2, 1, "01-01-23", "10:00:10", author="B"),
        _make_msg(1, 3, 2, "01-01-23", "10:00:20", author="B"),
    ]
    stats = _compute_stats_from_messages(iter(msgs))

    text = render_stats_as_text(stats, use_colors=False)
    assert "Conversation Analysis:" in text
    assert "Threads:       1" in text
    assert "Fastest Responders (min 2 replies):" in text
    assert "B" in text

    html = "\n".join(_render_stats_html(stats))
    assert "Threads:" in html
    assert "Fastest Responders" in html

    md = "\n".join(_render_stats_markdown(stats))
    assert "Conversation:" in md
    assert "Fastest Responders" in md
