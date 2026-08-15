import logging
import sys
from unittest.mock import patch, MagicMock
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    ProcessingSettings,
    show_threads,
    render_threads_as_text,
)


def test_render_threads_as_text_truncation():
    thread_metrics = [
        {
            "thread_id": "1",
            "root_subject": "A" * 35,  # > 30 chars
            "starter": "B" * 25,       # > 20 chars
            "reply_count": 5,
            "deepest_depth": 3,
            "last_activity": "01-01-24 10:00",
        }
    ]
    out = render_threads_as_text(thread_metrics, use_colors=False)
    assert "A" * 27 + "..." in out
    assert "B" * 17 + "..." in out


def test_show_threads_short_file_and_load_exception():
    logger = logging.getLogger("test_threads_branches")
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=True,
        binaries_removal=False,
        redact_pii=False,
        format="json",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )

    # 1. Non-structured file_data shorter than BLOCK_SIZE (128 bytes)
    with patch("pyqwk.core.load_data", return_value=(b"short_bytes", {})):
        with patch("logging.Logger.warning") as mock_warn:
            show_threads(["short.qwk"], settings, logger)
            mock_warn.assert_called_with("No messages loaded. Thread-listing aborted.")

    # 2. Exception raised during load_data in first pass
    with patch("pyqwk.core.load_data", side_effect=ValueError("Load failed")):
        with patch("logging.Logger.error") as mock_err:
            show_threads(["invalid.qwk"], settings, logger)
            mock_err.assert_called_once()
            assert "Failed to load archive" in mock_err.call_args[0][0]


def test_show_threads_bbs_info_username_and_second_pass_exception(message_factory):
    logger = logging.getLogger("test_threads_bbs")
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=True,
        binaries_removal=False,
        redact_pii=False,
        format="json",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
        exclude_conferences=["General"],  # Triggers allowed_exclude_conferences update
    )

    m1 = message_factory(1, 0, "Test subject", confnum=1, text="Body\n")
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "Bob"
    m1.header.msgdate = "01-01-24"
    m1.header.msgtime = "10:00"

    bbs_info = MagicMock()
    bbs_info.user_name = "BBS User"
    board_dict = MagicMock()
    board_dict.bbs_info = bbs_info

    # First load_data succeeds, second load_data in pass 2 raises Exception
    load_counts = 0

    def mock_load_data(path, logger, encoding):
        nonlocal load_counts
        load_counts += 1
        if load_counts == 1:
            return ([m1], board_dict)
        raise RuntimeError("Second pass error")

    with patch("pyqwk.core.load_data", side_effect=mock_load_data):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_threads(["test.qwk"], settings, logger)
            mock_write.assert_called_once()


def test_show_threads_output_formats(message_factory):
    logger = logging.getLogger("test_threads_formats")
    m1 = message_factory(1, 0, "Test format subject", confnum=1, text="Body\n")
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "Bob"
    m1.header.msgdate = "01-01-24"
    m1.header.msgtime = "10:00"

    formats = ["html", "markdown", "csv", "text"]

    for fmt in formats:
        settings = ProcessingSettings(
            verbose=False,
            private=True,
            no_header=False,
            truncate_signatures=False,
            cut_quoting=False,
            individual_files=False,
            threaded=True,
            binaries_removal=False,
            redact_pii=False,
            format=fmt,
            separator="none",
            output_mode="stdout",
            output_path=None,
            encoding="cp437",
            quiet=True,
        )

        with patch("pyqwk.core.load_data", return_value=([m1], {})):
            with patch("pyqwk.core._write_text_output") as mock_write:
                with patch.object(sys.stdout, "isatty", return_value=True):
                    show_threads(["test.qwk"], settings, logger)
                    mock_write.assert_called_once()
