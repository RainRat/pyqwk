import pytest
import sys
import json
import io
import logging
from unittest.mock import patch, MagicMock
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    ProcessingSettings,
    matches_filters,
    process_merged_files,
    calculate_archive_stats,
    _order_messages_by_thread,
)
from pyqwk.cli import main


def create_test_msg(msgnum, refnum, confnum=1, subject=None, text="Body"):
    if subject is None:
        subject = f"Subject {msgnum}"
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="ToUser",
        msgfrom="FromUser",
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


def test_thread_id_matches_filters():
    # Setup matching messages
    m1 = create_test_msg(1, 0)
    m1.thread_id = "1"
    m2 = create_test_msg(2, 1)
    m2.thread_id = "1"
    m3 = create_test_msg(3, 0)
    m3.thread_id = "3"

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
        encoding="cp437",
        thread_id_filters={1},
    )

    allowed_confs = {1}

    # Matches thread_id "1"
    assert matches_filters(m1, settings, allowed_confs) is True
    assert matches_filters(m2, settings, allowed_confs) is True
    # Does not match thread_id "3"
    assert matches_filters(m3, settings, allowed_confs) is False

    # Message with None thread_id
    m4 = create_test_msg(4, 0)
    m4.thread_id = None
    assert matches_filters(m4, settings, allowed_confs) is False

    # Custom string thread_id matching fallback
    settings_custom = replace_thread_filters(settings, {999})
    m5 = create_test_msg(5, 0)
    m5.thread_id = "999"
    assert matches_filters(m5, settings_custom, allowed_confs) is True


def replace_thread_filters(settings, filters):
    from dataclasses import replace
    return replace(settings, thread_id_filters=filters)


def test_process_merged_files_with_thread_id_filter(tmp_path):
    # Create an archive with messages
    # Thread 1: 1 (root), 2 (reply), 3 (reply to 2)
    # Thread 4: 4 (root), 5 (reply)
    # Thread 6: 6 (root)
    m1 = create_test_msg(1, 0)
    m2 = create_test_msg(2, 1)
    m3 = create_test_msg(3, 2)
    m4 = create_test_msg(4, 0)
    m5 = create_test_msg(5, 4)
    m6 = create_test_msg(6, 0)

    archive = tmp_path / "archive.json"
    data = [
        {"header": m.header.as_dict, "text": m.text, "confnum": m.confnum}
        for m in [m1, m2, m3, m4, m5, m6]
    ]
    archive.write_text(json.dumps(data))

    logger = logging.getLogger("test_thread_id")

    # Limit to thread 4
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=True,
        binaries_removal=False,
        redact_pii=False,
        format="json",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        thread_id_filters={4},
        quiet=True,
    )

    with patch("sys.stdout", new=io.StringIO()) as fake_out:
        process_merged_files([str(archive)], settings, logger)
        result = json.loads(fake_out.getvalue())
        # Should contain message 4 and 5
        assert len(result) == 2
        msgnums = {r["header"]["msgnum"] for r in result}
        assert msgnums == {4, 5}


def test_calculate_archive_stats_with_thread_id_filter(tmp_path):
    # Thread 1: 1, 2
    # Thread 3: 3
    m1 = create_test_msg(1, 0)
    m2 = create_test_msg(2, 1)
    m3 = create_test_msg(3, 0)

    archive = tmp_path / "archive_stats.json"
    data = [
        {"header": m.header.as_dict, "text": m.text, "confnum": m.confnum}
        for m in [m1, m2, m3]
    ]
    archive.write_text(json.dumps(data))

    logger = logging.getLogger("test_thread_id_stats")

    # Limit stats to thread 1
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=True,
        binaries_removal=False,
        redact_pii=False,
        format="json",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        thread_id_filters={1},
        quiet=True,
    )

    stats = calculate_archive_stats([str(archive)], settings, logger)
    assert stats["matching_messages"] == 2
    assert stats["total_messages"] == 3


def test_cli_thread_id_parsing():
    # Test integration using mock args
    test_args = ["qwk.py", "dummy.qwk", "--thread-id", "10,20-22", "--dry-run"]
    with patch("sys.argv", test_args), patch("pyqwk.cli.expand_paths", return_value=["dummy.qwk"]), patch("pyqwk.cli.process_merged_files") as mock_process:
        main()
        mock_process.assert_called_once()
        settings = mock_process.call_args[0][1]
        assert settings.thread_id_filters == {10, 20, 21, 22}
        assert settings.dry_run is True
