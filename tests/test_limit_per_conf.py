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
        limit_per_conf=None,
        limit=None,
        quiet=True
    )

def create_mock_msg(confnum, msgnum, text="Test message"):
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
        confname=f"Conf {confnum}"
    )

def test_limit_per_conf_logic(mock_logger, base_settings):
    # Set limit per conference to 2
    base_settings.limit_per_conf = 2

    # 3 messages in Conf 1, 1 message in Conf 2
    messages = [
        create_mock_msg(1, 101),
        create_mock_msg(1, 102),
        create_mock_msg(1, 103), # Should be skipped
        create_mock_msg(2, 201),
    ]

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, {1: "Conf 1", 2: "Conf 2"})

        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)

            # Check the messages passed to write_messages
            # args[0] is the list of messages
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 3
            conf1_msgs = [m for m in written_messages if m.confnum == 1]
            conf2_msgs = [m for m in written_messages if m.confnum == 2]

            assert len(conf1_msgs) == 2
            assert len(conf2_msgs) == 1
            assert [m.msgnum for m in conf1_msgs] == [101, 102]

def test_limit_per_conf_with_global_limit(mock_logger, base_settings):
    # Limit per conf = 2, Global limit = 3
    base_settings.limit_per_conf = 2
    base_settings.limit = 3

    # 3 messages in Conf 1, 3 messages in Conf 2
    messages = [
        create_mock_msg(1, 101),
        create_mock_msg(1, 102),
        create_mock_msg(1, 103), # Skipped (conf limit)
        create_mock_msg(2, 201),
        create_mock_msg(2, 202), # Skipped (global limit reached by this or next?)
        create_mock_msg(2, 203),
    ]

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, {1: "Conf 1", 2: "Conf 2"})

        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)

            written_messages = mock_write.call_args[0][0]

            # 101, 102 (Conf 1), 201 (Conf 2) -> Total 3
            assert len(written_messages) == 3
            assert [m.msgnum for m in written_messages] == [101, 102, 201]

def test_limit_per_conf_streaming_behavior(mock_logger, base_settings):
    # Verify it works with streaming (no sort/thread/tail)
    base_settings.limit_per_conf = 1

    messages = [
        create_mock_msg(1, 101),
        create_mock_msg(1, 102),
        create_mock_msg(2, 201),
        create_mock_msg(2, 202),
    ]

    # In streaming mode, write_messages might not be called if individual_files is True,
    # but here it's False, so it collects all and calls write_messages at the end.

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, {1: "Conf 1", 2: "Conf 2"})

        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 2
            assert [m.msgnum for m in written_messages] == [101, 201]
