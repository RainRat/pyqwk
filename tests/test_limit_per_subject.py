import pytest
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    ProcessingSettings,
    process_merged_files,
    calculate_archive_stats,
    BBSInfo,
    ConferenceMap,
)
from unittest.mock import MagicMock, patch
import io
import os

def create_msg(msgnum, author, subject, confnum=1):
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="All",
        msgfrom=author,
        msgsubject=subject,
        msgpassword="",
        refnum=0,
        numblocks=1,
        msgflag="",
        confnum=confnum,
        lognum=0,
        nettag=""
    )
    return ParsedMessage(
        text=f"Body of {msgnum}",
        msgnum=msgnum,
        refnum=0,
        confnum=confnum,
        header=header
    )

def create_settings(**kwargs):
    default_settings = {
        "verbose": False,
        "private": False,
        "no_header": False,
        "truncate_signatures": False,
        "cut_quoting": False,
        "individual_files": False,
        "threaded": False,
        "binaries_removal": False,
        "redact_pii": False,
        "format": "text",
        "separator": "none",
        "output_mode": "stdout",
        "output_path": None,
        "encoding": "utf-8"
    }
    default_settings.update(kwargs)
    return ProcessingSettings(**default_settings)

def test_limit_per_subject_logic():
    # Create mock messages with different subjects
    msg1 = create_msg(1, "User A", "Subject A")
    msg2 = create_msg(2, "User B", "Re: Subject A")
    msg3 = create_msg(3, "User C", "Subject B")
    msg4 = create_msg(4, "User D", "Subject A")

    messages = [msg1, msg2, msg3, msg4]

    settings = create_settings(limit_per_subject=1)

    logger = MagicMock()

    # We need to mock load_data to return our messages
    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, ConferenceMap())

        # Test process_merged_files (streaming)
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            process_merged_files(["dummy.qwk"], settings, logger)
            output = fake_out.getvalue()
            # Should have "Subject A" and "Subject B" once.
            # msg2 is "Re: Subject A" which normalizes to "subject a"
            # So with limit 1, it should only show msg1 and msg3.
            assert "Body of 1" in output
            assert "Body of 3" in output
            assert "Body of 2" not in output
            assert "Body of 4" not in output

    # Test with limit 2
    settings.limit_per_subject = 2
    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, ConferenceMap())
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            process_merged_files(["dummy.qwk"], settings, logger)
            output = fake_out.getvalue()
            assert "Body of 1" in output
            assert "Body of 2" in output # Re: Subject A
            assert "Body of 3" in output # Subject B
            assert "Body of 4" not in output # Third "Subject A"

def test_limit_per_subject_stats():
    msg1 = create_msg(1, "User A", "Subject A")
    msg2 = create_msg(2, "User B", "Re: Subject A")

    messages = [msg1, msg2]
    settings = create_settings(limit_per_subject=1)
    logger = MagicMock()

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, ConferenceMap())
        stats = calculate_archive_stats(["dummy.qwk"], settings, logger)
        assert stats["total_messages"] == 2
        assert stats["matching_messages"] == 1

def test_consistent_limits_in_stats():
    msg1 = create_msg(1, "User A", "Subject A", confnum=1)
    msg2 = create_msg(2, "User A", "Subject B", confnum=1)
    msg3 = create_msg(3, "User B", "Subject C", confnum=2)

    messages = [msg1, msg2, msg3]
    logger = MagicMock()

    # Test limit_per_conf
    settings = create_settings(limit_per_conf=1)
    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, ConferenceMap())
        stats = calculate_archive_stats(["dummy.qwk"], settings, logger)
        # Conf 1: msg1 (msg2 skipped)
        # Conf 2: msg3
        assert stats["matching_messages"] == 2

    # Test limit_per_author
    settings = create_settings(limit_per_author=1)
    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, ConferenceMap())
        stats = calculate_archive_stats(["dummy.qwk"], settings, logger)
        # User A: msg1 (msg2 skipped)
        # User B: msg3
        assert stats["matching_messages"] == 2
