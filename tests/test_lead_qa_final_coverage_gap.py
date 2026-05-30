import pytest
from unittest.mock import MagicMock
from pyqwk.core import _bytes_to_uue, _message_from_email

def test_bytes_to_uue_empty():
    """Cover line 475: _bytes_to_uue with empty data."""
    assert _bytes_to_uue(b"", "test.txt") == ""

def test_message_from_email_body_no_newline():
    """Cover line 1406: multipart email body not ending in newline with attachments."""
    mock_msg = MagicMock()
    mock_msg.is_multipart.return_value = True

    # Header fields
    headers = {
        "Date": "Fri, 01 Jan 2024 12:00:00 +0000",
        "From": "Alice",
        "To": "Bob",
        "Subject": "Test",
        "X-QWK-MsgNum": "1",
        "X-QWK-RefNum": "0",
        "X-QWK-ConfNum": "1",
        "X-QWK-Status": " "
    }
    mock_msg.get.side_effect = lambda k, d=None: headers.get(k, d)

    # Body part (text/plain, no newline)
    part1 = MagicMock()
    part1.get_content_type.return_value = "text/plain"
    part1.get_filename.return_value = None
    part1.get_payload.return_value = b"Body without newline"

    # Attachment part
    part2 = MagicMock()
    part2.get_content_type.return_value = "application/octet-stream"
    part2.get_filename.return_value = "attach.bin"
    part2.get_payload.return_value = b"binarydata"

    # In _message_from_email, it iterates through walk()
    # The first item returned by walk() is often the message itself.
    # If mock_msg is returned, it will hit line 1386 (content_type="text/plain" and not filename and not body)
    # But wait, mock_msg.get_content_type() might not be text/plain.
    # Let's ensure walk() only returns the parts we want to process.
    mock_msg.walk.return_value = [part1, part2]

    msg = _message_from_email(mock_msg)

    # Check that a newline was added between body and attachment block
    # The code does: body += "\n" if not body.endswith("\n")
    # Then: body += "\n" + "\n".join(uue_blocks)
    # Result should have TWO newlines before "begin 644"
    assert "Body without newline\n\nbegin 644 attach.bin" in msg.text
    assert msg.text.startswith("Body without newline\n\nbegin 644 attach.bin")
