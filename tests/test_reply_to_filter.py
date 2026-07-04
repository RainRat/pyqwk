import pytest
from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings, matches_filters

def test_reply_to_filter():
    # Helper to create a message with a specific refnum
    def create_msg(msgnum, refnum):
        header = MessageHeader(
            status=" ",
            msgnum=msgnum,
            msgdate="01-01-23",
            msgtime="12:00",
            msgto="All",
            msgfrom="User",
            msgsubject="Test",
            msgpassword="",
            refnum=refnum,
            numblocks=1,
            msgflag=" ",
            confnum=1,
            lognum=0,
            nettag=" "
        )
        return ParsedMessage(text="Test", msgnum=msgnum, refnum=refnum, confnum=1, header=header)

    msg1 = create_msg(101, 100)
    msg2 = create_msg(102, 101)
    msg3 = create_msg(103, 200)

    # Base settings
    base_settings = {
        "verbose": False, "private": True, "no_header": False,
        "truncate_signatures": False, "cut_quoting": False,
        "individual_files": False, "threaded": False,
        "binaries_removal": False, "redact_pii": False,
        "format": "text", "separator": "auto", "output_mode": "stdout",
        "output_path": None, "encoding": "cp437"
    }

    # Test single number
    settings = ProcessingSettings(**base_settings, refnum_filters={100})
    assert matches_filters(msg1, settings, set()) is True
    assert matches_filters(msg2, settings, set()) is False

    # Test range
    settings = ProcessingSettings(**base_settings, refnum_filters=set(range(100, 102)))
    assert matches_filters(msg1, settings, set()) is True
    assert matches_filters(msg2, settings, set()) is True
    assert matches_filters(msg3, settings, set()) is False

def test_text_parser_ref_alias(tmp_path):
    from pyqwk.core import _parse_text_messages

    content = """
From: User1
To: User2
Subject: Hello
Ref #: 123

How are you?
"""
    file_path = tmp_path / "test.txt"
    file_path.write_text(content)

    messages = _parse_text_messages(str(file_path))
    assert len(messages) == 1
    assert messages[0].refnum == 123
    assert messages[0].header.refnum == 123
