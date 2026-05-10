import pytest
from pyqwk.core import ParsedMessage, MessageHeader, _get_message_mapping

def test_get_message_mapping_discovers_attachments():
    """Verify that _get_message_mapping triggers attachment discovery."""
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="To",
        msgfrom="From",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=None,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" "
    )

    # Body contains a UUE attachment
    body = "Hello\nbegin 644 test.txt\nM(R!A(&9I;&4@(&-O;G1E;G0@;V8@=&5S=\"!F:6QE+@H`\nend\n"
    msg = ParsedMessage(
        text=body,
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
        attachments=None  # Explicitly None to trigger discovery
    )

    # Initially attachments is None
    assert msg.attachments is None

    # Getting mapping should trigger discovery
    mapping = _get_message_mapping(msg, 1)

    # Check that discovery happened and flags/count are correct
    assert msg.attachments == ["test.txt"]
    assert mapping["flags"] == "@"
    assert mapping["attachment_count"] == 1
    assert mapping["attachments"] == "test.txt"
