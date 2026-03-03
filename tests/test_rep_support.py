import struct
import zipfile
import os
import logging
from pathlib import Path
import pytest
from pyqwk.core import load_data, parse_messages, ProcessingSettings, process_file

def create_rep_packet(path, bbs_id=b"TESTBBS", msg_count=1):
    # Header record
    header_rec = bbs_id.ljust(128, b" ")

    data = header_rec

    for i in range(msg_count):
        # Message header
        msg_header = struct.pack('<c7s8s5s25s25s25s12s8s6scHHc',
            b' ',
            str(i+1).encode().ljust(7, b' '),
            b'01-01-24',
            b'12:00',
            b'RECIPIENT'.ljust(25, b' '),
            b'SENDER'.ljust(25, b' '),
            f'SUBJECT {i+1}'.encode().ljust(25, b' '),
            b''.ljust(12, b' '),
            b'0'.ljust(8, b' '),
            b'2'.ljust(6, b' '),
            b' ',
            1,
            0,
            b' '
        )
        data += msg_header

        # Body block (2 blocks total, so 1 header + 1 body)
        msg_body = f"This is message {i+1}.".encode('cp437') + b"\xe3"
        msg_body = msg_body.ljust(128, b" ")
        data += msg_body

    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('REPLY.DAT', data)

def test_load_rep_packet(tmp_path, caplog):
    rep_path = tmp_path / "test.rep"
    create_rep_packet(rep_path)

    logger = logging.getLogger("pyqwk.test")
    with caplog.at_level(logging.DEBUG):
        file_data, board_dict = load_data(str(rep_path), logger)

    assert len(file_data) == 128 * 3 # Header + 1 msg header + 1 body
    assert board_dict == {}

    messages = list(parse_messages(file_data, None))
    assert len(messages) == 1
    assert messages[0].header.msgfrom.strip() == "SENDER"
    assert messages[0].text.strip() == "This is message 1."

def test_process_rep_file(tmp_path, capsys):
    rep_path = tmp_path / "test.rep"
    create_rep_packet(rep_path, msg_count=2)

    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True
    )

    logger = logging.getLogger("pyqwk.test")
    process_file(str(rep_path), settings, logger)

    captured = capsys.readouterr()
    assert "This is message 1." in captured.out
    assert "This is message 2." in captured.out

def test_rep_with_lowercase_filename(tmp_path):
    rep_path = tmp_path / "lowercase.rep"
    header_rec = b"BBSID".ljust(128, b" ")
    with zipfile.ZipFile(rep_path, 'w') as z:
        z.writestr('reply.dat', header_rec)

    logger = logging.getLogger("pyqwk.test")
    file_data, _ = load_data(str(rep_path), logger)
    assert len(file_data) == 128
