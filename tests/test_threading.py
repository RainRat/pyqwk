import pytest
import logging
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qwk import (
    ProcessedMessage,
    MessageHeader,
    _order_messages_by_thread,
    _write_text,
    _write_html,
    _write_json,
    _write_xml,
)
from unittest.mock import patch, mock_open

# Helper to create messages
def make_msg(msgnum, refnum, subject, confnum=1, text="Body\n"):
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="",
        msgtime="",
        msgto="",
        msgfrom="",
        msgsubject=subject,
        msgpassword="",
        refnum=refnum,
        numblocks=None,
        msgflag="",
        confnum=confnum,
        lognum=0,
        nettag="",
    )
    return ProcessedMessage(
        text=text,
        msgnum=msgnum,
        refnum=refnum,
        confnum=confnum,
        header=header
    )

def test_threading_depth_and_structure():
    msgs = [
        make_msg(1, 0, "Root"),
        make_msg(2, 1, "Child 1"),
        make_msg(3, 2, "Grandchild 1"),
        make_msg(4, 1, "Child 2"),
        make_msg(5, 0, "Root 2"),
    ]

    ordered = _order_messages_by_thread(msgs)

    # Check order
    assert [m.msgnum for m in ordered] == [1, 2, 3, 4, 5]
    # Check depth
    assert [m.depth for m in ordered] == [0, 1, 2, 1, 0]
    # Check parents
    assert ordered[2].parent_msgnum == 2

def test_fallback_subject_threading():
    msgs = [
        make_msg(10, 0, "Important Topic"),
        make_msg(11, 0, "Re: Important Topic"), # Missing refnum, should match by subject
        make_msg(12, 11, "Re: Important Topic"), # Explicit refnum to 11
        make_msg(13, 0, "Other Topic"),
        make_msg(14, 0, "Re: Important Topic"), # Another one matching root or last one?
    ]

    # 14 should probably attach to 10 or 11 or 12 depending on logic.
    # Logic: Prefer candidate appearing before.
    # For 11: candidates [10]. Parent -> 10.
    # For 14: candidates [10, 11, 12]. Parent -> 12.

    ordered = _order_messages_by_thread(msgs)

    # Order should be 10 -> 11 -> 12 -> 14, then 13 separately

    ids = [m.msgnum for m in ordered]
    # 13 is root, 10 is root.
    # 10, 11, 12, 14, 13 (or 13 anywhere if it's root)

    # Check 11's parent
    m11 = next(m for m in ordered if m.msgnum == 11)
    assert m11.parent_msgnum == 10
    assert m11.depth == 1

    # Check 14's parent
    m14 = next(m for m in ordered if m.msgnum == 14)
    assert m14.parent_msgnum == 12
    assert m14.depth == 3

def test_text_output_indentation():
    msgs = [
        make_msg(1, 0, "Root", text="RootBody\n"),
        make_msg(2, 1, "Child", text="ChildBody\n"),
    ]
    msgs[1].depth = 1 # Manually set depth as _write_text expects it

    with patch("qwk._write_text_output") as mock_write:
        _write_text(msgs, None)
        content = mock_write.call_args[0][0]
        assert "RootBody" in content
        assert "  ChildBody" in content

def test_html_output_nesting():
    msgs = [
        make_msg(1, 0, "Root"),
        make_msg(2, 1, "Child"),
    ]
    msgs[0].depth = 0
    msgs[1].depth = 1

    with patch("qwk._write_text_output") as mock_write:
        _write_html(msgs, None)
        content = mock_write.call_args[0][0]
        # Should contain nested structure
        # Child is depth 1, should be preceded by <div class="reply">
        assert '<div class="reply">' in content
        assert content.count('<div class="reply">') == 1

def test_json_metadata():
    msgs = [make_msg(1, 0, "Root")]
    msgs[0].depth = 0
    msgs[0].thread_id = "1"

    with patch("qwk._write_text_output") as mock_write:
        _write_json(msgs, None)
        content = mock_write.call_args[0][0]
        data = json.loads(content)
        assert data[0]['depth'] == 0
        assert data[0]['thread_id'] == "1"

def test_xml_metadata():
    msgs = [make_msg(1, 0, "Root")]
    msgs[0].depth = 1
    msgs[0].thread_id = "thread1"

    with patch("qwk._write_text_output") as mock_write:
        _write_xml(msgs, None)
        content = mock_write.call_args[0][0]
        assert "<depth>1</depth>" in content
        assert "<thread_id>thread1</thread_id>" in content
