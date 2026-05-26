import email
import os
import binascii
from pyqwk.core import ParsedMessage, MessageHeader, _serialize_rfc822, _message_from_email, extract_binaries

def test_eml_mime_export_with_attachment():
    """Verify that a message with UUE content is exported as a MIME email with an attachment."""
    # "Cat" in UUE is #0V%T
    uue_content = (
        "begin 644 test.txt\r\n"
        "#0V%T\r\n"
        "`\r\n"
        "end"
    )
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto="Recipient", msgfrom="Author", msgsubject="Test Subject",
        msgpassword="", refnum=None, numblocks=None, msgflag=" ",
        confnum=1, lognum=0, nettag=""
    )
    msg = ParsedMessage(text="Hello world\r\n" + uue_content, msgnum=1, refnum=None, confnum=1, header=header)

    # Export to EML (no mbox header)
    eml_str = _serialize_rfc822(msg, include_mbox_header=False)

    # Parse back with standard email library to verify MIME structure
    eml_obj = email.message_from_string(eml_str)
    assert eml_obj.is_multipart()

    attachments = []
    for part in eml_obj.walk():
        if part.get_filename():
            attachments.append((part.get_filename(), part.get_payload(decode=True)))

    assert len(attachments) == 1
    assert attachments[0][0] == "test.txt"
    assert attachments[0][1] == b"Cat"

def test_eml_mime_import_with_attachment():
    """Verify that a MIME email with an attachment is imported with the attachment as UUE."""
    raw_eml = (
        "From: Author\n"
        "To: Recipient\n"
        "Subject: Test Subject\n"
        "Content-Type: multipart/mixed; boundary=\"bound\"\n"
        "\n"
        "--bound\n"
        "Content-Type: text/plain\n"
        "\n"
        "Main body text\n"
        "--bound\n"
        "Content-Type: application/octet-stream\n"
        "Content-Disposition: attachment; filename=\"hello.bin\"\n"
        "Content-Transfer-Encoding: base64\n"
        "\n"
        "SGVsbG8=\n" # "Hello" in base64
        "--bound--"
    )
    msg_obj = email.message_from_string(raw_eml)
    parsed = _message_from_email(msg_obj)

    assert "Main body text" in parsed.text
    assert "begin 644 hello.bin" in parsed.text
    assert "end" in parsed.text

    # Verify extraction works on the imported text
    binaries = extract_binaries(parsed.text)
    assert len(binaries) == 1
    assert binaries[0][0] == "hello.bin"
    assert binaries[0][1] == b"Hello"

def test_eml_mime_roundtrip():
    """Verify full roundtrip: ParsedMessage -> EML -> ParsedMessage."""
    # Use "Cat" (#0V%T) which is reliable
    original_uue = (
        "begin 644 data.dat\r\n"
        "#0V%T\r\n"
        "`\r\n"
        "end"
    )
    header = MessageHeader(
        status=" ", msgnum=123, msgdate="05-26-24", msgtime="14:00",
        msgto="World", msgfrom="Jules", msgsubject="Roundtrip",
        msgpassword="", refnum=None, numblocks=None, msgflag=" ",
        confnum=10, lognum=0, nettag=""
    )
    original_msg = ParsedMessage(text="Roundtrip test\r\n" + original_uue, msgnum=123, refnum=None, confnum=10, header=header)

    # 1. Export
    eml_str = _serialize_rfc822(original_msg, include_mbox_header=False)

    # 2. Import
    msg_obj = email.message_from_string(eml_str)
    imported_msg = _message_from_email(msg_obj)

    # 3. Verify
    assert imported_msg.header.msgfrom == "Jules"
    assert imported_msg.header.msgsubject == "Roundtrip"
    assert "Roundtrip test" in imported_msg.text

    binaries = extract_binaries(imported_msg.text)
    assert len(binaries) == 1
    assert binaries[0][0] == "data.dat"
    assert binaries[0][1] == b"Cat"
