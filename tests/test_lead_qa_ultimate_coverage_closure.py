import logging
from unittest.mock import MagicMock, patch

import pytest

from pyqwk.core import (
    BBSInfo,
    ConferenceMap,
    ProcessingSettings,
    _create_progress_bar,
    process_multiple_files,
    show_attachments,
    show_list_authors,
    show_list_bbs,
    show_list_conferences,
    show_stats,
    show_threads,
)


def test_create_progress_bar_not_quiet():
    mock_tqdm_mod = MagicMock()
    mock_pbar = MagicMock()
    mock_tqdm_mod.tqdm.return_value = mock_pbar
    with patch.dict("sys.modules", {"tqdm": mock_tqdm_mod}):
        res = _create_progress_bar(100, quiet=False, desc="Testing")
        assert res == mock_pbar


def test_structured_file_progress_bar_updates(message_factory, tmp_path):
    m = message_factory(1, 0, "Progress Test")
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
        format="text",
        separator="line",
        output_mode="file",
        output_path=str(tmp_path / "out.txt"),
        encoding="cp437",
        quiet=False,
    )
    logger = logging.getLogger("test_pbar")

    board_map = ConferenceMap()
    mock_tqdm_mod = MagicMock()
    with patch.dict("sys.modules", {"tqdm": mock_tqdm_mod}):
        with patch("pyqwk.core.load_data", return_value=([m], board_map)):
            process_multiple_files(
                ["dummy.json"], str(tmp_path / "out"), settings, logger
            )
            show_stats(["dummy.json"], settings, logger)


def test_show_threads_raw_bytes_and_root_depth_fallback(message_factory):
    m1 = message_factory(1, 0, "Reply Subj")
    m1.depth = 1
    m1.thread_id = 10

    settings = ProcessingSettings(
        verbose=False,
        private=False,
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
    logger = logging.getLogger("test_threads")

    qwk_bytes = bytearray(256)

    def mock_load(path, logger_arg, enc):
        if path == "bytes.qwk":
            return qwk_bytes, ConferenceMap()
        return [m1], ConferenceMap()

    with patch("pyqwk.core.load_data", side_effect=mock_load):
        with patch("pyqwk.core.parse_messages", return_value=[m1]):
            with patch("pyqwk.core._order_messages_by_thread", return_value=[m1]):
                with patch("pyqwk.core._write_text_output") as mock_write:
                    show_threads(["bytes.qwk", "msg.json"], settings, logger)
                    mock_write.assert_called_once()


def test_show_attachments_uncovered_branches(message_factory):
    m = message_factory(1, 0, "Subj")
    m.discover_attachments = lambda: ["file.txt"]
    bbs_info = BBSInfo(user_name="AutoBBSUser")
    board_map = ConferenceMap()
    board_map.bbs_info = bbs_info

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
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        my_name=None,
        quiet=True,
    )
    logger = logging.getLogger("test_attachments")

    short_bytes = b"short"
    long_bytes = bytearray(256)

    def mock_load(path, logger_arg, enc):
        if path == "short.qwk":
            return short_bytes, board_map
        if path == "long.qwk":
            return long_bytes, board_map
        if path == "err.qwk":
            raise ValueError("Error loading")
        return [m], board_map

    with patch("pyqwk.core.load_data", side_effect=mock_load):
        with patch("pyqwk.core.parse_messages", return_value=[m]):
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_attachments(
                    ["short.qwk", "long.qwk", "err.qwk", "msg.json"], settings, logger
                )
                mock_write.assert_called_once()


def test_show_list_bbs_raw_bytes(message_factory):
    m = message_factory(1, 0, "Subj")
    board_map = ConferenceMap()

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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )
    logger = logging.getLogger("test_bbs")

    short_bytes = b"short"
    long_bytes = bytearray(256)

    def mock_load(path, logger_arg, enc):
        if path == "short.qwk":
            return short_bytes, board_map
        return long_bytes, board_map

    with patch("pyqwk.core.load_data", side_effect=mock_load):
        with patch("pyqwk.core.parse_messages", return_value=[m]):
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_list_bbs(["short.qwk", "long.qwk"], settings, logger)
                mock_write.assert_called_once()


def test_show_list_conferences_raw_bytes(message_factory):
    m = message_factory(1, 0, "Subj")
    board_map = ConferenceMap()

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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )
    logger = logging.getLogger("test_conf")

    short_bytes = b"short"
    long_bytes = bytearray(256)

    def mock_load(path, logger_arg, enc):
        if path == "short.qwk":
            return short_bytes, board_map
        return long_bytes, board_map

    with patch("pyqwk.core.load_data", side_effect=mock_load):
        with patch("pyqwk.core.parse_messages", return_value=[m]):
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_list_conferences(["short.qwk", "long.qwk"], settings, logger)
                mock_write.assert_called_once()


def test_show_list_authors_raw_bytes(message_factory):
    m = message_factory(1, 0, "Subj")
    board_map = ConferenceMap()

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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )
    logger = logging.getLogger("test_auth")

    short_bytes = b"short"
    long_bytes = bytearray(256)

    def mock_load(path, logger_arg, enc):
        if path == "short.qwk":
            return short_bytes, board_map
        if path == "long.qwk":
            return long_bytes, board_map
        return [m], board_map

    with patch("pyqwk.core.load_data", side_effect=mock_load):
        with patch("pyqwk.core.parse_messages", return_value=[m]):
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_list_authors(["short.qwk", "long.qwk", "valid.json"], settings, logger)
                mock_write.assert_called_once()


def test_gui_validation_report_cancel_save():
    mock_tk = MagicMock()
    mock_ttk = MagicMock()
    with patch.dict(
        "sys.modules",
        {
            "tkinter": mock_tk,
            "tkinter.filedialog": MagicMock(),
            "tkinter.messagebox": MagicMock(),
            "tkinter.simpledialog": MagicMock(),
            "tkinter.ttk": mock_ttk,
        },
    ):
        from pyqwk.gui import QwkGuiApp

        root = MagicMock()
        root.after = MagicMock()
        app = QwkGuiApp(root)
        app.current_paths = ["test.qwk"]
        app.logger = MagicMock()

        mock_res = {
            "valid": True,
            "format": "qwk",
            "messages_count": 10,
            "errors": [],
            "warnings": [],
        }

        mock_txt = MagicMock()
        save_btn_callback = None

        def mock_button(*args, **kwargs):
            nonlocal save_btn_callback
            if kwargs.get("text") == "Save Report...":
                save_btn_callback = kwargs.get("command")
            return MagicMock()

        with (
            patch("pyqwk.gui.validate_archive", return_value=mock_res),
            patch("pyqwk.gui.tk.Toplevel"),
            patch(
                "pyqwk.gui.filedialog.asksaveasfilename", return_value=""
            ) as mock_save,
            patch("pyqwk.gui.tk.Text", return_value=mock_txt),
            patch("pyqwk.gui.ttk.Button", side_effect=mock_button),
        ):
            app.validate_current_archives()
            assert save_btn_callback is not None
            save_btn_callback()
            mock_save.assert_called_once()


def test_gui_validation_outer_exception():
    mock_tk = MagicMock()
    mock_ttk = MagicMock()
    with patch.dict(
        "sys.modules",
        {
            "tkinter": mock_tk,
            "tkinter.filedialog": MagicMock(),
            "tkinter.messagebox": MagicMock(),
            "tkinter.simpledialog": MagicMock(),
            "tkinter.ttk": mock_ttk,
        },
    ):
        from pyqwk.gui import QwkGuiApp

        root = MagicMock()
        root.after = MagicMock()
        app = QwkGuiApp(root)
        app.current_paths = ["test.qwk"]
        app.logger = MagicMock()

        mock_res = {
            "valid": True,
            "format": "qwk",
            "messages_count": 10,
            "errors": [],
            "warnings": [],
        }

        with (
            patch("pyqwk.gui.validate_archive", return_value=mock_res),
            patch(
                "pyqwk.gui.tk.Toplevel",
                side_effect=RuntimeError("Toplevel creation failed"),
            ),
            patch("pyqwk.gui.messagebox.showerror") as mock_err,
        ):
            app.validate_current_archives()
            mock_err.assert_called_once_with(
                "Validation Error", "Toplevel creation failed"
            )
