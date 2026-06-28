import pytest
import io
from pyqwk.core import (
    ProcessingSettings, ParsedMessage, MessageHeader,
    ConferenceMap, process_merged_files
)
from unittest.mock import MagicMock, patch

def test_limit_zero_with_sorting():
    """Verify that limit=0 correctly results in no output when sorting is enabled (non-streaming)."""
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False,
        format="text", separator="auto",
        output_mode="stdout", output_path=None,
        encoding="cp437", limit=0, sort="num", quiet=True
    )
    msg1 = ParsedMessage("msg1", 1, None, 1, MessageHeader(" ", 1, "01-01-24", "10:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""))
    bd = ConferenceMap({1: "Conf1"})

    logger = MagicMock()
    with patch("pyqwk.core.load_data", return_value=([msg1], bd)):
        with patch("sys.stdout", new=io.StringIO()) as mock_stdout:
            process_merged_files(["test.qwk"], settings, logger)
            output = mock_stdout.getvalue()
            # The output should only be the final newline added by _write_text_output
            assert output == "\n"

def test_tail_zero_with_sorting():
    """Verify that tail=0 correctly results in no output when sorting is enabled (non-streaming)."""
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False,
        format="text", separator="auto",
        output_mode="stdout", output_path=None,
        encoding="cp437", tail=0, sort="num", quiet=True
    )
    msg1 = ParsedMessage("msg1", 1, None, 1, MessageHeader(" ", 1, "01-01-24", "10:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""))
    bd = ConferenceMap({1: "Conf1"})

    logger = MagicMock()
    with patch("pyqwk.core.load_data", return_value=([msg1], bd)):
        with patch("sys.stdout", new=io.StringIO()) as mock_stdout:
            process_merged_files(["test.qwk"], settings, logger)
            output = mock_stdout.getvalue()
            assert output == "\n"

def test_skip_zero_with_sorting():
    """Verify that skip=0 correctly results in all output when sorting is enabled (non-streaming)."""
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False,
        format="text", separator="auto",
        output_mode="stdout", output_path=None,
        encoding="cp437", skip=0, sort="num", quiet=True
    )
    msg1 = ParsedMessage("msg1", 1, None, 1, MessageHeader(" ", 1, "01-01-24", "10:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""))
    bd = ConferenceMap({1: "Conf1"})

    logger = MagicMock()
    with patch("pyqwk.core.load_data", return_value=([msg1], bd)):
        with patch("sys.stdout", new=io.StringIO()) as mock_stdout:
            process_merged_files(["test.qwk"], settings, logger)
            output = mock_stdout.getvalue()
            assert "From" in output
            assert "To" in output
            assert "Sub" in output
