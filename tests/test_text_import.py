import logging
from pyqwk.core import load_data


def test_text_import_standard(tmp_path):
    text_content = """Conference: General (1)
From: Alice
To: Bob
Subject: Hello
Date: 01-23-24 12:34

This is a test message.
"""
    path = tmp_path / "test.txt"
    path.write_text(text_content)

    logger = logging.getLogger("test")
    messages, board_dict = load_data(str(path), logger)

    assert len(messages) == 1
    msg = messages[0]
    assert msg.confnum == 1
    assert msg.confname == "General"
    assert msg.header.msgfrom == "Alice"
    assert msg.header.msgto == "Bob"
    assert msg.header.msgsubject == "Hello"
    assert msg.header.msgdate == "01-23-24"
    assert msg.header.msgtime == "12:34"
    assert msg.text.strip() == "This is a test message."
    assert board_dict[1] == "General"


def test_text_import_verbose(tmp_path):
    text_content = """--------------------------------------------------------------------------------
Conference:  General (1)
Status:      [PRIVATE]
Message #:   123                   Date: 01-23-24 12:34
From:        Alice
To:          Bob
Subject:     Hello
Reference #: 0

Body here.
"""
    path = tmp_path / "test_verbose.txt"
    path.write_text(text_content)

    logger = logging.getLogger("test")
    messages, board_dict = load_data(str(path), logger)

    assert len(messages) == 1
    msg = messages[0]
    assert msg.header.msgnum == 123
    assert msg.header.is_private is True
    assert msg.text.strip() == "Body here."


def test_text_import_multiple(tmp_path):
    text_content = """Conference: General (1)
From: Alice
To: Bob
Subject: Hello
Date: 01-23-24 12:34

Msg 1
--------------------------------------------------------------------------------
Conference: Tech (2)
From: Bob
To: Alice
Subject: Re: Hello
Date: 01-23-24 12:35

Msg 2
"""
    path = tmp_path / "test_multi.txt"
    path.write_text(text_content)

    logger = logging.getLogger("test")
    messages, board_dict = load_data(str(path), logger)

    assert len(messages) == 2
    assert messages[0].confnum == 1
    assert messages[0].text.strip() == "Msg 1"
    assert messages[1].confnum == 2
    assert messages[1].text.strip() == "Msg 2"
    assert board_dict[1] == "General"
    assert board_dict[2] == "Tech"


def test_text_import_double_newline_separator(tmp_path):
    # Test fallback to double newline splitting if no dashes present
    text_content = """Conference: General (1)
From: Alice
To: Bob
Subject: One
Date: 01-23-24 12:34

Body One

Conference: Tech (2)
From: Bob
To: Alice
Subject: Two
Date: 01-23-24 12:35

Body Two
"""
    path = tmp_path / "test_newline.txt"
    path.write_text(text_content)

    logger = logging.getLogger("test")
    messages, board_dict = load_data(str(path), logger)

    assert len(messages) == 2
    assert messages[0].header.msgsubject == "One"
    assert messages[1].header.msgsubject == "Two"


def test_text_import_with_bbs_name(tmp_path):
    text_content = """Conference: General (1)
BBS: My Cool BBS
From: Alice
To: Bob
Subject: Hello
Date: 01-23-24 12:34

Body
"""
    path = tmp_path / "test_bbs.txt"
    path.write_text(text_content)

    logger = logging.getLogger("test")
    messages, board_dict = load_data(str(path), logger)

    assert len(messages) == 1
    assert messages[0].bbs_name == "My Cool BBS"
    assert board_dict.bbs_info.name == "My Cool BBS"


def test_text_import_attachments(tmp_path):
    text_content = """Conference: General (1)
From: Alice
To: Bob
Subject: Hello
Date: 01-23-24 12:34
Attachments: file1.zip, file2.jpg

Body
"""
    path = tmp_path / "test_attach.txt"
    path.write_text(text_content)

    logger = logging.getLogger("test")
    messages, board_dict = load_data(str(path), logger)

    assert len(messages) == 1
    assert messages[0].attachments == ["file1.zip", "file2.jpg"]


def test_text_import_single_part_date(tmp_path):
    text_content = """Conference: General (1)
From: Alice
To: Bob
Subject: Hello
Date: 01-23-24

Body
"""
    path = tmp_path / "test_single_date.txt"
    path.write_text(text_content)

    logger = logging.getLogger("test")
    messages, board_dict = load_data(str(path), logger)

    assert len(messages) == 1
    assert messages[0].header.msgdate == "01-23-24"
    assert messages[0].header.msgtime == "00:00"


def test_text_import_whitespace_only_date(tmp_path):
    # Use non-breaking space (\xa0) which is not in [ \t] but is in split()
    text_content = "Conference: General (1)\nFrom: Alice\nTo: Bob\nSubject: Hello\nDate: \xa0\n\nBody"
    path = tmp_path / "test_whitespace_date.txt"
    path.write_text(text_content, encoding="utf-8")

    logger = logging.getLogger("test")
    messages, board_dict = load_data(str(path), logger, encoding="utf-8")

    assert len(messages) == 1
    assert messages[0].header.msgdate == "01-01-70"
    assert messages[0].header.msgtime == "00:00"
