import sys
import os
from pathlib import Path
import pytest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyqwk.core import _write_mbox, _serialize_message_mbox, ProcessedMessage, MessageHeader

@pytest.fixture
def sample_message():
    header = MessageHeader(
        status=' ',
        msgnum=123,
        msgdate='01-01-90',
        msgtime='12:34',
        msgto='Recipient',
        msgfrom='Sender Name',
        msgsubject='Hello World',
        msgpassword='',
        refnum=None,
        numblocks=1,
        msgflag=' ',
        confnum=1,
        lognum=0,
        nettag='',
    )
    return ProcessedMessage(
        text="This is the body.\r\nIt has two lines.",
        msgnum=123,
        refnum=None,
        confnum=1,
        header=header,
    )

def test_serialize_message_mbox_format(sample_message):
    # We patch datetime to return a consistent current time if the parsing fails or for the "From " line
    # But since we will implement date parsing, we expect it to parse 01-01-90 correctly.
    # 01-01-90 -> Jan 1, 1990 (or 2090?). Let's assume 1990 for now or whatever datetime defaults to.

    mbox_content = _serialize_message_mbox(sample_message)

    lines = mbox_content.splitlines()

    # Check "From " line
    assert lines[0].startswith("From ")
    # The current implementation replaces non-alphanumeric with dot
    # "Sender Name" -> "Sender.Name"
    assert "Sender.Name" in lines[0]

    # Check headers
    assert "From: Sender Name" in mbox_content
    assert "To: Recipient" in mbox_content
    assert "Subject: Hello World" in mbox_content
    assert "X-QWK-Conference: 1" in mbox_content
    assert "Message-ID:" in mbox_content

    # Check Body
    assert "This is the body." in mbox_content

def test_serialize_message_mbox_with_metadata(sample_message):
    sample_message.confname = "Main Board"
    sample_message.header.status = "*"
    sample_message.header.msgflag = " "

    mbox_content = _serialize_message_mbox(sample_message)

    assert "X-QWK-Conference-Name: Main Board" in mbox_content
    assert "X-QWK-Message-Number: 123" in mbox_content
    assert "X-QWK-Status: *" in mbox_content
    assert "Content-Type: text/plain; charset=utf-8" in mbox_content

def test_serialize_message_mbox_threading(sample_message):
    sample_message.parent_msgnum = 100
    mbox_content = _serialize_message_mbox(sample_message)

    assert "In-Reply-To: <1.100@qwk>" in mbox_content
    assert "References: <1.100@qwk>" in mbox_content

def test_write_mbox_multiple(tmp_path, sample_message):
    output_file = tmp_path / "output.mbox"

    msg2 = sample_message
    messages = [sample_message, msg2]

    _write_mbox(messages, str(output_file))

    content = output_file.read_text(encoding='utf-8')
    assert content.count("From ") >= 2
    assert content.count("Subject: Hello World") == 2

def test_mbox_body_quoting(sample_message):
    sample_message.text = "From the beginning...\r\nThis line starts with From usually."

    mbox_content = _serialize_message_mbox(sample_message)

    # "From " at start of line in body should be escaped
    assert "\n>From the beginning..." in mbox_content or "\r\n>From the beginning..." in mbox_content
