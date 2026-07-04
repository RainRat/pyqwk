import pytest
import io
from pyqwk.core import (
    ProcessingSettings, ParsedMessage, MessageHeader,
    ConferenceMap, process_merged_files
)
from unittest.mock import MagicMock, patch

def test_threaded_depth_filtering_coverage(message_factory):
    """Targeted test to cover line 3679 in pyqwk/core.py where depth filtering is applied after threading."""

    # Setup messages: 1 root, 1 child (depth 1), 1 grandchild (depth 2)
    # message_factory(msgnum, refnum, subject)
    m1 = message_factory(10, 0, "Root Topic")
    m2 = message_factory(11, 10, "Re: Root Topic")
    m3 = message_factory(12, 11, "Re: Root Topic")

    # We want to filter for messages with depth >= 1 and <= 1
    # This should only return m2
    settings = ProcessingSettings(
        verbose=True, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=True, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437",
        min_depth=1, max_depth=1, sort=None, reverse=False, quiet=True
    )

    bd = ConferenceMap({1: "Test Conference"})

    logger = MagicMock()
    with patch("pyqwk.core.load_data", return_value=([m1, m2, m3], bd)):
        with patch("sys.stdout", new=io.StringIO()) as mock_stdout:
            process_merged_files(["test.qwk"], settings, logger)
            output = mock_stdout.getvalue()

    # Verify m2 is present (Msg # 11)
    assert "Message #:      11" in output
    # Verify m1 (depth 0, Msg # 10) and m3 (depth 2, Msg # 12) are NOT present
    assert "Message #:      10" not in output
    assert "Message #:      12" not in output

def test_threaded_min_depth_only(message_factory):
    """Verify that min_depth only works correctly with threading."""
    m1 = message_factory(10, 0, "Root Topic")
    m2 = message_factory(11, 10, "Re: Root Topic")

    settings = ProcessingSettings(
        verbose=True, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=True, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437",
        min_depth=1, sort=None, quiet=True
    )

    bd = ConferenceMap({1: "Test Conference"})

    logger = MagicMock()
    with patch("pyqwk.core.load_data", return_value=([m1, m2], bd)):
        with patch("sys.stdout", new=io.StringIO()) as mock_stdout:
            process_merged_files(["test.qwk"], settings, logger)
            output = mock_stdout.getvalue()

            assert "Message #:      11" in output
            assert "Message #:      10" not in output

def test_threaded_max_depth_only(message_factory):
    """Verify that max_depth only works correctly with threading."""
    m1 = message_factory(10, 0, "Root Topic")
    m2 = message_factory(11, 10, "Re: Root Topic")

    settings = ProcessingSettings(
        verbose=True, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=True, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437",
        max_depth=0, sort=None, quiet=True
    )

    bd = ConferenceMap({1: "Test Conference"})

    logger = MagicMock()
    with patch("pyqwk.core.load_data", return_value=([m1, m2], bd)):
        with patch("sys.stdout", new=io.StringIO()) as mock_stdout:
            process_merged_files(["test.qwk"], settings, logger)
            output = mock_stdout.getvalue()

            assert "Message #:      10" in output
            assert "Message #:      11" not in output
