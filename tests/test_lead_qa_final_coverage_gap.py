from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pyqwk.core import _bytes_to_uue, _message_from_email

def test_bytes_to_uue_empty():
    assert _bytes_to_uue(b"", "test.bin") == ""

def test_message_from_email_body_no_newline():
    msg = MIMEMultipart()
    msg['Subject'] = 'Test'
    msg['From'] = 'sender@example.com'
    msg['To'] = 'receiver@example.com'

    body_part = MIMEText('No newline here')
    msg.attach(body_part)

    attachment_part = MIMEText('data')
    attachment_part.add_header('Content-Disposition', 'attachment', filename='test.bin')
    msg.attach(attachment_part)

    parsed = _message_from_email(msg)

    assert "No newline here\n\nbegin 644 test.bin" in parsed.text
