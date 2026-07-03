
import pytest
from unittest.mock import patch, MagicMock
from pyqwk.core import process_merged_files, ProcessingSettings

def test_process_merged_files_threaded_depth_filtering(message_factory):
    # Setup messages: m1 is root (depth 0), m2 is reply to m1 (depth 1)
    m1 = message_factory(1, None, "Topic")
    m2 = message_factory(2, 1, "Re: Topic")

    # Configure settings to enable threading and depth filtering
    # We want to keep only m2, so we set min_depth=1
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=True,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        min_depth=1,
        quiet=True
    )

    # Mock data loading
    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = ([m1, m2], {1: "General"})

        # Capture stdout to verify output
        with patch("pyqwk.core._write_text") as mock_write:
            process_merged_files(["dummy.qwk"], settings, MagicMock())

            # Verify that only m2 (depth 1) was processed after threading and depth filtering
            args, _ = mock_write.call_args
            messages = args[0]
            msgnums = [m.msgnum for m in messages]

            assert 1 not in msgnums, "Root message (depth 0) should have been filtered out"
            assert 2 in msgnums, "Reply message (depth 1) should have been kept"
            assert len(messages) == 1
