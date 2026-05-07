import pytest
from pyqwk.core import _parse_text_messages, load_data
import logging


def test_parse_text_messages_latin1_fallback(tmp_path):
    # Create a file with Latin-1 specific characters that are invalid in UTF-8
    # 0xA9 is the copyright symbol in Latin-1
    content = b"From: Alice\nTo: Bob\nSubject: Hello \xa9\n\nBody content"
    txt_file = tmp_path / "latin1.txt"
    txt_file.write_bytes(content)

    messages = _parse_text_messages(str(txt_file))
    assert len(messages) == 1
    assert "Alice" in messages[0].header.msgfrom
    assert "\xa9" in messages[0].header.msgsubject


def test_parse_text_messages_empty_section(tmp_path):
    # Multiple separators with whitespace should trigger 'if not section: continue' (1427)
    content = "From: A\nTo: B\nSubject: S\n\nBody\n\n------------------------------\n   \n------------------------------\nFrom: C\nTo: D\nSubject: T\n\nBody 2"
    txt_file = tmp_path / "empty_section.txt"
    txt_file.write_text(content)

    messages = _parse_text_messages(str(txt_file))
    assert len(messages) == 2


def test_parse_text_messages_invalid_section(tmp_path):
    # Section with missing mandatory headers (From, To, Subject) (1435)
    content = (
        "From: Alice\nTo: Bob\nSubject: S1\n\nBody 1\n"
        "------------------------------\n"
        "Invalid Section lacking headers\n"
        "------------------------------\n"
        "From: Charlie\nTo: Delta\nSubject: S2\n\nBody 2"
    )
    txt_file = tmp_path / "invalid.txt"
    txt_file.write_text(content)

    messages = _parse_text_messages(str(txt_file))
    # Should skip the middle section
    assert len(messages) == 2
    assert messages[0].header.msgfrom == "Alice"
    assert messages[1].header.msgfrom == "Charlie"


def test_parse_text_messages_extra_headers(tmp_path):
    # Test Message # (1448), Reference # (1468), and Attachments (1473)
    content = (
        "Conference: General (1)\n"
        "BBS: MyBBS\n"
        "Status: [PRIVATE]\n"
        "Message #: 123\n"
        "Date: 01-01-24 12:00\n"
        "From: Alice\n"
        "To: Bob\n"
        "Subject: Topic\n"
        "Reference #: 456\n"
        "Attachments: file1.zip, file2.txt\n"
        "\n"
        "Body content"
    )
    txt_file = tmp_path / "extra.txt"
    txt_file.write_text(content)

    messages = _parse_text_messages(str(txt_file))
    assert len(messages) == 1
    msg = messages[0]
    assert msg.msgnum == 123
    assert msg.refnum == 456
    assert msg.attachments == ["file1.zip", "file2.txt"]
    assert msg.confnum == 1
    assert msg.confname == "General"
    assert msg.bbs_name == "MyBBS"
    assert msg.header.is_private


def test_load_data_text_error_wrapping(tmp_path):
    # To trigger an exception in _parse_text_messages, we can pass a directory path
    # as the file path, which will cause 'open()' to raise an IsADirectoryError. (1797-1798)

    dir_path = tmp_path / "test_dir.txt"
    dir_path.mkdir()

    logger = logging.getLogger("test")
    with pytest.raises(ValueError, match="Failed to load text archive"):
        load_data(str(dir_path), logger)


def test_parse_text_messages_date_std_match_logic(tmp_path):
    # Currently date_s_match is unreachable because date_v_match is more greedy.
    content = "From: A\nTo: B\nSubject: S\nDate: 01-01-2024 12:00\n\nBody"
    txt_file = tmp_path / "date.txt"
    txt_file.write_text(content)

    messages = _parse_text_messages(str(txt_file))
    assert len(messages) == 1
    assert messages[0].header.msgdate == "01-01-2024"
    assert messages[0].header.msgtime == "12:00"


def test_parse_text_messages_leading_empty_lines(tmp_path):
    content = "------------------------------\n\nFrom: Alice\nTo: Bob\nSubject: Hello\n\nBody content"
    txt_file = tmp_path / "leading_empty.txt"
    txt_file.write_text(content)

    messages = _parse_text_messages(str(txt_file))
    assert len(messages) == 1
    assert messages[0].header.msgfrom == "Alice"
    assert messages[0].text == "Body content"
