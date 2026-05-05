import logging
import os
import sqlite3
import io
import xml.etree.ElementTree as ET
import pytest
from pyqwk.core import (
    LogFormatter,
    _parse_sqlite_messages,
    _parse_xml_messages,
    _reconstruct_archive_information,
    _message_from_email,
    load_data,
    _serialize_rfc822,
    calculate_archive_stats,
    _write_text,
    _write_sqlite,
    _parse_qwk_date,
    process_merged_files,
    matches_filters,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
)


@pytest.fixture
def logger():
    logger = logging.getLogger("pyqwk.tests")
    logger.addHandler(logging.NullHandler())
    return logger


def test_log_formatter_no_colors():
    formatter = LogFormatter(use_colors=False)
    # Test all log levels
    levels = [
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
    ]
    for level in levels:
        record = logging.LogRecord("test", level, "path", 1, "message", (), None)
        output = formatter.format(record)
        if level == logging.INFO:
            assert output == "message"
        else:
            levelname = logging.getLevelName(level)
            assert output == f"{levelname}: message"
        assert "\x1b[" not in output


def test_parse_sqlite_missing_file(tmp_path):
    db_path = tmp_path / "nonexistent.db"
    with pytest.raises(sqlite3.OperationalError):
        _parse_sqlite_messages(str(db_path))


def test_parse_sqlite_reconstruction(tmp_path):
    db_path = tmp_path / "reconstruct.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE messages (conference_number INT, message_number INT, date TEXT, author TEXT, recipient TEXT, subject TEXT, status TEXT, text TEXT, reference_number INT, depth INT, thread_id TEXT, parent_message_number INT, conference_name TEXT, bbs_name TEXT, bbs_id TEXT, source_file TEXT, attachments TEXT)"
    )
    conn.execute(
        "INSERT INTO messages (conference_number, message_number, date, author, recipient, subject, status, text, bbs_name, conference_name, attachments, depth, thread_id, parent_message_number, source_file, bbs_id) VALUES (1, 1, '2024-01-01', 'Me', 'You', 'Sub', ' ', 'Text', 'Test BBS', 'General', '', 0, '', NULL, 'test.qwk', 'TESTID')"
    )
    conn.execute("CREATE TABLE conferences (number INT, name TEXT)")  # Exist but empty
    conn.commit()
    conn.close()

    messages, board_dict = _parse_sqlite_messages(str(db_path))
    assert board_dict[1] == "General"
    assert board_dict.bbs_info.name == "Test BBS"
    assert board_dict.bbs_info.bbs_id == "TESTID"


def test_parse_sqlite_merge_bbs_info(tmp_path):
    db_path = tmp_path / "merge_bbs.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE messages (conference_number INT, message_number INT, date TEXT, author TEXT, recipient TEXT, subject TEXT, status TEXT, text TEXT, reference_number INT, depth INT, thread_id TEXT, parent_message_number INT, conference_name TEXT, bbs_name TEXT, bbs_id TEXT, source_file TEXT, attachments TEXT)"
    )
    conn.execute(
        "INSERT INTO messages (conference_number, message_number, date, author, recipient, subject, status, text, bbs_name, attachments, depth, thread_id, parent_message_number, source_file) VALUES (1, 1, '2024-01-01', 'Me', 'You', 'Sub', ' ', 'Text', 'From Messages', '', 0, '', NULL, 'test.qwk')"
    )
    conn.execute("CREATE TABLE bbs_info (location TEXT, name TEXT)")
    conn.execute("INSERT INTO bbs_info (location, name) VALUES ('From Table', '')")
    conn.execute("CREATE TABLE conferences (number INT, name TEXT)")  # Empty
    conn.commit()
    conn.close()

    messages, board_dict = _parse_sqlite_messages(str(db_path))
    assert board_dict.bbs_info.location == "From Table"
    assert board_dict.bbs_info.name == "From Messages"


def test_parse_xml_single_message_root():
    root = ET.fromstring(
        "<message><header><msgfrom>Me</msgfrom><confnum>1</confnum></header><text>Hi</text></message>"
    )
    messages = _parse_xml_messages(root)
    assert len(messages) == 1
    assert messages[0].header.msgfrom == "Me"


def test_parse_xml_missing_header_and_unknown_tags():
    xml = """
    <messages>
        <message>
            <header>
                <unknown>Tag</unknown>
                <msgfrom>Sender</msgfrom>
                <confnum>2</confnum>
            </header>
            <text>Content</text>
        </message>
        <message>
            <text>No header</text>
        </message>
    </messages>
    """
    root = ET.fromstring(xml)
    messages = _parse_xml_messages(root)
    assert len(messages) == 2
    assert messages[0].header.msgfrom == "Sender"
    assert messages[1].header.msgfrom == ""


def test_reconstruct_archive_information_none_confnum():
    header = MessageHeader(" ", None, "", "", "", "", "", "", None, None, "", 1, 0, "")
    msg = ParsedMessage("Text", None, None, None, header)
    msg.confnum = None
    board_dict = _reconstruct_archive_information([msg])
    assert board_dict == {}


def test_message_from_email_empty_payload(mocker):
    msg_obj = mocker.Mock()
    msg_obj.is_multipart.return_value = True
    part = mocker.Mock()
    part.get_content_type.return_value = "text/plain"
    part.get_payload.return_value = None
    msg_obj.walk.return_value = [part]
    msg_obj.get.return_value = None
    parsed = _message_from_email(msg_obj)
    assert parsed.text == ""

    msg_obj = mocker.Mock()
    msg_obj.is_multipart.return_value = False
    msg_obj.get_payload.return_value = None
    msg_obj.get.return_value = None
    parsed = _message_from_email(msg_obj)
    assert parsed.text == ""


def test_load_data_messages_dat_current_dir(tmp_path, logger):
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with open("messages.dat", "wb") as f:
            f.write(b" " * 128)
        with open("control.dat", "wb") as f:
            f.write(
                b"BBS Name\nLoc\nPhone\nSysop\nSN,ID\nDate\nUser\n\n\n\n0\n0\nConf\n"
            )
        data, board_dict = load_data("messages.dat", logger)
        assert board_dict.bbs_info.name == "BBS Name"
    finally:
        os.chdir(old_cwd)


def test_load_data_messages_dat_case_insensitive_control(tmp_path, logger):
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with open("messages.dat", "wb") as f:
            f.write(b" " * 128)
        with open("CONTROL.DAT", "wb") as f:  # Uppercase
            f.write(
                b"BBS Name\nLoc\nPhone\nSysop\nSN,ID\nDate\nUser\n\n\n\n0\n0\nConf\n"
            )
        data, board_dict = load_data("messages.dat", logger)
        assert board_dict.bbs_info.name == "BBS Name"
    finally:
        os.chdir(old_cwd)


def test_rfc822_mbox_no_at_in_from():
    header = MessageHeader(
        " ",
        1,
        "01-01-70",
        "00:00",
        "To",
        "Author Name",
        "Sub",
        "",
        None,
        None,
        "",
        1,
        0,
        "",
    )
    msg = ParsedMessage("Body", 1, None, 1, header)
    output = _serialize_rfc822(msg, include_mbox_header=True)
    assert "From Author.Name@example.com" in output


def test_calculate_stats_limit(tmp_path, logger):
    import json
    from pyqwk.core import _message_to_dict

    def make_msg(i):
        header = MessageHeader(
            " ",
            i,
            "01-01-70",
            "00:00",
            "To",
            "From",
            f"Sub {i}",
            "",
            None,
            None,
            "",
            1,
            0,
            "",
        )
        return ParsedMessage(f"Body {i}", i, None, 1, header)

    messages = [make_msg(1), make_msg(2), make_msg(3)]
    json_path = tmp_path / "test.json"
    with open(json_path, "w") as f:
        json.dump([_message_to_dict(m) for m in messages], f)
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
        format="json",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="latin1",
        limit=2,
        quiet=True,
    )
    stats = calculate_archive_stats([str(json_path)], settings, logger)
    assert stats["matching_messages"] == 2


def test_write_text_oneline_no_colors(capsys):
    import sys

    header = MessageHeader(
        " ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, ""
    )
    msg = ParsedMessage("Body", 1, None, 1, header, confname="Conf")
    settings = ProcessingSettings(
        verbose=True,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="latin1",
        oneline=True,
        quiet=True,
    )
    original_isatty = sys.stdout.isatty
    sys.stdout.isatty = lambda: False
    try:
        _write_text([msg], None, "latin1", settings)
    finally:
        sys.stdout.isatty = original_isatty
    captured = capsys.readouterr()
    assert (
        "Num    Conference   Date           From            To              Subject"
        in captured.out
    )
    assert "\x1b[" not in captured.out


def test_write_sqlite_no_path():
    with pytest.raises(ValueError, match="Output path is required"):
        _write_sqlite([], None)


def test_parse_qwk_date_iso():
    iso_date = "2024-05-20T12:34:56"
    dt = _parse_qwk_date(iso_date, "")
    assert dt.year == 2024
    assert dt.month == 5
    assert dt.day == 20
    assert dt.hour == 12


def test_markdown_import_bracket_attachments(tmp_path, logger):
    md_content = """## Subject
- **Date:** 01-01-24 12:00
- **From:** Me
- **To:** You
- **Conference:** General (1)
- **Attachments:** [file1.zip], [file2.txt]

Body text
"""
    md_path = tmp_path / "test.md"
    md_path.write_text(md_content, encoding="utf-8")
    messages, _ = load_data(str(md_path), logger)
    assert messages[0].attachments == ["file1.zip", "file2.txt"]


def test_markdown_import_extra_hr(tmp_path, logger):
    md_content = """## Msg 1
Content 1
---
Not a new message
---
## Msg 2
Content 2
"""
    md_path = tmp_path / "test.md"
    md_path.write_text(md_content, encoding="utf-8")
    messages, _ = load_data(str(md_path), logger)
    assert len(messages) == 2
    assert "Not a new message" in messages[0].text


def test_process_merged_files_leading_newlines(tmp_path, logger):
    header = MessageHeader(
        " ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, ""
    )
    msg = ParsedMessage("\r\n\r\nBody", 1, None, 1, header)
    json_path = tmp_path / "leading.json"
    import json
    from pyqwk.core import _message_to_dict

    with open(json_path, "w") as f:
        json.dump([_message_to_dict(msg)], f)
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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="latin1",
        quiet=True,
    )
    import sys

    original_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        process_merged_files([str(json_path)], settings, logger)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = original_stdout
    assert output.count("\r\n") >= 2


def test_matches_filters_bbs_id_only(logger):
    header = MessageHeader(
        " ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, ""
    )
    msg = ParsedMessage("Body", 1, None, 1, header, bbs_name="Other", bbs_id="TargetID")
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
        format="text",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="latin1",
        quiet=True,
        bbs_names=["TargetID"],
    )
    assert matches_filters(msg, settings, set()) == True


def test_matches_filters_bbs_no_match(logger):
    header = MessageHeader(
        " ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, ""
    )
    msg = ParsedMessage("Body", 1, None, 1, header, bbs_name="Other", bbs_id="OtherID")
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
        format="text",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="latin1",
        quiet=True,
        bbs_names=["TargetID"],
    )
    assert matches_filters(msg, settings, set()) == False


def test_markdown_import_no_messages(tmp_path, logger):
    md_path = tmp_path / "empty.md"
    md_path.write_text("# Just a title\nNo messages here.", encoding="utf-8")
    messages, _ = load_data(str(md_path), logger)
    assert len(messages) == 0
