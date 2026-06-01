from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pyqwk.core import _bytes_to_uue, _message_from_email

def test_bytes_to_uue_empty():
    """Cover line 475: if not data in _bytes_to_uue."""
    assert _bytes_to_uue(b"", "test.bin") == ""

def test_message_from_email_body_no_newline_with_attachment():
    """Cover line 1406: if body and not body.endswith('\\n') in _message_from_email."""
    msg = MIMEMultipart()

    # We use a text part that doesn't end with a newline
    part1 = MIMEText("No newline", "plain")
    # EmailMessage/MIMEText sometimes adds newlines automatically,
    # but _message_from_email will see what's in the payload.
    part1.set_payload("No newline")
    msg.attach(part1)

    # Add an attachment to trigger the UUE block appending logic
    part2 = MIMEApplication(b"data")
    part2.add_header("Content-Disposition", "attachment", filename="test.bin")
    msg.attach(part2)

    parsed = _message_from_email(msg)

    # The result should have exactly one newline added before the double-newline separator
    # 'No newline' + '\n' (from line 1406) + '\n' + UUE_BLOCK (from line 1407)
    assert parsed.text.startswith("No newline\n\nbegin 644 test.bin")
