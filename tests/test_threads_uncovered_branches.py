import logging
import json
from unittest.mock import patch

from pyqwk.core import (
    BBSInfo,
    ConferenceMap,
    ParsedMessage,
    ProcessingSettings,
    render_threads_as_text,
    show_threads,
)


def test_render_threads_as_text_truncation_and_colors():
    thread_metrics = [
        {
            "thread_id": "100",
            "root_subject": "A" * 35,  # > 30 chars
            "starter": "B" * 25,       # > 20 chars
            "reply_count": 5,
            "deepest_depth": 3,
            "last_activity": "01-01-24 12:00",
        }
    ]

    plain_out = render_threads_as_text(thread_metrics, use_colors=False)
    assert "A" * 27 + "..." in plain_out
    assert "B" * 17 + "..." in plain_out

    colored_out = render_threads_as_text(thread_metrics, use_colors=True)
    assert "\033[" in colored_out
    assert "A" * 27 + "..." in colored_out


def test_show_threads_short_file_data_and_exception(message_factory):
    m = message_factory(1, 0, "Normal Subject")
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
    logger = logging.getLogger("test_threads_uncovered")

    def mock_load_data(path, logger_arg, encoding):
        if path == "short.qwk":
            return bytearray(b"too_short"), ConferenceMap()
        if path == "error.qwk":
            raise ValueError("Corrupt file")
        return [m], ConferenceMap()

    with patch("pyqwk.core.load_data", side_effect=mock_load_data):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_threads(["short.qwk", "error.qwk", "valid.json"], settings, logger)
            mock_write.assert_called_once()
            metrics = json.loads(mock_write.call_args[0][0])
            assert len(metrics) == 1
            assert metrics[0]["root_subject"] == "Normal Subject"


def test_show_threads_bbs_info_fallback_and_second_pass_exception(message_factory):
    m = message_factory(1, 0, "Pass2 Subject")
    bbs_info = BBSInfo(user_name="BBSUser")
    board_map = ConferenceMap()
    board_map.bbs_info = bbs_info

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
        my_name=None,
        quiet=True,
    )
    logger = logging.getLogger("test_threads_bbs_pass2")

    call_count = 0

    def mock_load_data(path, logger_arg, encoding):
        nonlocal call_count
        call_count += 1
        # Pass 1 calls (1 and 2):
        if call_count <= 2:
            if path == "file1.json":
                return [m], board_map
            return [], ConferenceMap()
        # Pass 2 calls (3 and 4):
        if path == "file1.json":
            return [m], board_map
        raise RuntimeError("Pass 2 error")

    with patch("pyqwk.core.load_data", side_effect=mock_load_data):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_threads(["file1.json", "file2.json"], settings, logger)
            mock_write.assert_called_once()


def test_show_threads_non_zero_depth_root_and_string_thread_id(message_factory):
    # m1 has msgnum=None so thread_id becomes "idx_0" (string fallback in thread_sort_key)
    m1 = message_factory(1, 0, "No Zero Depth Root")
    m1.header.msgnum = None
    m1.msgnum = None

    m2 = message_factory(2, 0, "Numeric Thread ID")

    # Manually construct list with m1 depth=1
    m1_parsed = ParsedMessage(
        text=m1.text,
        msgnum=None,
        refnum=None,
        confnum=1,
        header=m1.header,
        depth=1,
    )

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
    logger = logging.getLogger("test_threads_roots")

    with patch("pyqwk.core.load_data", return_value=([m1_parsed, m2], ConferenceMap())):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_threads(["dummy.json"], settings, logger)
            mock_write.assert_called_once()
            metrics = json.loads(mock_write.call_args[0][0])
            assert len(metrics) == 2
            # "2" sorts before "idx_0" (tuple (0, 2) vs (1, "idx_0"))
            assert metrics[0]["thread_id"] == "2"
            assert metrics[1]["thread_id"] == "idx_0"


def test_show_threads_output_formats(message_factory):
    m = message_factory(1, 0, "Multi Format Subject")

    base_settings_kwargs = dict(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=True,
        binaries_removal=False,
        redact_pii=False,
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )

    formats = ["html", "markdown", "csv", "text"]
    logger = logging.getLogger("test_threads_formats")

    for fmt in formats:
        settings = ProcessingSettings(format=fmt, **base_settings_kwargs)
        with patch("pyqwk.core.load_data", return_value=([m], ConferenceMap())):
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_threads(["dummy.json"], settings, logger)
                mock_write.assert_called_once()
                out = mock_write.call_args[0][0]
                if fmt == "html":
                    assert "<h1>Conversation Threads</h1>" in out
                elif fmt == "markdown":
                    assert "# Conversation Threads" in out
                elif fmt == "csv":
                    assert '"thread_id","root_subject"' in out
                elif fmt == "text":
                    assert "Conversation Threads:" in out
