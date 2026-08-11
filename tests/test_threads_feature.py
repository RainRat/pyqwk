import pytest
import sys
import json
import io
import logging
import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure the root directory is in sys.path so we can import pyqwk.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    ProcessingSettings,
    calculate_threads,
    show_threads,
)
from pyqwk.cli import main


def create_test_msg(msgnum, refnum, confnum=1, subject=None, text="Body", date="01-01-24", time="12:00", author="FromUser"):
    if subject is None:
        subject = f"Subject {msgnum}"
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate=date,
        msgtime=time,
        msgto="ToUser",
        msgfrom=author,
        msgsubject=subject,
        msgpassword="",
        refnum=refnum,
        numblocks=1,
        msgflag=" ",
        confnum=confnum,
        lognum=0,
        nettag=" ",
    )
    return ParsedMessage(
        text=text,
        msgnum=msgnum,
        refnum=refnum,
        confnum=confnum,
        header=header,
    )


def test_calculate_threads_metrics(tmp_path):
    # Setup messages:
    # Thread 1: Msg 1 (root, author Alice), Msg 2 (reply to 1, author Bob, date 01-02-24)
    # Thread 3: Msg 3 (root, author Charlie)
    m1 = create_test_msg(1, 0, subject="Thread Root 1", author="Alice", date="01-01-24")
    m2 = create_test_msg(2, 1, subject="Re: Thread Root 1", author="Bob", date="01-02-24")
    m3 = create_test_msg(3, 0, subject="Thread Root 3", author="Charlie", date="01-03-24")

    archive = tmp_path / "archive_threads.json"
    data = [
        {"header": m.header.as_dict, "text": m.text, "confnum": m.confnum}
        for m in [m1, m2, m3]
    ]
    archive.write_text(json.dumps(data))

    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=True,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )

    logger = logging.getLogger("test_threads")
    threads = calculate_threads([str(archive)], settings, logger)

    # We expect 2 threads sorted by last activity (descending by default)
    # Since Msg 3 was last active on 01-03-24, and Thread 1 on 01-02-24, Thread 3 is first!
    assert len(threads) == 2

    # Thread 3
    assert threads[0]["thread_id"] == "3"
    assert threads[0]["subject"] == "Thread Root 3"
    assert threads[0]["starter"] == "Charlie"
    assert threads[0]["reply_count"] == 0
    assert threads[0]["deepest_depth"] == 0

    # Thread 1
    assert threads[1]["thread_id"] == "1"
    assert threads[1]["subject"] == "Thread Root 1"
    assert threads[1]["starter"] == "Alice"
    assert threads[1]["reply_count"] == 1
    assert threads[1]["deepest_depth"] == 1
    assert "01-02-24 12:00" in threads[1]["last_activity"]


def test_calculate_threads_sorting(tmp_path):
    m1 = create_test_msg(1, 0, subject="Banana Thread", author="Zack", date="01-01-24")
    m2 = create_test_msg(2, 0, subject="Apple Thread", author="Abby", date="01-02-24")

    archive = tmp_path / "archive_sort.json"
    data = [
        {"header": m.header.as_dict, "text": m.text, "confnum": m.confnum}
        for m in [m1, m2]
    ]
    archive.write_text(json.dumps(data))

    logger = logging.getLogger("test_threads_sort")

    # Sort by subject
    settings_subj = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=True, binaries_removal=False, redact_pii=False,
        format="text", separator="none", output_mode="stdout", output_path=None, encoding="cp437",
        sort="subject", quiet=True,
    )
    threads = calculate_threads([str(archive)], settings_subj, logger)
    # Apple Thread before Banana Thread
    assert threads[0]["subject"] == "Apple Thread"
    assert threads[1]["subject"] == "Banana Thread"

    # Sort by starter (author)
    settings_author = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=True, binaries_removal=False, redact_pii=False,
        format="text", separator="none", output_mode="stdout", output_path=None, encoding="cp437",
        sort="author", quiet=True,
    )
    threads = calculate_threads([str(archive)], settings_author, logger)
    # Abby before Zack
    assert threads[0]["starter"] == "Abby"
    assert threads[1]["starter"] == "Zack"


def test_calculate_threads_filters(tmp_path):
    m1 = create_test_msg(1, 0)
    m2 = create_test_msg(2, 1)
    m3 = create_test_msg(3, 0)

    archive = tmp_path / "archive_filters.json"
    data = [
        {"header": m.header.as_dict, "text": m.text, "confnum": m.confnum}
        for m in [m1, m2, m3]
    ]
    archive.write_text(json.dumps(data))

    logger = logging.getLogger("test_threads_filters")

    # Filter by thread_id_filters = {3}
    settings_id = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=True, binaries_removal=False, redact_pii=False,
        format="text", separator="none", output_mode="stdout", output_path=None, encoding="cp437",
        thread_id_filters={3}, quiet=True,
    )
    threads = calculate_threads([str(archive)], settings_id, logger)
    assert len(threads) == 1
    assert threads[0]["thread_id"] == "3"

    # Filter by min_replies = 1
    settings_min_replies = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=True, binaries_removal=False, redact_pii=False,
        format="text", separator="none", output_mode="stdout", output_path=None, encoding="cp437",
        min_replies=1, quiet=True,
    )
    threads = calculate_threads([str(archive)], settings_min_replies, logger)
    assert len(threads) == 1
    assert threads[0]["thread_id"] == "1"


def test_show_threads_serialization(tmp_path):
    m1 = create_test_msg(1, 0, subject="Root Subject", author="Alice")
    m2 = create_test_msg(2, 1, subject="Re: Root Subject", author="Bob")

    archive = tmp_path / "archive_serialize.json"
    data = [
        {"header": m.header.as_dict, "text": m.text, "confnum": m.confnum}
        for m in [m1, m2]
    ]
    archive.write_text(json.dumps(data))

    logger = logging.getLogger("test_threads_serialization")

    # Test JSON Format
    out_json = tmp_path / "out.json"
    settings_json = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=True, binaries_removal=False, redact_pii=False,
        format="json", separator="none", output_mode="file", output_path=str(out_json), encoding="cp437",
        quiet=True,
    )
    show_threads([str(archive)], settings_json, logger)
    result = json.loads(out_json.read_text(encoding="utf-8"))
    assert len(result) == 1
    assert result[0]["thread_id"] == "1"
    assert result[0]["reply_count"] == 1

    # Test CSV Format
    out_csv = tmp_path / "out.csv"
    settings_csv = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=True, binaries_removal=False, redact_pii=False,
        format="csv", separator="none", output_mode="file", output_path=str(out_csv), encoding="cp437",
        quiet=True,
    )
    show_threads([str(archive)], settings_csv, logger)
    csv_out = out_csv.read_text(encoding="utf-8")
    assert "thread_id,subject,starter,reply_count,deepest_depth,last_activity" in csv_out
    assert "1,Root Subject,Alice,1,1" in csv_out

    # Test Markdown Format
    out_md = tmp_path / "out.md"
    settings_md = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=True, binaries_removal=False, redact_pii=False,
        format="markdown", separator="none", output_mode="file", output_path=str(out_md), encoding="cp437",
        quiet=True,
    )
    show_threads([str(archive)], settings_md, logger)
    md_out = out_md.read_text(encoding="utf-8")
    assert "# Conversation Threads" in md_out
    assert "| 1 | Root Subject | Alice | 1 | 1 |" in md_out

    # Test HTML Format
    out_html = tmp_path / "out.html"
    settings_html = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=True, binaries_removal=False, redact_pii=False,
        format="html", separator="none", output_mode="file", output_path=str(out_html), encoding="cp437",
        quiet=True,
    )
    show_threads([str(archive)], settings_html, logger)
    html_out = out_html.read_text(encoding="utf-8")
    assert "<title>Conversation Threads</title>" in html_out
    assert "Root Subject" in html_out
    assert "Alice" in html_out

    # Test Plain Text (no colors) via logs/stdout
    settings_text = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=True, binaries_removal=False, redact_pii=False,
        format="text", separator="none", output_mode="stdout", output_path=None, encoding="cp437",
        quiet=True,
    )
    with patch.object(logger, "info") as mock_info:
        show_threads([str(archive)], settings_text, logger)
        log_lines = [call[0][0] for call in mock_info.call_args_list]
        text_out = "\n".join(log_lines)
        assert "Thread ID" in text_out
        assert "Root Subject" in text_out


def test_cli_threads_integration():
    test_args = ["qwk.py", "dummy.qwk", "--threads", "--dry-run"]
    with patch("sys.argv", test_args), patch("pyqwk.cli.expand_paths", return_value=["dummy.qwk"]), patch("pyqwk.cli.show_threads") as mock_show_threads:
        try:
            main()
        except SystemExit as e:
            assert e.code == 0
        mock_show_threads.assert_called_once()
