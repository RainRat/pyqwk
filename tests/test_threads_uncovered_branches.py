import logging
import json
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
            "root_subject": "This is a very long root subject that exceeds thirty characters",
            "starter": "VeryLongAuthorNameExceedingTwentyChars",
            "reply_count": 0,
            "deepest_depth": 0,
            "last_activity": "01-01-24 10:00",
        }
    ]
    res = render_threads_as_text(thread_metrics, use_colors=False)
    assert "This is a very long root su..." in res
    assert "VeryLongAuthorNam..." in res


def test_show_threads_uncovered_branches(message_factory):
    logger = logging.getLogger("test_threads_branches")

    m1 = message_factory(10, 0, "Non-zero depth root", confnum=1)
    m1.depth = 2
    m1.thread_id = "non_numeric_tid"
    m1.header.msgfrom = "Bob"
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

        bbs_info_mock = MagicMock()
        bbs_info_mock.user_name = "AliceBBSUser"
        board_dict_mock = MagicMock()
        board_dict_mock.bbs_info = bbs_info_mock
        board_dict_mock.get.return_value = "General"

        large_file_data = b"X" * 200

        def mock_load_data(path, log, enc):
            if "short.qwk" in path:
                return (b"short data", {})
            elif "error.qwk" in path:
                raise RuntimeError("Failed to read file")
            elif "large_bytes.qwk" in path:
                return (large_file_data, board_dict_mock)
            else:
                return ([m1], board_dict_mock)

        input_paths = ["short.qwk", "error.qwk", "large_bytes.qwk", "valid.qwk"]

        with patch("pyqwk.core.load_data", side_effect=mock_load_data):
            with patch("pyqwk.core.parse_messages", return_value=[m1]):
                with patch("pyqwk.core._order_messages_by_thread", side_effect=lambda msgs: msgs):
                    with patch("pyqwk.core._write_text_output") as mock_write:
                        show_threads(input_paths, settings, logger)
                        mock_write.assert_called_once()
                        output = mock_write.call_args[0][0]
                        assert len(output) > 0
                        if fmt == "html":
                            assert "<title>Conversation Threads</title>" in output
                        elif fmt == "markdown":
                            assert "# Conversation Threads" in output
                        elif fmt == "csv":
                            assert '"thread_id"' in output
                        elif fmt == "text":
                            assert "Conversation Threads:" in output
