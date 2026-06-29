import logging
from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings, matches_filters, process_merged_files
import pytest
from unittest.mock import MagicMock

def test_attachment_count_filtering():
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-24", msgtime="12:00",
        msgto="To", msgfrom="From", msgsubject="Subj", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=1, nettag=" "
    )

    # Message with 0 attachments (no UUE markers)
    msg0 = ParsedMessage(text="Hello world", msgnum=1, refnum=None, confnum=1, header=header)

    # Message with 1 attachment (UUE)
    uue_text = "begin 644 test.txt\n!\nend\n"
    msg1 = ParsedMessage(text=f"Check this out\n\n{uue_text}", msgnum=2, refnum=None, confnum=1, header=header)

    # Message with 2 attachments (UUE)
    uue_text2 = "begin 644 test1.txt\n!\nend\nbegin 644 test2.txt\n!\nend\n"
    msg2 = ParsedMessage(text=f"Two files\n\n{uue_text2}", msgnum=3, refnum=None, confnum=1, header=header)

    settings_min = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="auto", output_mode="stdout",
        output_path=None, encoding="cp437", min_attachments=1
    )

    assert not matches_filters(msg0, settings_min, {1})
    assert matches_filters(msg1, settings_min, {1})
    assert matches_filters(msg2, settings_min, {1})

    settings_max = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="auto", output_mode="stdout",
        output_path=None, encoding="cp437", max_attachments=1
    )

    assert matches_filters(msg0, settings_max, {1})
    assert matches_filters(msg1, settings_max, {1})
    assert not matches_filters(msg2, settings_max, {1})

    settings_range = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="auto", output_mode="stdout",
        output_path=None, encoding="cp437", min_attachments=1, max_attachments=1
    )

    assert not matches_filters(msg0, settings_range, {1})
    assert matches_filters(msg1, settings_range, {1})
    assert not matches_filters(msg2, settings_range, {1})

def test_attachment_count_sorting(mocker):
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-24", msgtime="12:00",
        msgto="To", msgfrom="From", msgsubject="Subj", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=1, nettag=" "
    )

    msg0 = ParsedMessage(text="Zero", msgnum=1, refnum=None, confnum=1, header=header)
    msg1 = ParsedMessage(text="One\n\nbegin 644 t.txt\n!\nend", msgnum=2, refnum=None, confnum=1, header=header)
    msg2 = ParsedMessage(text="Two\n\nbegin 644 t1.txt\n!\nend\nbegin 644 t2.txt\n!\nend", msgnum=3, refnum=None, confnum=1, header=header)

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="auto", output_mode="stdout",
        output_path=None, encoding="cp437", sort="attachments"
    )

    # We need to mock load_data to return our messages
    mocker.patch("pyqwk.core.load_data", return_value=([msg1, msg0, msg2], {1: "General"}))
    # Mock sys.stdout.write to capture output if needed, but here we just want to check sort order
    # Actually, we can check how they are collected in process_merged_files if we mock handle_output

    # Let's mock write_messages to see what it gets
    mock_write = mocker.patch("pyqwk.core.write_messages")

    logger = logging.getLogger("test")
    process_merged_files(["dummy.qwk"], settings, logger)

    # The messages should be sorted by attachment count: msg0 (0), msg1 (1), msg2 (2)
    called_messages = mock_write.call_args[0][0]
    assert [m.msgnum for m in called_messages] == [1, 2, 3]

    # Test reverse sort
    settings.reverse = True
    process_merged_files(["dummy.qwk"], settings, logger)
    called_messages_rev = mock_write.call_args[0][0]
    assert [m.msgnum for m in called_messages_rev] == [3, 2, 1]
