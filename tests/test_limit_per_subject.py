import pytest
import logging
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    ProcessingSettings,
    process_merged_files,
    calculate_archive_stats,
)
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)

@pytest.fixture
def base_settings():
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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        limit_per_subject=None,
        limit=None,
        quiet=True
    )

def create_mock_msg(subject, msgnum, confnum=1, text="Test message"):
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="All",
        msgfrom="User",
        msgsubject=subject,
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=confnum,
        lognum=0,
        nettag=" "
    )
    return ParsedMessage(
        text=text,
        msgnum=msgnum,
        refnum=None,
        confnum=confnum,
        header=header,
        confname=f"Conf {confnum}",
        bbs_name="Test BBS"
    )

def test_limit_per_subject_logic(mock_logger, base_settings):
    # Set limit per subject to 2
    base_settings.limit_per_subject = 2

    # 3 messages with subject "Alpha", 1 with "Beta"
    messages = [
        create_mock_msg("Alpha", 101),
        create_mock_msg("Alpha", 102),
        create_mock_msg("Alpha", 103), # Should be skipped
        create_mock_msg("Beta", 201),
    ]

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, {1: "Conf 1"})

        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)

            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 3
            alpha_msgs = [m for m in written_messages if m.header.msgsubject == "Alpha"]
            beta_msgs = [m for m in written_messages if m.header.msgsubject == "Beta"]

            assert len(alpha_msgs) == 2
            assert len(beta_msgs) == 1
            assert [m.msgnum for m in alpha_msgs] == [101, 102]

def test_limit_per_subject_normalization(mock_logger, base_settings):
    # Set limit per subject to 1
    base_settings.limit_per_subject = 1

    # "Re: Hello" should be normalized to "hello" and hit the limit after "Hello"
    messages = [
        create_mock_msg("Hello", 101),
        create_mock_msg("Re: Hello", 102), # Should be skipped
    ]

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, {1: "Conf 1"})

        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 1
            assert written_messages[0].msgnum == 101

def test_limit_per_subject_stats(mock_logger, base_settings):
    base_settings.limit_per_subject = 1

    messages = [
        create_mock_msg("Alpha", 101),
        create_mock_msg("Alpha", 102),
        create_mock_msg("Beta", 201),
    ]

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, {1: "Conf 1"})

        stats = calculate_archive_stats(["mock.qwk"], base_settings, mock_logger)

        # 1 from Alpha, 1 from Beta
        assert stats["matching_messages"] == 2
        assert stats["total_messages"] == 3

def test_limit_per_subject_case_insensitive(mock_logger, base_settings):
    base_settings.limit_per_subject = 1

    messages = [
        create_mock_msg("APPLE", 101),
        create_mock_msg("apple", 102), # Should be skipped
    ]

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, {1: "Conf 1"})

        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 1
            assert written_messages[0].msgnum == 101
