import logging
import pytest
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    load_data,
    _serialize_rfc822,
    _write_eml
)

@pytest.fixture
def logger():
    return logging.getLogger("pyqwk.tests")

def test_xml_empty_attachment_tag(tmp_path, logger):
    """Test XML import with an empty attachment tag (line 842-843)."""
    xml_content = """<messages>
    <message>
        <header>
            <msgnum>1</msgnum>
            <msgdate>01-01-24</msgdate>
            <msgtime>10:00</msgtime>
            <msgfrom>Alice</msgfrom>
            <msgto>Bob</msgto>
            <msgsubject>Test</msgsubject>
            <confnum>1</confnum>
        </header>
        <text>Hello</text>
        <attachments>
            <attachment></attachment>
            <attachment>real.txt</attachment>
        </attachments>
    </message>
</messages>"""
    xml_file = tmp_path / "test.xml"
    xml_file.write_text(xml_content)

    messages, board_dict = load_data(str(xml_file), logger)
    assert len(messages) == 1
    # The empty attachment tag should be ignored
    assert messages[0].attachments == ["real.txt"]

def test_eml_import_invalid_date(tmp_path, logger):
    """Test EML import with invalid date (line 945-950)."""
    eml_content = (
        "From: Alice\n"
        "To: Bob\n"
        "Subject: Hello\n"
        "Date: Invalid Date String\n"
        "\n"
        "Body content"
    )
    eml_file = tmp_path / "test.eml"
    eml_file.write_text(eml_content)

    messages, board_dict = load_data(str(eml_file), logger)
    assert messages[0].header.msgdate == "01-01-70"
    assert messages[0].header.msgtime == "00:00"

def test_eml_import_missing_date(tmp_path, logger):
    """Test EML import with missing date (line 948-950)."""
    eml_content = (
        "From: Alice\n"
        "To: Bob\n"
        "Subject: Hello\n"
        "\n"
        "Body content"
    )
    eml_file = tmp_path / "test.eml"
    eml_file.write_text(eml_content)

    messages, board_dict = load_data(str(eml_file), logger)
    assert messages[0].header.msgdate == "01-01-70"
    assert messages[0].header.msgtime == "00:00"

def test_eml_import_multipart(tmp_path, logger):
    """Test EML import with multipart payload (line 955-960)."""
    eml_content = (
        "From: Alice\n"
        "To: Bob\n"
        "Subject: Hello\n"
        "Date: Mon, 1 Jan 2024 10:00:00 +0000\n"
        "Content-Type: multipart/mixed; boundary=\"boundary\"\n"
        "\n"
        "--boundary\n"
        "Content-Type: text/plain\n"
        "\n"
        "Multipart body\n"
        "--boundary--"
    )
    eml_file = tmp_path / "test.eml"
    eml_file.write_text(eml_content)

    messages, board_dict = load_data(str(eml_file), logger)
    assert messages[0].text.strip() == "Multipart body"

def test_eml_import_non_multipart(tmp_path, logger):
    """Test EML import with non-multipart payload (line 962-964)."""
    eml_content = (
        "From: Alice\n"
        "To: Bob\n"
        "Subject: Hello\n"
        "Date: Mon, 1 Jan 2024 10:00:00 +0000\n"
        "\n"
        "Single part body"
    )
    eml_file = tmp_path / "test.eml"
    eml_file.write_text(eml_content)

    messages, board_dict = load_data(str(eml_file), logger)
    assert messages[0].text.strip() == "Single part body"

def test_eml_import_non_multipart_empty_payload(tmp_path, logger):
    """Test EML import with non-multipart empty payload (line 962-964)."""
    eml_content = (
        "From: Alice\n"
        "To: Bob\n"
        "Subject: Hello\n"
        "Date: Mon, 1 Jan 2024 10:00:00 +0000\n"
        "\n"
    )
    eml_file = tmp_path / "test.eml"
    eml_file.write_text(eml_content)

    messages, board_dict = load_data(str(eml_file), logger)
    assert messages[0].text.strip() == ""

def test_rfc822_extra_headers_serialization():
    """Test serialization of extra QWK headers (lines 2580-2586)."""
    header = MessageHeader(
        status='*',
        msgnum=123,
        msgdate='01-01-24',
        msgtime='12:00',
        msgto='Bob',
        msgfrom='Alice',
        msgsubject='Subject',
        msgpassword='',
        refnum=456,
        numblocks=1,
        msgflag='FLAGS',
        confnum=1,
        lognum=0,
        nettag=''
    )
    msg = ParsedMessage(
        text="Hello",
        msgnum=123,
        refnum=456,
        confnum=1,
        header=header,
        attachments=["file1.bin"],
        depth=1,
        thread_id="T1",
        parent_msgnum=100
    )

    serialized = _serialize_rfc822(msg)
    assert "X-QWK-Status: *" in serialized
    assert "X-QWK-Flags: FLAGS" in serialized
    assert "X-QWK-Reference: 456" in serialized
    assert "X-QWK-Attachments: file1.bin" in serialized
    assert "X-QWK-Depth: 1" in serialized
    assert "X-QWK-Thread-ID: T1" in serialized
    assert "X-QWK-Parent-Msgnum: 100" in serialized

def test_write_eml_aggregate(tmp_path):
    """Test aggregate EML output (line 2713)."""
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-24', msgtime='10:00',
        msgto='B', msgfrom='A', msgsubject='S', msgpassword='',
        refnum=0, numblocks=1, msgflag='', confnum=1, lognum=0, nettag=''
    )
    msg1 = ParsedMessage(text="Msg1", msgnum=1, refnum=0, confnum=1, header=header)
    msg2 = ParsedMessage(text="Msg2", msgnum=2, refnum=0, confnum=1, header=header)

    output_file = tmp_path / "out.eml"
    _write_eml([msg1, msg2], str(output_file))

    content = output_file.read_text()
    assert "Msg1" in content
    assert "Msg2" in content
    # Should be separated by double newlines (plus the one from join and the one from _serialize_rfc822)
    # Actually _write_eml uses "\n\n".join(parts)
    assert content.count("Subject: S") == 2
