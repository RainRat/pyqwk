import pytest
import logging
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    ProcessingSettings,
    process_merged_files,
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
        limit_per_author=None,
        limit=None,
        quiet=True
    )

def create_mock_msg(msgfrom, msgnum, confnum=1, text="Test message"):
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="All",
        msgfrom=msgfrom,
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
        confname=f"Conf {confnum}"
    )

def test_limit_per_author_logic(mock_logger, base_settings):
    # Set limit per author to 2
    base_settings.limit_per_author = 2

    # 3 messages from Alice, 1 message from Bob
    messages = [
        create_mock_msg("Alice", 101),
        create_mock_msg("Alice", 102),
        create_mock_msg("Alice", 103), # Should be skipped
        create_mock_msg("Bob", 201),
    ]

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, {1: "Conf 1"})

        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)

            # Check the messages passed to write_messages
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 3
            alice_msgs = [m for m in written_messages if m.header.msgfrom == "Alice"]
            bob_msgs = [m for m in written_messages if m.header.msgfrom == "Bob"]

            assert len(alice_msgs) == 2
            assert len(bob_msgs) == 1
            assert [m.msgnum for m in alice_msgs] == [101, 102]

def test_limit_per_author_case_insensitivity(mock_logger, base_settings):
    # Set limit per author to 1
    base_settings.limit_per_author = 1

    # Mixed case author names
    messages = [
        create_mock_msg("Alice", 101),
        create_mock_msg("alice", 102), # Should be skipped
        create_mock_msg("ALICE", 103), # Should be skipped
    ]

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, {1: "Conf 1"})

        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 1
            assert written_messages[0].msgnum == 101

def test_limit_per_author_with_limit_per_conf(mock_logger, base_settings):
    # limit per author = 1, limit per conf = 2
    base_settings.limit_per_author = 1
    base_settings.limit_per_conf = 2

    messages = [
        create_mock_msg("Alice", 101, confnum=1),
        create_mock_msg("Alice", 102, confnum=1), # Skipped (author limit)
        create_mock_msg("Bob", 103, confnum=1),
        create_mock_msg("Charlie", 104, confnum=1), # Skipped (conf limit)
    ]

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, {1: "Conf 1"})

        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            # 101 (Alice, Conf 1), 103 (Bob, Conf 1)
            assert len(written_messages) == 2
            assert [m.msgnum for m in written_messages] == [101, 103]
