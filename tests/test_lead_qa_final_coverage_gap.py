import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pyqwk.core import _bytes_to_uue, _message_from_email

def test_bytes_to_uue_empty():
    assert _bytes_to_uue(b"", "test.bin") == ""

def test_message_from_email_body_no_newline_with_attachments():
    msg = MIMEMultipart()

    # Create a text part without a trailing newline
    text_part = MIMEText("")
    text_part.set_payload("Hello World") # No trailing \n
    msg.attach(text_part)

    # Add an attachment to trigger uue_blocks
    app_part = MIMEApplication(b"binary data")
    app_part.add_header("Content-Disposition", "attachment", filename="test.bin")
    msg.attach(app_part)

    parsed = _message_from_email(msg)

    # Line 1406: if body and not body.endswith("\n"): body += "\n"
    # The body should now have a newline before the UUE blocks
    assert "Hello World\n\nbegin 644 test.bin" in parsed.text
    assert parsed.text.startswith("Hello World\n\n")

if __name__ == "__main__":
    # Quick manual verification of the MIME part
    msg = MIMEMultipart()
    text_part = MIMEText("")
    text_part.set_payload("Hello World")
    print(f"Payload: {repr(text_part.get_payload())}")

    test_bytes_to_uue_empty()
    test_message_from_email_body_no_newline_with_attachments()
    print("Tests passed!")
