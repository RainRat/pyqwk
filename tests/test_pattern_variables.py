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

    message = ParsedMessage(
        text="Sample message body",
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

    # New variables
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

    message = ParsedMessage(
        text="Sample message body with email@example.com",
        msgnum=123,
        refnum=None,
        confnum=1,
        header=header
    )

    mapping = _get_message_mapping(message, count=1, redact_pii=True)

    assert mapping["subject"] == "Re: Contact me at [PHONE]"
    assert mapping["subject_clean"] == "Contact me at [PHONE]"
    assert mapping["snippet"] == "Sample message body with [EMAIL]"

def test_snippet_pii_truncation_leak():
    """Verify that PII is redacted even if it would be cut off by snippet truncation."""
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-24", msgtime="12:00",
        msgto="To", msgfrom="From", msgsubject="Subj", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" "
    )
    # 45 chars followed by a phone number. Truncation at 50 would cut the phone number.
    text = "A" * 45 + " 555-1212"
    msg = ParsedMessage(text=text, msgnum=1, refnum=None, confnum=1, header=header)

    mapping = _get_message_mapping(msg, 1, redact_pii=True)
    snippet = mapping["snippet"]

    # Should contain the start of the redacted placeholder, not the start of the phone number
    assert "[PHO" in snippet
    assert "555" not in snippet

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
