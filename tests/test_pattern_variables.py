from pyqwk.core import ParsedMessage, MessageHeader, _get_message_mapping

def test_extended_pattern_variables():
    header = MessageHeader(
        status="*",
        msgnum=123,
        msgdate="10-12-23",
        msgtime="14:30:00",
        msgto="Recipient Name",
        msgfrom="Author Name",
        msgsubject="Re[123]: Important Subject",
        msgpassword="",
        refnum=456,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" "
    )

    text = "Sample message body with https://example.com and test@example.com or 555-1212.\nNew line."

    message = ParsedMessage(
        text=text,
        msgnum=123,
        refnum=456,
        confnum=1,
        header=header,
        confname="General",
        bbs_name="The BBS",
        bbs_id="THEBBS",
        source_file="archive.qwk",
        attachments=["file1.zip", "image.jpg"]
    )

    mapping = _get_message_mapping(message, count=1)

    # Existing variables
    assert mapping["author"] == "Author Name"
    assert mapping["to"] == "Recipient Name"
    assert mapping["subject"] == "Re[123]: Important Subject"
    assert mapping["confnum"] == 1
    assert mapping["confname"] == "General"

    # New variables from test_pattern_variables.py
    assert mapping["subject_clean"] == "Important Subject"
    assert mapping["confname_or_num"] == "General"
    assert mapping["source_file"] == "archive.qwk"
    assert mapping["refnum"] == 456
    assert mapping["status"] == "*"
    assert mapping["msgflag"] == " "
    assert mapping["is_private"] == "true"
    assert mapping["is_reply"] == "true"
    assert mapping["attachments"] == "file1.zip, image.jpg"
    assert mapping["attachment_count"] == 2

    # Added variables from test_pattern_vars.py
    assert mapping["body"] == text
    assert mapping["body_clean"] == "Sample message body with https://example.com and test@example.com or 555-1212. New line."
    assert mapping["msgid"] == "1.123@THEBBS"
    assert mapping["url_count"] == 1
    assert mapping["email_count"] == 1
    assert mapping["phone_count"] == 1

def test_extended_variables_redact_pii():
    header = MessageHeader(
        status=" ",
        msgnum=123,
        msgdate="10-12-23",
        msgtime="14:30:00",
        msgto="Recipient Name",
        msgfrom="Author Name",
        msgsubject="Re: Contact me at 555-1234",
        msgpassword="",
        refnum=0,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" "
    )

    text = "Body: email@example.com and 555-1212"
    message = ParsedMessage(
        text=text,
        msgnum=123,
        refnum=None,
        confnum=1,
        header=header
    )

    mapping = _get_message_mapping(message, count=1, redact_pii=True)

    assert mapping["subject"] == "Re: Contact me at [PHONE]"
    assert mapping["subject_clean"] == "Contact me at [PHONE]"
    assert mapping["snippet"] == "Body: [EMAIL] and [PHONE]"

    # Added redaction checks from test_pattern_vars.py
    assert "[EMAIL]" in mapping["body"]
    assert "[PHONE]" in mapping["body"]
    assert "email@example.com" not in mapping["body"]
    assert "555-1212" not in mapping["body"]
    assert "[EMAIL]" in mapping["body_clean"]
    assert "[PHONE]" in mapping["body_clean"]

def test_confname_or_num_fallback():
    header = MessageHeader(
        status=" ",
        msgnum=123,
        msgdate="10-12-23",
        msgtime="14:30:00",
        msgto="Recipient",
        msgfrom="Author",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=42,
        lognum=0,
        nettag=" "
    )

    message = ParsedMessage(
        text="Text",
        msgnum=123,
        refnum=None,
        confnum=42,
        header=header,
        confname=None
    )

    mapping = _get_message_mapping(message, count=1)
    assert mapping["confname"] == ""
    assert mapping["confname_or_num"] == "42"

def test_msgid_fallbacks():
    # Scenario from test_pattern_vars.py
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
