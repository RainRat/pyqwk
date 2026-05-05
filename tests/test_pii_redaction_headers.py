import pytest
from pyqwk.core import MessageHeader, ConferenceMap, ParsedMessage, _get_message_mapping


def test_header_format_text_redaction():
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="user@example.com",
        msgfrom="555-1234",
        msgsubject="Secret 123-456-7890",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )

    # Without redaction
    formatted = header.format_text({1: "General"}, verbose=False)
    assert "user@example.com" in formatted
    assert "555-1234" in formatted
    assert "123-456-7890" in formatted

    # With redaction
    redacted = header.format_text({1: "General"}, verbose=False, redact_pii=True)
    assert "[EMAIL]" in redacted
    assert "user@example.com" not in redacted
    assert "[PHONE]" in redacted
    assert "555-1234" not in redacted
    assert "123-456-7890" not in redacted


def test_header_format_oneline_redaction():
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="user@example.com",
        msgfrom="555-1234",
        msgsubject="Secret 123-456-7890",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )

    # With redaction
    redacted = header.format_oneline({1: "General"}, redact_pii=True)
    assert "[EMAIL]" in redacted
    assert "[PHONE]" in redacted
    assert "Secret" in redacted
    assert "123-456-7890" not in redacted


def test_get_message_mapping_redaction():
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="user@example.com",
        msgfrom="555-1234",
        msgsubject="Secret 123-456-7890",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg = ParsedMessage(
        text="Body with 111-222-3333", msgnum=1, refnum=None, confnum=1, header=header
    )

    mapping = _get_message_mapping(msg, 1, redact_pii=True)
    assert mapping["author"] == "[PHONE]"
    assert mapping["to"] == "[EMAIL]"
    assert "Secret [PHONE]" in mapping["subject"]
    assert "[PHONE]" in mapping["snippet"]
