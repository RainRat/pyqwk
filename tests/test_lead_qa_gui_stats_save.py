import sys
import os
from unittest.mock import MagicMock, patch, ANY

mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.simpledialog"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

import pytest
from pyqwk.gui import QwkGuiApp

@pytest.fixture
def app():
    root = MagicMock()
    root.after = MagicMock()
    app = QwkGuiApp(root)
    app.status_label = MagicMock()
    return app

def test_save_report_success(app):
    app.current_paths = ["test.qwk"]
    app.logger = MagicMock()

    with (
        patch("pyqwk.gui.tk.Toplevel") as mock_toplevel,
        patch("pyqwk.gui.tk.Text") as mock_text,
        patch("pyqwk.gui.filedialog.asksaveasfilename", return_value="report.html") as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info,
        patch("pyqwk.gui.calculate_archive_stats", return_value={"file": "test.qwk"}),
        patch("pyqwk.core.show_stats") as mock_show_stats
    ):
        buttons = []
        def mock_button(parent, **kwargs):
            btn = MagicMock()
            btn.kwargs = kwargs
            buttons.append(btn)
            return btn

        with patch("pyqwk.gui.ttk.Button", side_effect=mock_button):
            app.show_stats_window()

        save_btn = next(b for b in buttons if b.kwargs.get("text") == "Save Report...")
        save_report_cmd = save_btn.kwargs["command"]

        save_report_cmd()

        mock_ask.assert_called_once()
        mock_show_stats.assert_called_once()
        args, _ = mock_show_stats.call_args
        assert args[0] == ["test.qwk"]
        assert args[1].format == "html"
        assert args[1].output_mode == "file"
        assert args[1].output_path == "report.html"
        mock_info.assert_called_once_with("Report Saved", ANY)

def test_save_report_cancelled(app):
    app.current_paths = ["test.qwk"]

    with (
        patch("pyqwk.gui.tk.Toplevel"),
        patch("pyqwk.gui.tk.Text"),
        patch("pyqwk.gui.filedialog.asksaveasfilename", return_value="") as mock_ask,
        patch("pyqwk.core.show_stats") as mock_show_stats,
        patch("pyqwk.gui.calculate_archive_stats", return_value={"file": "test.qwk"})
    ):
        buttons = []
        def mock_button(parent, **kwargs):
            btn = MagicMock()
            btn.kwargs = kwargs
            buttons.append(btn)
            return btn

        with patch("pyqwk.gui.ttk.Button", side_effect=mock_button):
            app.show_stats_window()

        save_btn = next(b for b in buttons if b.kwargs.get("text") == "Save Report...")
        save_report_cmd = save_btn.kwargs["command"]

        save_report_cmd()

        mock_ask.assert_called_once()
        mock_show_stats.assert_not_called()

def test_save_report_error(app):
    app.current_paths = ["test.qwk"]
    app.logger = MagicMock()

    with (
        patch("pyqwk.gui.tk.Toplevel"),
        patch("pyqwk.gui.tk.Text"),
        patch("pyqwk.gui.filedialog.asksaveasfilename", return_value="report.json") as mock_ask,
        patch("pyqwk.gui.messagebox.showerror") as mock_error,
        patch("pyqwk.gui.calculate_archive_stats", return_value={"file": "test.qwk"}),
        patch("pyqwk.core.show_stats", side_effect=Exception("Disk full")) as mock_show_stats
    ):
        buttons = []
        def mock_button(parent, **kwargs):
            btn = MagicMock()
            btn.kwargs = kwargs
            buttons.append(btn)
            return btn

        with patch("pyqwk.gui.ttk.Button", side_effect=mock_button):
            app.show_stats_window()

        save_btn = next(b for b in buttons if b.kwargs.get("text") == "Save Report...")
        save_report_cmd = save_btn.kwargs["command"]

        save_report_cmd()

        mock_ask.assert_called_once()
        mock_show_stats.assert_called_once()
        mock_error.assert_any_call("Save Report Error", "Disk full")
