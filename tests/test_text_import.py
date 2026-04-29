import os
import shutil
import tempfile
import logging
from pyqwk.core import load_data, write_messages, ProcessingSettings, MessageHeader, ParsedMessage, BBSInfo
from dataclasses import replace

def test_text_import_symmetry():
    # Setup
    tmpdir = tempfile.mkdtemp()
    try:
        text_path = os.path.join(tmpdir, "test.txt")
        logger = logging.getLogger("test")

        # 1. Create a dummy message
        header1 = MessageHeader(
            status=" ",
            msgnum=123,
            msgdate="05-20-23",
            msgtime="14:30",
            msgto="Receiver",
            msgfrom="Sender",
            msgsubject="Text Import Test",
            msgpassword="",
            refnum=456,
            numblocks=0,
            msgflag=" ",
            confnum=7,
            lognum=0,
            nettag=""
        )
        msg1 = ParsedMessage(
            text="Hello from the plain text world.\nThis is a multi-line message.",
            msgnum=123,
            refnum=456,
            confnum=7,
            header=header1,
            confname="Development",
            bbs_name="The High Frontier",
            attachments=["file1.zip", "image.jpg"]
        )

        board_dict = {7: "Development"}

        # Prepare content with headers as pyqwk would export it
        # (This is what we are testing: re-importing pyqwk's own export)
        header_text = msg1.header.format_text(
            board_dict,
            verbose=True,
            include_separator=True,
            attachments=msg1.attachments,
            bbs_name=msg1.bbs_name,
        )
        content = header_text + msg1.text + "\n"

        with open(text_path, "w", encoding="utf-8") as f:
            f.write(content)

        # 2. Re-import from text
        imported_messages, imported_board = load_data(text_path, logger)

        assert len(imported_messages) == 1
        imp_msg = imported_messages[0]

        assert imp_msg.header.msgfrom.strip() == "Sender"
        assert imp_msg.header.msgto.strip() == "Receiver"
        assert imp_msg.header.msgsubject.strip() == "Text Import Test"
        assert imp_msg.header.msgdate == "05-20-23"
        # msgtime might have extra seconds if format_text adds them, but our current format_text is HH:MM
        assert imp_msg.header.msgtime == "14:30"
        assert imp_msg.header.msgnum == 123
        assert imp_msg.header.refnum == 456
        assert imp_msg.confnum == 7
        assert imp_msg.confname == "Development"
        assert imp_msg.bbs_name == "The High Frontier"
        assert "file1.zip" in imp_msg.attachments
        assert "image.jpg" in imp_msg.attachments
        assert "Hello from the plain text world." in imp_msg.text
        assert "This is a multi-line message." in imp_msg.text

    finally:
        shutil.rmtree(tmpdir)

def test_text_import_multi_message():
    # Setup
    tmpdir = tempfile.mkdtemp()
    try:
        text_path = os.path.join(tmpdir, "multi.txt")
        content = """
--------------------------------------------------------------------------------
Conference:     General
From:           Alice
To:             Bob
Subject:        First Message
Date:           01-01-23 10:00

Hello Bob!

--------------------------------------------------------------------------------
Conference:     Technical
From:           Bob
To:             Alice
Subject:        Second Message
Date:           01-01-23 11:00

Hi Alice, this is technical.
"""
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger = logging.getLogger("test")
        imported_messages, board = load_data(text_path, logger)

        assert len(imported_messages) == 2
        assert imported_messages[0].header.msgfrom == "Alice"
        assert imported_messages[0].confname == "General"
        assert imported_messages[0].text == "Hello Bob!"

        assert imported_messages[1].header.msgfrom == "Bob"
        assert imported_messages[1].confname == "Technical"
        assert imported_messages[1].text == "Hi Alice, this is technical."

    finally:
        shutil.rmtree(tmpdir)
