import pytest
import pyqwk.core
from unittest.mock import MagicMock
from pyqwk.core import (
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    process_merged_files,
    calculate_archive_stats,
)

@pytest.fixture
def message_factory():
    def _create_message(subject, msgnum, confnum=1):
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
            nettag=" ",
        )
        return ParsedMessage(
            text="Message body",
            msgnum=msgnum,
            refnum=None,
            confnum=confnum,
            header=header,
        )
    return _create_message

def test_limit_per_subject_export(message_factory, mocker):
    # Mock load_data to return our test messages
    messages = [
        message_factory("Topic A", 1),
        message_factory("Re: Topic A", 2),
        message_factory("Topic A", 3),
        message_factory("Topic B", 4),
        message_factory("Topic B", 5),
    ]

    mocker.patch("pyqwk.core.load_data", return_value=(messages, {}))
    mocker.patch("pyqwk.core.write_messages")

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="cp437", limit_per_subject=1
    )

    logger = MagicMock()
    process_merged_files(["dummy.qwk"], settings, logger)

    # Capture the messages passed to write_messages
    args, _ = pyqwk.core.write_messages.call_args
    written_messages = args[0]

    # Should only have one from Topic A and one from Topic B
    assert len(written_messages) == 2
    subjects = [m.header.msgsubject for m in written_messages]
    assert "Topic A" in subjects
    assert "Topic B" in subjects

def test_limit_per_subject_stats(message_factory, mocker):
    messages = [
        message_factory("Topic A", 1),
        message_factory("Re: Topic A", 2),
        message_factory("Topic B", 3),
    ]

    mocker.patch("pyqwk.core.load_data", return_value=(messages, {}))

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="cp437", limit_per_subject=1
    )

    logger = MagicMock()
    stats = calculate_archive_stats(["dummy.qwk"], settings, logger)

    # Topic A (2 msg) -> limited to 1
    # Topic B (1 msg) -> limited to 1
    # Total matching should be 2
    assert stats["matching_messages"] == 2
    assert stats["total_messages"] == 3
