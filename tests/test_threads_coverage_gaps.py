import json
import logging
from unittest.mock import patch, MagicMock, ANY
import pytest
from pyqwk.core import (
    ProcessingSettings,
    show_threads,
    render_threads_as_text,
)


def test_render_threads_text_truncation_long_subject_and_starter():
    thread_metrics = [{
        "thread_id": "1",
        "root_subject": "This is a very long subject that exceeds thirty characters",
        "starter": "ThisIsAVeryLongStarterNameIndeed",
        "reply_count": 0,
        "deepest_depth": 0,
        "last_activity": "01-01-24 10:00",
    }]
    text_out = render_threads_as_text(thread_metrics, use_colors=False)
    assert "This is a very long subject..." in text_out
    assert "ThisIsAVeryLongSt..." in text_out


def test_show_threads_fallback_when_no_root_message(message_factory):
    m = message_factory(10, 1, "A reply thread", confnum=1, text="Text")
    m.header.msgfrom = "Bob"
    m.header.msgdate = "01-01-24"
    m.header.msgtime = "10:00"
    m.thread_id = 10
    m.depth = 1

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

    with patch("pyqwk.core.load_data", return_value=([m], {})):
        with patch("pyqwk.core._order_messages_by_thread") as mock_order:
            m_with_depth = message_factory(10, 1, "A reply thread", confnum=1, text="Text")
            m_with_depth.header.msgfrom = "Bob"
            m_with_depth.header.msgdate = "01-01-24"
            m_with_depth.header.msgtime = "10:00"
            m_with_depth.thread_id = 10
            m_with_depth.depth = 1
            mock_order.return_value = [m_with_depth]
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_threads(["dummy.qwk"], settings, logging.getLogger("test"))
                mock_write.assert_called_once()
                output_content = mock_write.call_args[0][0]
                metrics = json.loads(output_content)
                assert len(metrics) == 1
                assert metrics[0]["root_subject"] == "A reply thread"


def test_show_threads_sorting_fallback_with_non_integer_thread_id(message_factory):
    m1 = message_factory(None, 0, "Thread idx", confnum=1)
    m1.header.msgfrom = "User"
    m1.header.msgdate = "01-01-24"
    m1.header.msgtime = "10:00"
    m1.depth = 0

    m2 = message_factory(2, 0, "Thread 2", confnum=1)
    m2.header.msgfrom = "User"
    m2.header.msgdate = "01-01-24"
    m2.header.msgtime = "10:00"
    m2.depth = 0

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

    with patch("pyqwk.core.load_data", return_value=([m1, m2], {})):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_threads(["dummy.qwk"], settings, logging.getLogger("test"))
            output_content = mock_write.call_args[0][0]
            metrics = json.loads(output_content)
            assert metrics[0]["thread_id"] == "2"
            assert metrics[1]["thread_id"] == "idx_0"


def test_show_threads_archives_load_failure_exception():
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
    logger = MagicMock()
    with patch("pyqwk.core.load_data", side_effect=Exception("Corrupt file")):
        show_threads(["corrupt.qwk"], settings, logger)
        logger.error.assert_called_with(
            "Failed to load archive %s: %s", "corrupt.qwk", ANY
        )


def test_show_threads_file_data_smaller_than_block_size():
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
    logger = MagicMock()
    with patch("pyqwk.core.load_data", return_value=(b"Short data", {})):
        show_threads(["short.qwk"], settings, logger)
        logger.warning.assert_called_with("No messages loaded. Thread-listing aborted.")


def test_show_threads_multi_formats_integration(message_factory):
    m = message_factory(1, 0, "Post", confnum=1, text="Original text\n")
    m.header.msgfrom = "Alice"
    m.header.msgdate = "01-01-24"
    m.header.msgtime = "10:00"
    m.thread_id = 1
    m.depth = 0

    for fmt in ["html", "markdown", "csv"]:
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
        with patch("pyqwk.core.load_data", return_value=([m], {})):
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_threads(["dummy.qwk"], settings, logging.getLogger("test"))
                mock_write.assert_called_once()
                output = mock_write.call_args[0][0]
                if fmt == "html":
                    assert "<html" in output.lower()
                elif fmt == "markdown":
                    assert "| Thread ID |" in output
                elif fmt == "csv":
                    assert '"thread_id"' in output


def test_show_threads_text_ansi_colors_integration(message_factory):
    m = message_factory(1, 0, "Post", confnum=1, text="Original text\n")
    m.header.msgfrom = "Alice"
    m.header.msgdate = "01-01-24"
    m.header.msgtime = "10:00"
    m.thread_id = 1
    m.depth = 0

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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )
    with patch("pyqwk.core.load_data", return_value=([m], {})):
        with patch("pyqwk.core._write_text_output") as mock_write:
            mock_stdout = MagicMock()
            mock_stdout.isatty.return_value = True
            with patch("sys.stdout", mock_stdout):
                show_threads(["dummy.qwk"], settings, logging.getLogger("test"))
                mock_write.assert_called_once()
                output = mock_write.call_args[0][0]
                assert "\033[" in output


def test_show_threads_user_name_auto_detection_from_bbs_metadata(message_factory):
    m = message_factory(10, 0, "Topic", confnum=1)
    m.header.msgfrom = "Self User"
    m.header.msgdate = "01-01-24"
    m.header.msgtime = "10:00"
    m.thread_id = 10
    m.depth = 0

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
        my_name=None,
    )

    board_dict = {}
    class BBSInfo:
        name = "MyBBS"
        bbs_id = "BBS1"
        user_name = "Self User"

    board_dict_mock = MagicMock()
    board_dict_mock.get.side_effect = lambda k: "Board Name"
    setattr(board_dict_mock, "bbs_info", BBSInfo())

    with patch("pyqwk.core.load_data", return_value=([m], board_dict_mock)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_threads(["dummy.qwk"], settings, logging.getLogger("test"))
            mock_write.assert_called_once()
            output_content = mock_write.call_args[0][0]
            metrics = json.loads(output_content)
            assert len(metrics) == 1


def test_show_threads_bytes_larger_than_block_size(message_factory):
    m = message_factory(1, 0, "Post", confnum=1, text="Text\n")
    m.header.msgfrom = "Alice"
    m.header.msgdate = "01-01-24"
    m.header.msgtime = "10:00"
    m.thread_id = 1
    m.depth = 0

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
    with patch("pyqwk.core.load_data", return_value=(b"A" * 150, {})):
        with patch("pyqwk.core.parse_messages", return_value=[m]):
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_threads(["dummy.qwk"], settings, logging.getLogger("test"))
                mock_write.assert_called_once()


def test_show_threads_load_data_second_loop_exception(message_factory):
    m = message_factory(1, 0, "Post", confnum=1, text="Text\n")
    m.header.msgfrom = "Alice"
    m.header.msgdate = "01-01-24"
    m.header.msgtime = "10:00"
    m.thread_id = 1
    m.depth = 0

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

    # First call to load_data succeeds, second call to load_data raises Exception
    with patch("pyqwk.core.load_data", side_effect=[([m], {}), Exception("Fail on loop 2")]):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_threads(["dummy.qwk"], settings, logging.getLogger("test"))
            mock_write.assert_called_once()
