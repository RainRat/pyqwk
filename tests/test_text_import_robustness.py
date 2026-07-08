import pytest
import os
from pyqwk.core import _parse_text_messages

def test_text_import_robustness(tmp_path):
    """Test that plain text import handles indented headers and Ref #: alias."""
    content = """From: Jules
To: Everyone
Subject: Test 1
Ref #: 123

Normal message.
------------------------------------------------------------
  From: Jules
  To: Everyone
  Subject: Test 2
  Ref #: 456

Indented message.
------------------------------------------------------------
From: Jules
To: Everyone
Subject: Test 3
Reference #: 789

Message with Reference #: header.
"""
    test_file = tmp_path / "test_robustness.txt"
    test_file.write_text(content)

    msgs = _parse_text_messages(str(test_file))

    assert len(msgs) == 3

    assert msgs[0].header.msgsubject == "Test 1"
    assert msgs[0].refnum == 123

    assert msgs[1].header.msgsubject == "Test 2"
    assert msgs[1].refnum == 456

    assert msgs[2].header.msgsubject == "Test 3"
    assert msgs[2].refnum == 789

def test_text_import_mixed_indentation(tmp_path):
    """Test that plain text import handles mixed indentation within headers."""
    content = """From: Jules
  To: Everyone
Subject: Test Mixed
  Ref #: 111

Body starts here.
"""
    test_file = tmp_path / "test_mixed.txt"
    test_file.write_text(content)

    msgs = _parse_text_messages(str(test_file))

    assert len(msgs) == 1
    assert msgs[0].header.msgfrom == "Jules"
    assert msgs[0].header.msgto == "Everyone"
    assert msgs[0].header.msgsubject == "Test Mixed"
    assert msgs[0].refnum == 111
