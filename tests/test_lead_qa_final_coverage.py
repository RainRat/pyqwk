import logging
import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest

from pyqwk.core import (
    BLOCK_SIZE,
    MessageHeader,
    ProcessingSettings,
    show_list_months,
    show_list_years,
)
from pyqwk.gui import QwkGuiApp


def test_show_list_years_user_name_fallback_and_short_file(mocker, tmp_path):
    logger = logging.getLogger("test_years_gaps")

    class MockBBSInfo:
        user_name = "BBS Fallback User"
        name = "Test BBS"
        bbs_id = "TESTBBS"

    class MockBoardDict(dict):
        bbs_info = MockBBSInfo()

    mocker.patch(
        "pyqwk.core.load_data",
        return_value=([], MockBoardDict()),
    )

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="json",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        my_name=None,
    )

    show_list_years(["archive.qwk"], settings, logger)

    mocker.patch(
        "pyqwk.core.load_data",
        return_value=(b"short_data", MockBoardDict()),
    )
    show_list_months(["short.qwk"], settings, logger)
    show_list_years(["short.qwk"], settings, logger)

    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="All",
        msgfrom="Alice",
        msgsubject="Test",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" ",
    )
    qwk_bytes = bytearray(header.to_bytes("cp437") + b"Body".ljust(128))
    mocker.patch(
        "pyqwk.core.load_data",
        return_value=(qwk_bytes, MockBoardDict()),
    )
    show_list_months(["archive.qwk"], settings, logger)
    show_list_years(["archive.qwk"], settings, logger)


def test_show_list_months_raw_bytes_propagation(mocker):
    """Verify show_list_months propagates conference and BBS names while parsing raw bytes."""
    logger = logging.getLogger("test_months_raw_bytes")

    class MockBBSInfo:
        user_name = "Raw Bytes User"
        name = "Raw Bytes BBS"
        bbs_id = "RAWBYTES"

    class MockBoardDict(dict):
        bbs_info = MockBBSInfo()

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="json",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        my_name=None,
    )

    mock_msg = MagicMock()
    mock_msg.confnum = 1
    mock_msg.confname = None
    mock_msg.bbs_name = None
    mock_msg.bbs_id = None
    mock_msg.source_file = None
    mock_msg.msgnum = 100
    mock_msg.date = "2023-05-15"
    mock_msg.time = "12:00:00"
    mock_msg.author = "Alice"
    mock_msg.recipient = "Bob"
    mock_msg.subject = "Test raw bytes"

    mocker.patch(
        "pyqwk.core.load_data",
        return_value=(b"X" * 256, MockBoardDict({1: "General"})),
    )
    mocker.patch(
        "pyqwk.core.parse_messages",
        return_value=[mock_msg],
    )

    show_list_months(["archive.qwk"], settings, logger)
    assert mock_msg.confname == "General"
    assert mock_msg.bbs_name == "Raw Bytes BBS"
    assert mock_msg.bbs_id == "RAWBYTES"
    assert mock_msg.source_file == "archive.qwk"


def test_show_list_months_and_years_whitespace_blocks(mocker):
    """Verify show_list_months/years tolerate whitespace-padded blocks and short data."""
    logger = logging.getLogger("test_months_whitespace")

    class MockBoardDict(dict):
        pass

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="json",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        my_name=None,
    )

    mocker.patch(
        "pyqwk.core.load_data",
        return_value=(b" " * BLOCK_SIZE, MockBoardDict()),
    )
    show_list_months(["archive.qwk"], settings, logger)
    show_list_years(["archive.qwk"], settings, logger)


def test_gui_exclude_selection_valid_text():
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.root = root
            app.detail_text = MagicMock()
            app.exclude_var = MagicMock()
            app.message_list = MagicMock()
            app.reload_messages = MagicMock()

            app.detail_text.tag_ranges.return_value = ("1.0", "1.5")
            app.detail_text.get.return_value = " spam "

            app._exclude_from_selection()

            app.exclude_var.set.assert_called_once_with("spam")
            app.reload_messages.assert_called_once()
            app.message_list.focus_set.assert_called_once()


def test_gui_exclude_selection_tcl_error():
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.root = root
            app.detail_text = MagicMock()
            app.exclude_var = MagicMock()
            app.message_list = MagicMock()
            app.reload_messages = MagicMock()
            app._search_timer = None

            app.detail_text.tag_ranges.side_effect = tk.TclError("No selection")

            app._exclude_from_selection()
            app.detail_text.tag_ranges.assert_called_with("sel")

            app.detail_text.tag_ranges.side_effect = None
            app.detail_text.tag_ranges.return_value = ("1.0", "1.5")
            app.detail_text.get.side_effect = tk.TclError("Invalid index")
            app._exclude_from_selection()
            app.detail_text.get.assert_called_with("1.0", "1.5")


def test_gui_handle_search_navigation_after_cancel_exception():
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.root = root
            app.message_list = MagicMock()
            app.reload_messages = MagicMock()
            app._search_timer = "invalid_timer_id"

            root.after_cancel.side_effect = Exception("Timer cancel failed")

            app._handle_search_navigation(1)
            assert app._search_timer is None
            assert app.reload_messages.called
