import os
import json
import logging
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from dataclasses import replace

from pyqwk.core import (
    process_multiple_files,
    process_file,
    show_info,
    show_stats,
    ProcessingSettings,
    PROCESSING_EXCEPTIONS,
    ParsedMessage,
    MessageHeader,
    process_merged_files,
    LogFormatter,
    _message_to_xml_element,
    parse_messages,
    _order_messages_by_thread
)

@pytest.fixture
def logger():
    logger = logging.getLogger("pyqwk.tests")
    logger.addHandler(logging.NullHandler())
    return logger

@pytest.fixture
def default_settings():
    return ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format='text',
        separator='auto',
        output_mode='stdout',
        output_path=None,
        encoding='cp437',
        quiet=True
    )

def test_process_multiple_files_formats(tmp_path, logger, default_settings):
    input_paths = ['testdata/test1_qwk.zip', 'testdata/test2_qwk.zip']
    formats = [
        ('json', '.json'),
        ('xml', '.xml'),
        ('html', '.html'),
        ('markdown', '.md'),
        ('csv', '.csv'),
        ('mbox', '.mbox'),
        ('text', '.txt')
    ]

    for fmt, ext in formats:
        output_dir = tmp_path / f"out_{fmt}"
        settings = replace(default_settings, format=fmt)

        # We need to make sure the output_dir exists as process_multiple_files calls os.makedirs
        # but for multiple files it's expected to be a folder.

        had_errors = process_multiple_files(input_paths, str(output_dir), settings, logger)

        assert not had_errors
        assert output_dir.exists()

        files = list(output_dir.iterdir())
        assert len(files) == 2
        for f in files:
            assert f.suffix == ext

def test_process_multiple_files_error_handling(tmp_path, logger, default_settings):
    input_paths = ['testdata/test1_qwk.zip']
    output_dir = tmp_path / "out_error"

    with patch('pyqwk.core.process_file') as mock_process:
        mock_process.side_effect = OSError("Mocked OS Error")

        with patch.object(logger, 'error') as mock_log_error:
            had_errors = process_multiple_files(input_paths, str(output_dir), default_settings, logger)

            assert had_errors
            mock_log_error.assert_called()
            assert "Error processing file" in mock_log_error.call_args[0][0]

def test_show_info_error_handling(logger, default_settings):
    with patch('pyqwk.core.load_data') as mock_load:
        mock_load.side_effect = Exception("Mocked Error")

        with patch.object(logger, 'error') as mock_log_error:
            show_info(['fake.zip'], default_settings, logger)

            mock_log_error.assert_called()
            assert "Error reading info" in mock_log_error.call_args[0][0]

def test_show_stats_error_handling(logger, default_settings):
    with patch('pyqwk.core.load_data') as mock_load:
        mock_load.side_effect = Exception("Mocked Error")

        with patch.object(logger, 'error') as mock_log_error:
            show_stats(['fake.zip'], default_settings, logger)

            mock_log_error.assert_called()
            assert "Error calculating stats" in mock_log_error.call_args[0][0]

def test_individual_files_csv(tmp_path, logger, default_settings):
    input_path = 'testdata/test1_qwk.zip'
    output_dir = tmp_path / "csv_individual"

    settings = replace(
        default_settings,
        individual_files=True,
        format='csv',
        output_mode='file',
        output_path=str(output_dir)
    )

    process_file(input_path, settings, logger)

    assert output_dir.exists()
    files = list(output_dir.iterdir())
    assert len(files) > 0
    # Current behavior: individual files have no extension and are named by hash
    assert files[0].name != ""

def test_individual_files_unique_text(tmp_path, logger, default_settings):
    output_path = tmp_path / "individual_unique"
    settings = replace(
        default_settings,
        individual_files=True,
        unique=True,
        format='text',
        output_mode='file',
        output_path=str(output_path)
    )

    # Create mock messages
    h1 = MagicMock(spec=MessageHeader)
    h1.is_private = False
    h1.is_password = False
    h1.msgnum = 1
    h1.confnum = 100
    h1.msgfrom = "User"
    h1.msgto = "All"
    h1.msgdate = "01-01-23"
    h1.msgtime = "12:00"
    h1.msgsubject = "Subj"
    h1.format_text.return_value = "Header\n"

    msg1 = ParsedMessage(text="Body1", msgnum=1, refnum=None, confnum=100, header=h1)

    with patch('pyqwk.core.load_data') as mock_load:
        mock_load.return_value = (bytearray(b'Produced '), {})
        with patch('pyqwk.core.parse_messages') as mock_parse:
            mock_parse.return_value = [msg1]

            process_merged_files(['archive.qwk'], settings, logger)

    assert output_path.exists()
    assert output_path.is_dir()
    files = list(output_path.iterdir())
    assert len(files) == 1
    # The filename should be a sha1 hash of the encoded buffer because it's in the unique block
    # and it uses hashlib.sha1(encoded_buffer).hexdigest()
    # Let's verify it contains the content
    with files[0].open('rb') as f:
        content = f.read()
        assert b"Body1" in content

def test_log_formatter():
    formatter = LogFormatter(use_colors=True)
    record = logging.LogRecord("test", logging.INFO, "path", 10, "Info message", None, None)
    assert formatter.format(record) == "Info message"

    record.levelno = logging.DEBUG
    assert "\033[" in formatter.format(record)

    record.levelno = logging.WARNING
    assert "\033[" in formatter.format(record)

    record.levelno = logging.ERROR
    assert "\033[" in formatter.format(record)

    record.levelno = logging.CRITICAL
    assert "\033[" in formatter.format(record)

def test_xml_serialization_with_parent():
    h = MagicMock(spec=MessageHeader)
    h.as_dict = {"from": "user"}
    msg = MagicMock()
    msg.header = h
    msg.depth = 1
    msg.thread_id = 123
    msg.parent_msgnum = 456
    msg.text = "Body"

    element = _message_to_xml_element(msg)
    import xml.etree.ElementTree as ET
    xml_str = ET.tostring(element).decode()
    assert "<depth>1</depth>" in xml_str
    assert "<thread_id>123</thread_id>" in xml_str
    assert "<parent_msgnum>456</parent_msgnum>" in xml_str

def test_parse_messages_progress_bar():
    data = bytearray(b'Produced '.ljust(128, b' '))
    # Add a valid header
    import struct
    header = struct.pack(
        '<c7s8s5s25s25s25s12s8s6scHHc',
        b' ', b"1".ljust(7, b' '), b"01-01-90", b"12:00",
        b"To".ljust(25, b' '), b"From".ljust(25, b' '), b"Subj".ljust(25, b' '),
        b"".ljust(12, b' '), b"0".ljust(8, b' '),
        b"0".ljust(6, b' '), # 0 body blocks
        b' ', 1, 1, b' '
    )
    data += header

    mock_pb = MagicMock()
    list(parse_messages(data, mock_pb))

    assert mock_pb.update.called

def test_order_messages_by_thread_empty():
    assert _order_messages_by_thread([]) == []

def test_individual_files_triple_collision(tmp_path, logger, default_settings):
    """Test collision handling when three messages would have the same filename."""
    output_dir = tmp_path / "triple_collision"
    output_dir.mkdir()

    def make_msg(text):
        h = MagicMock(spec=MessageHeader)
        h.is_private = False
        h.is_password = False
        h.msgnum = 1
        h.confnum = 1
        h.msgfrom = "User"
        h.msgto = "All"
        h.msgdate = "01-01-23"
        h.msgtime = "12:00"
        h.msgsubject = "Collision"
        h.format_text.return_value = ""
        return ParsedMessage(text=text, msgnum=1, refnum=None, confnum=1, header=h)

    # Three messages with identical content and metadata -> same base filename AND same hash
    msg1 = make_msg("Duplicate Body")
    msg2 = make_msg("Duplicate Body")
    msg3 = make_msg("Duplicate Body")

    settings = replace(
        default_settings,
        individual_files=True,
        format='text',
        output_mode='file',
        output_path=str(output_dir),
        no_header=True
    )

    with patch('pyqwk.core.load_data') as mock_load:
        mock_load.return_value = (bytearray(b'Produced '), {1: "General"})
        with patch('pyqwk.core.parse_messages') as mock_parse:
            mock_parse.return_value = [msg1, msg2, msg3]
            process_merged_files(['archive.qwk'], settings, logger)

    files = list(output_dir.iterdir())
    # If the logic is buggy (no loop), it will only have 2 files because the 3rd overwrote the 2nd
    # or failed to be unique.
    assert len(files) == 3, f"Expected 3 files, found {len(files)}: {[f.name for f in files]}"

def test_parse_control_dat_truncated(logger):
    """Test that CONTROL.DAT with fewer conference entries than specified is handled."""
    control_data = [
        b"BBS Name",
        b"Location",
        b"Phone",
        b"SysOp",
        b"Serial,ID",
        b"01-01-23",
        b"User",
        b"Menu",
        b"1",
        b"0",
        b"10"  # Says 10 conferences (+1 = 11), but we provide fewer
    ]
    # Add only 2 conference entries (4 lines)
    control_data += [b"1", b"Conf 1", b"2", b"Conf 2"]

    from pyqwk.core import _parse_control_dat
    with patch.object(logger, 'warning') as mock_warn:
        board_dict = _parse_control_dat(control_data, logger)

        assert len(board_dict) == 2
        assert board_dict[1] == "Conf 1"
        assert board_dict[2] == "Conf 2"
        mock_warn.assert_called()
        assert "CONTROL.DAT is truncated" in mock_warn.call_args[0][0]
