import os
import shutil
import tempfile
import logging
import pytest
from pyqwk.core import (
    load_data,
    write_messages,
    ProcessingSettings,
    MessageHeader,
    ParsedMessage,
    BBSInfo,
    parse_messages,
    _serialize_control_dat,
    _write_qwk,
    process_message,
)


def test_qwk_export_symmetry():
    # Setup
    tmpdir = tempfile.mkdtemp()
    try:
        qwk_path = os.path.join(tmpdir, "test.qwk")
        logger = logging.getLogger("test")

        # 1. Create dummy messages
        header1 = MessageHeader(
            status=" ",
            msgnum=1,
            msgdate="01-01-23",
            msgtime="12:00",
            msgto="Alice",
            msgfrom="Bob",
            msgsubject="Hello Symmetry",
            msgpassword="",
            refnum=0,
            numblocks=0,
            msgflag=" ",
            confnum=1,
            lognum=0,
            nettag="",
        )
        msg1 = ParsedMessage(
            text="This is a test message for symmetry.\r\nLine 2.",
            msgnum=1,
            refnum=0,
            confnum=1,
            header=header1,
        )

        messages = [msg1]
        bbs_info = BBSInfo(name="Test BBS", bbs_id="TESTBBS")
        board_dict = {1: "General"}

        settings = ProcessingSettings(
            verbose=False,
            private=True,
            no_header=False,
            truncate_signatures=False,
            cut_quoting=False,
            individual_files=False,
            threaded=False,
            binaries_removal=False,
            redact_pii=False,
            format="qwk",
            separator="none",
            output_mode="file",
            output_path=qwk_path,
            encoding="cp437",
        )

        # 2. Export to QWK
        write_messages(messages, qwk_path, settings, bbs_info, board_dict)
        assert os.path.exists(qwk_path)

        # 3. Re-import from QWK
        imported_data, imported_board = load_data(qwk_path, logger)
        assert imported_board[1] == "General"
        assert imported_board.bbs_info.name == "Test BBS"

        imported_messages = list(parse_messages(imported_data, None))
        assert len(imported_messages) == 1
        imp_msg = imported_messages[0]

        assert imp_msg.header.msgfrom.strip() == "Bob"
        assert imp_msg.header.msgto.strip() == "Alice"
        assert imp_msg.header.msgsubject.strip() == "Hello Symmetry"

        cleaned_text = process_message(imp_msg.text, False, False, False, False)
        assert "This is a test message for symmetry." in cleaned_text
        assert "Line 2." in cleaned_text

    finally:
        shutil.rmtree(tmpdir)


def test_rep_export_symmetry():
    # Setup
    tmpdir = tempfile.mkdtemp()
    try:
        rep_path = os.path.join(tmpdir, "test.rep")
        logger = logging.getLogger("test")

        header1 = MessageHeader(
            status=" ",
            msgnum=None,
            msgdate="01-01-23",
            msgtime="12:00",
            msgto="Sysop",
            msgfrom="User",
            msgsubject="Reply Test",
            msgpassword="",
            refnum=1,
            numblocks=0,
            msgflag=" ",
            confnum=1,
            lognum=0,
            nettag="",
        )
        msg1 = ParsedMessage(
            text="Reply content.", msgnum=None, refnum=1, confnum=1, header=header1
        )

        settings = ProcessingSettings(
            verbose=False,
            private=True,
            no_header=False,
            truncate_signatures=False,
            cut_quoting=False,
            individual_files=False,
            threaded=False,
            binaries_removal=False,
            redact_pii=False,
            format="rep",
            separator="none",
            output_mode="file",
            output_path=rep_path,
            encoding="cp437",
        )

        write_messages(
            [msg1], rep_path, settings, BBSInfo(bbs_id="TESTBBS"), {1: "General"}
        )

        imported_data, _ = load_data(rep_path, logger)
        imported_messages = list(parse_messages(imported_data, None))

        assert len(imported_messages) == 1
        assert imported_messages[0].header.msgsubject.strip() == "Reply Test"
        assert imported_messages[0].header.refnum == 1
    finally:
        shutil.rmtree(tmpdir)


def test_control_dat_no_bbs_info():
    # Coverage for board_dict is None/empty
    lines = _serialize_control_dat(None, None)
    assert lines[10] == b"-1"


def test_write_qwk_no_output_path():
    # Coverage for output_path is None
    with pytest.raises(ValueError, match="Output path is required"):
        _write_qwk([], None)
