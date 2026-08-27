import os
import pytest
import logging
from pyqwk.core import (
    detect_extension,
    process_merged_files,
    show_list_bbs,
    show_list_authors,
    show_list_recipients,
    show_list_subjects,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
)


def test_detect_extension_markdown_without_dashes():
    # Header starts with '# ' but lacks '---'
    data = b"# Hello World\nThis is plain text without markdown dividers.\n"
    ext = detect_extension(data)
    assert ext == ".txt"


def test_process_merged_files_dry_run_archive_export(tmp_path):
    logger = logging.getLogger("test_dry_run")
    zip_path = str(tmp_path / "export.zip")

    # Create a dummy message file
    msg_file = tmp_path / "msg.json"
    msg_file.write_text(
        '[{"text": "Hello", "header": {"status": " ", "msgnum": 1, "msgdate": "01-01-24", "msgtime": "12:00", "msgto": "All", "msgfrom": "Alice", "msgsubject": "Test", "confnum": 1}}]',
        encoding="utf-8",
    )

    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="auto",
        output_mode="file",
        output_path=zip_path,
        encoding="utf-8",
        dry_run=True,
    )

    process_merged_files([str(msg_file)], settings, logger)
    # Since dry_run is True, the zip archive should not be packed to disk
    assert not os.path.exists(zip_path)


def test_list_reports_date_comparison_branches(tmp_path):
    logger = logging.getLogger("test_reports_branches")

    # Create two messages for the same BBS/Author/Recipient/Subject with out-of-order date
    # Msg 1: 05-10-20 (Sets first_dt = May 10 2020, last_dt = May 10 2020)
    # Msg 2: 05-15-20 (Sets last_dt = May 15 2020, first_dt stays May 10 2020)
    # Msg 3: 05-12-20 (msg_dt < first_dt is False, msg_dt > last_dt is False)
    msg_file = tmp_path / "messages.json"
    msg_file.write_text(
        '['
        '{"text": "M1", "bbs_name": "TestBBS", "header": {"status": " ", "msgnum": 1, "msgdate": "05-10-20", "msgtime": "12:00", "msgto": "Bob", "msgfrom": "Alice", "msgsubject": "Topic", "confnum": 1}},'
        '{"text": "M2", "bbs_name": "TestBBS", "header": {"status": " ", "msgnum": 2, "msgdate": "05-15-20", "msgtime": "12:00", "msgto": "Bob", "msgfrom": "Alice", "msgsubject": "Topic", "confnum": 1}},'
        '{"text": "M3", "bbs_name": "TestBBS", "header": {"status": " ", "msgnum": 3, "msgdate": "05-12-20", "msgtime": "12:00", "msgto": "Bob", "msgfrom": "Alice", "msgsubject": "Topic", "confnum": 1}}'
        ']',
        encoding="utf-8",
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
        format="text",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="utf-8",
    )

    show_list_bbs([str(msg_file)], settings, logger)
    show_list_authors([str(msg_file)], settings, logger)
    show_list_recipients([str(msg_file)], settings, logger)
    show_list_subjects([str(msg_file)], settings, logger)
