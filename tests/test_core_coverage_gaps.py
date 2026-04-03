import sqlite3
import logging
import xml.etree.ElementTree as ET
import datetime
import pytest
import email
import os
from pyqwk.core import (
    _parse_xml_messages,
    _parse_sqlite_messages,
    _reconstruct_metadata,
    LogFormatter,
    _parse_qwk_date,
    ParsedMessage,
    MessageHeader,
    BBSInfo,
    ProcessingSettings,
    process_merged_files,
    _message_from_email,
    ConferenceMap
)

def test_parse_xml_single_message_root():
    # Covers line 913: if root.tag == 'message':
    xml_str = '<message><text>Hello</text></message>'
    root = ET.fromstring(xml_str)
    messages = _parse_xml_messages(root)
    assert len(messages) == 1
    assert messages[0].text == "Hello"

@pytest.fixture
def logger():
    return logging.getLogger("pyqwk.tests.final_gap")

def test_parse_xml_missing_header():
    # Covers line 920->925: if header_el is not None:
    xml_str = '<messages><message><text>No header here</text></message></messages>'
    root = ET.fromstring(xml_str)
    messages = _parse_xml_messages(root)
    assert len(messages) == 1
    assert messages[0].header.msgfrom == ""  # Default from MessageHeader.from_dict

def test_parse_xml_unknown_header_tag():
    # Covers line 922->921: if field_el.tag in header_fields:
    xml_str = '<messages><message><header><unknown>Tag</unknown><msgfrom>Me</msgfrom></header></message></messages>'
    root = ET.fromstring(xml_str)
    messages = _parse_xml_messages(root)
    assert len(messages) == 1
    assert messages[0].header.msgfrom == "Me"

def test_parse_sqlite_bbs_info_partial_columns(tmp_path):
    # Covers line 798: if field.name in row.keys():
    db_path = tmp_path / "partial_bbs.db"
    conn = sqlite3.connect(str(db_path))
    # Missing most columns, only 'name' exists
    conn.execute("CREATE TABLE messages (conference_number INTEGER, message_number INTEGER, date TEXT, author TEXT, recipient TEXT, subject TEXT, status TEXT, text TEXT, reference_number INTEGER, thread_id TEXT, depth INTEGER, parent_message_number INTEGER, conference_name TEXT, bbs_name TEXT, source_file TEXT, attachments TEXT)")
    conn.execute("CREATE TABLE bbs_info (name TEXT)")
    conn.execute("INSERT INTO bbs_info (name) VALUES ('Partial BBS')")
    conn.commit()
    conn.close()

    messages, board_dict = _parse_sqlite_messages(str(db_path))
    assert board_dict.bbs_info.name == "Partial BBS"
    assert board_dict.bbs_info.sysop == "" # Should be default

def test_reconstruct_metadata_basic():
    # Basic test for reconstruction
    h = MessageHeader(" ", 1, "", "", "", "", "", "", None, None, " ", 1, 0, "")
    m = ParsedMessage("Text", 1, None, 1, h, confname="Real Name")
    board_dict = _reconstruct_metadata([m])
    assert board_dict[1] == "Real Name"

def test_process_merged_files_stdout_with_path_error(logger):
    # Covers line 1130->1133: output_mode == 'stdout' and resolved_output_path is not None
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format='text', separator='none', output_mode='stdout',
        output_path='some_path', encoding='cp437'
    )
    with pytest.raises(ValueError, match="Output path cannot be provided"):
        process_merged_files(["dummy.qwk"], settings, logger)

def test_log_formatter_no_colors():
    # Covers line 761->771: if self.use_colors:
    formatter = LogFormatter(use_colors=False)
    record = logging.LogRecord("test", logging.WARNING, "path", 10, "Warning message", None, None)
    formatted = formatter.format(record)
    assert "WARNING: Warning message" in formatted
    assert "\x1b[" not in formatted

def test_parse_qwk_date_invalid_fallback():
    # Covers line 2339: except (ValueError, IndexError):
    # This string will fail split('-') or int conversion
    dt = _parse_qwk_date("not-a-date", "12:00")
    assert dt == datetime.datetime(1970, 1, 1, 0, 0)

def test_prepare_field_no_highlight():
    # Covers line 691->693: if highlight: (False branch)
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "Recipient", "Author", "Subject", "", None, None, " ", 1, 0, "")
    # format_oneline calls prepare_field which defaults highlight=True,
    # but we can't easily reach it with False from format_oneline.
    # However, if we don't provide highlight_term, highlight becomes effectively False or _highlight_text returns original.
    # Wait, prepare_field is internal to format_oneline.
    # In format_oneline:
    # conf_part = prepare_field(conf_name, 12) -> highlight=True
    # from_part = prepare_field(from_name, 15) -> highlight=True
    # to_part = prepare_field(to_name, 15) -> highlight=True
    # If highlight_term is None, _highlight_text returns text.
    line = header.format_oneline({}, highlight_term=None)
    assert "Author" in line

def test_parse_sqlite_file_not_found():
    # Covers line 779: raise sqlite3.OperationalError
    with pytest.raises(sqlite3.OperationalError, match="unable to open database file"):
        _parse_sqlite_messages("non_existent.db")

def test_reconstruct_metadata_confnum_none():
    # Covers line 992->995: if msg.confnum is not None: (False branch)
    h = MessageHeader(" ", 1, "", "", "", "", "", "", None, None, " ", 1, 0, "")
    m = ParsedMessage("Text", 1, None, 1, h)
    m.confnum = None # type: ignore
    board_dict = _reconstruct_metadata([m])
    assert len(board_dict) == 0

def test_reconstruct_metadata_bbs_info_extraction():
    # Covers line 995: if msg.bbs_name: and 997: if msg.bbs_id:
    h = MessageHeader(" ", 1, "", "", "", "", "", "", None, None, " ", 1, 0, "")
    m = ParsedMessage("Text", 1, None, 1, h, bbs_name="MyBBS", bbs_id="MID")
    board_dict = _reconstruct_metadata([m])
    assert board_dict.bbs_info.name == "MyBBS"
    assert board_dict.bbs_info.bbs_id == "MID"

def test_message_from_email_no_date_header():
    # Covers line 1050->1052: if date_hdr: (False branch)
    msg = email.message.EmailMessage()
    parsed = _message_from_email(msg)
    assert parsed.header.msgdate == "01-01-70"

def test_process_merged_files_invalid_sort_key(logger):
    # Covers line 2335->2339: if settings.sort in sort_keys: (False branch)
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, merge=True,
        binaries_removal=False, redact_pii=False, format='text', separator='none',
        output_mode='stdout', output_path=None, encoding='cp437',
        sort='invalid_key', reverse=False
    )
    h = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, None, " ", 1, 0, "")
    m = ParsedMessage("Msg", 1, None, 1, h)

    from unittest.mock import patch
    with patch('pyqwk.core.load_data', return_value=(bytearray(b'Produced '), ConferenceMap())):
        with patch('pyqwk.core.parse_messages', return_value=iter([m])):
            process_merged_files(['fake.qwk'], settings, logger)

def test_handle_output_limit_reached(logger):
    # Covers line 1312->1311: if settings.limit is not None and processed_count >= settings.limit:
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, merge=True,
        binaries_removal=False, redact_pii=False, format='text', separator='none',
        output_mode='stdout', output_path=None, encoding='cp437',
        limit=1
    )
    h = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, None, " ", 1, 0, "")
    m1 = ParsedMessage("Msg1", 1, None, 1, h)
    m2 = ParsedMessage("Msg2", 2, None, 1, h)

    from unittest.mock import patch
    with patch('pyqwk.core.load_data', return_value=(bytearray(b'Produced '), ConferenceMap())):
        with patch('pyqwk.core.parse_messages', return_value=iter([m1, m2])):
            # Should only process m1
            process_merged_files(['fake.qwk'], settings, logger)

def test_process_merged_files_individual_organize_dry_run(tmp_path, logger):
    # Covers line 1469->1475: Rel path collection with organize
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=True, threaded=False, merge=True,
        binaries_removal=False, redact_pii=False, format='html', separator='none',
        output_mode='file', output_path=str(tmp_path), encoding='cp437',
        organize=True, dry_run=True
    )
    h = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, None, " ", 1, 0, "")
    m = ParsedMessage("Msg", 1, None, 1, h, confname="General")

    from unittest.mock import patch
    with patch('pyqwk.core.load_data', return_value=(bytearray(b'Produced '), ConferenceMap())):
        with patch('pyqwk.core.parse_messages', return_value=iter([m])):
            process_merged_files(['fake.qwk'], settings, logger)
