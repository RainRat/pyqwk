import pytest
import logging
import io
from unittest.mock import patch, MagicMock
from pyqwk.core import (
    process_merged_files,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    ConferenceMap
)

def test_process_merged_files_threaded_depth_filtering_integration():
    """Cover deferred depth filtering in process_merged_files (line 3679)."""
    # Setup settings
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=True,  # Critical for triggering the gap
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        min_depth=1,    # Critical for triggering the gap
        quiet=True
    )

    # Root message (depth 0)
    h1 = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto="All", msgfrom="Root", msgsubject="Root topic", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" "
    )
    m1 = ParsedMessage(text="Root body\n", msgnum=1, refnum=None, confnum=1, header=h1)

    # Reply (depth 1)
    h2 = MessageHeader(
        status=" ", msgnum=2, msgdate="01-01-23", msgtime="12:05",
        msgto="Root", msgfrom="Reply", msgsubject="Re: Root topic", msgpassword="",
        refnum=1, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" "
    )
    m2 = ParsedMessage(text="Reply body\n", msgnum=2, refnum=1, confnum=1, header=h2)

    logger = logging.getLogger("test_depth")
    board_dict = ConferenceMap({1: "General"})

    with patch("pyqwk.core.load_data", return_value=([m1, m2], board_dict)):
        with patch("sys.stdout", new=io.StringIO()) as mock_stdout:
            process_merged_files(["dummy.qwk"], settings, logger)
            output = mock_stdout.getvalue()

    # With min_depth=1, Root body should be filtered out, and Reply body should be present.
    assert "Root body" not in output
    assert "Reply body" in output
