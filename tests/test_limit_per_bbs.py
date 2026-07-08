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
        limit_per_bbs=None,
        limit=None,
        quiet=True
    )

def create_mock_msg(bbs_name, msgnum, confnum=1, text="Test message"):
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="All",
        msgfrom="User",
        msgsubject="Subject",
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
        bbs_name=bbs_name
    )

def test_limit_per_bbs_logic(mock_logger, base_settings):
    # Set limit per BBS to 2
    base_settings.limit_per_bbs = 2

    # 3 messages from BBS A, 1 message from BBS B
    messages = [
        create_mock_msg("BBS A", 101),
        create_mock_msg("BBS A", 102),
        create_mock_msg("BBS A", 103), # Should be skipped
        create_mock_msg("BBS B", 201),
    ]

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, {1: "Conf 1"})

        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)

            # Check the messages passed to write_messages
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 3
            bbs_a_msgs = [m for m in written_messages if m.bbs_name == "BBS A"]
            bbs_b_msgs = [m for m in written_messages if m.bbs_name == "BBS B"]

            assert len(bbs_a_msgs) == 2
            assert len(bbs_b_msgs) == 1
            assert [m.msgnum for m in bbs_a_msgs] == [101, 102]

def test_limit_per_bbs_stats(mock_logger, base_settings):
    base_settings.limit_per_bbs = 1

    messages = [
        create_mock_msg("BBS A", 101),
        create_mock_msg("BBS A", 102),
        create_mock_msg("BBS B", 201),
    ]

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, {1: "Conf 1"})

        stats = calculate_archive_stats(["mock.qwk"], base_settings, mock_logger)

        # 1 from BBS A, 1 from BBS B
        assert stats["matching_messages"] == 2
        assert stats["total_messages"] == 3

def test_limit_per_bbs_case_insensitive(mock_logger, base_settings):
    base_settings.limit_per_bbs = 1

    messages = [
        create_mock_msg("BBS A", 101),
        create_mock_msg("bbs a", 102), # Should be skipped
    ]

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, {1: "Conf 1"})

        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 1
            assert written_messages[0].msgnum == 101
