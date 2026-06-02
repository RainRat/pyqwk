from pyqwk.core import ParsedMessage, MessageHeader, _get_message_mapping

def test_new_pattern_variables():
    header = MessageHeader(
        status=" ",
        msgnum=123,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="Recipient",
        msgfrom="Author",
        msgsubject="Test Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" "
    )

    text = "Hello world! Check out https://example.com and email me at test@example.com or call 555-1212.\nNew line here."

    msg = ParsedMessage(
        text=text,
        msgnum=123,
        refnum=None,
        confnum=1,
        header=header,
        bbs_id="MYBBS"
    )

    mapping = _get_message_mapping(msg, 1)

    assert mapping["body"] == text
    assert mapping["body_clean"] == "Hello world! Check out https://example.com and email me at test@example.com or call 555-1212. New line here."
    assert mapping["msgid"] == "1.123@MYBBS"
    assert mapping["url_count"] == 1
    assert mapping["email_count"] == 1
    assert mapping["phone_count"] == 1

def test_redaction_in_pattern_variables():
    header = MessageHeader(
        status=" ",
        msgnum=123,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="Recipient",
        msgfrom="Author",
        msgsubject="Test Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" "
    )

    text = "Email me at test@example.com or call 555-1212."

    msg = ParsedMessage(
        text=text,
        msgnum=123,
        refnum=None,
        confnum=1,
        header=header,
        bbs_id="MYBBS"
    )

    mapping = _get_message_mapping(msg, 1, redact_pii=True)

    assert "[EMAIL]" in mapping["body"]
    assert "[PHONE]" in mapping["body"]
    assert "test@example.com" not in mapping["body"]
    assert "555-1212" not in mapping["body"]

    assert "[EMAIL]" in mapping["body_clean"]
    assert "[PHONE]" in mapping["body_clean"]

def test_msgid_fallbacks():
    header = MessageHeader(
        status=" ",
        msgnum=None,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="Recipient",
        msgfrom="Author",
        msgsubject="Test Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=99,
        lognum=0,
        nettag=" "
    )

    msg = ParsedMessage(
        text="No links here",
        msgnum=None,
        refnum=None,
        confnum=99,
        header=header,
        bbs_id=None
    )

    mapping = _get_message_mapping(msg, 1)

    assert mapping["msgid"] == "99.0@"
    assert mapping["url_count"] == 0
