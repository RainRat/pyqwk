import logging
from unittest.mock import MagicMock, patch
import pytest

from pyqwk import gui
from pyqwk.core import (
    ProcessingSettings,
    show_list_months,
    show_list_years,
    BLOCK_SIZE,
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
    show_list_years(["short.qwk"], settings, logger)


def test_show_list_months_and_years_byte_data_coverage(mocker):
    logger = logging.getLogger("test_months_years_bytes")

    class MockBBSInfo:
        user_name = "BBS User"
        name = "Test BBS"
        bbs_id = "TESTBBS"

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

    # Test show_list_months with short raw byte data (< BLOCK_SIZE)
    mocker.patch(
        "pyqwk.core.load_data",
        return_value=(b"short_data", MockBoardDict()),
    )
    show_list_months(["short.qwk"], settings, logger)

    # Test show_list_months and show_list_years with valid raw byte data (>= BLOCK_SIZE)
    header = b" " * 128
    valid_bytes = header + b" " * 128
    mocker.patch(
        "pyqwk.core.load_data",
        return_value=(valid_bytes, MockBoardDict()),
    )
    show_list_months(["valid.qwk"], settings, logger)
    show_list_years(["valid.qwk"], settings, logger)


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

            app.detail_text.tag_ranges.side_effect = gui.tk.TclError("No selection")

            app._exclude_from_selection()
            app.detail_text.tag_ranges.assert_called_with("sel")


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
