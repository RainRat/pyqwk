import logging
import datetime
import tkinter as tk
import pytest

from pyqwk.core import (
    show_list_sources,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
)
from pyqwk.gui import QwkGuiApp


def test_show_list_sources_coverage_gaps(tmp_path, mocker):
    logger = logging.getLogger("test_show_list_sources")
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
    )

    # 1. Test load_data exception logging (line 10494)
    mocker.patch("pyqwk.core.load_data", side_effect=ValueError("Corrupted archive"))
    mock_error = mocker.patch.object(logger, "error")
    show_list_sources(["corrupt.qwk"], settings, logger)
    mock_error.assert_called_once()

    # 2. Test bytearray < BLOCK_SIZE branch (lines 10501-10503) and msg.datetime attribute branch (lines 10511-10512)
    dummy_file = tmp_path / "short.qwk"
    dummy_file.write_bytes(b"short")

    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="All",
        msgfrom="Tester",
        msgsubject="Test Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    msg_with_datetime = ParsedMessage(
        text="Hello world",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
        source_file="valid.qwk",
    )
    # Attach datetime attribute directly
    msg_with_datetime.datetime = datetime.datetime(2024, 1, 1, 12, 0)

    # Message without datetime attribute to exercise fallback _parse_qwk_date
    msg_without_datetime = ParsedMessage(
        text="No dt",
        msgnum=2,
        refnum=None,
        confnum=1,
        header=header,
        source_file="valid.qwk",
    )

    def mock_load_data_side_effect(path, *args, **kwargs):
        if "short" in str(path):
            return bytearray(b"short"), {}
        return [msg_with_datetime, msg_without_datetime], {1: "General"}

    mocker.patch("pyqwk.core.load_data", side_effect=mock_load_data_side_effect)

    # Run show_list_sources with both short file and valid file
    show_list_sources([str(dummy_file), "valid.qwk"], settings, logger)


def test_gui_copy_feedback_after_cancel_exception(mocker):
    root = tk.Tk()
    root.withdraw()
    try:
        app = QwkGuiApp(root)
        app._status_timer = "invalid_timer_id"
        mocker.patch.object(root, "after_cancel", side_effect=Exception("Timer cancel failed"))
        app._copy_to_clipboard("test text", label="Subject")
        # _copy_to_clipboard schedules a new timer after catching the after_cancel exception
        assert app._status_timer is not None
        assert app._status_timer != "invalid_timer_id"
    finally:
        root.destroy()


def test_gui_restore_status_bar_invalid_selection(mocker):
    root = tk.Tk()
    root.withdraw()
    try:
        app = QwkGuiApp(root)
        mocker.patch.object(app.message_list, "selection", return_value=("invalid_iid",))
        mock_update = mocker.patch.object(app, "_update_status_bar")
        app._restore_status_bar()
        mock_update.assert_called_once_with(None)
    finally:
        root.destroy()


def test_gui_handle_search_navigation_else_branch(mocker):
    root = tk.Tk()
    root.withdraw()
    try:
        app = QwkGuiApp(root)
        app._search_timer = None

        # Case A: focus is search_entry, but _search_matches is empty -> hits else branch
        mocker.patch.object(app.root, "focus_get", return_value=app.search_entry)
        app._search_matches = []
        mock_reload = mocker.patch.object(app, "reload_messages")
        mock_focus = mocker.patch.object(app.message_list, "focus_set")
        app._handle_search_navigation(1)
        mock_reload.assert_called_once()
        mock_focus.assert_called_once()

        # Case B: focus is NOT search_entry -> hits else branch
        mocker.patch.object(app.root, "focus_get", return_value=None)
        mock_reload.reset_mock()
        mock_focus.reset_mock()
        app._handle_search_navigation(1)
        mock_reload.assert_called_once()
        mock_focus.assert_called_once()
    finally:
        root.destroy()
