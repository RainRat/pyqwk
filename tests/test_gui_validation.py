import sys
import os
from unittest.mock import MagicMock, patch, ANY, mock_open

# Mock tkinter before any pyqwk.gui imports
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
    # Mock some methods that might be called during init
    root.after = MagicMock()
    return QwkGuiApp(root)


def test_validate_no_path(app):
    """Test that validating shows a warning when no paths are loaded."""
    app.current_paths = []

    with patch("pyqwk.gui.messagebox.showwarning") as mock_warning:
        app.validate_current_archives()
        mock_warning.assert_called_once_with("Archive Validation", "Please open an archive first.")


def test_validate_single_archive_valid(app):
    """Test validating a single valid archive path."""
    app.current_paths = ["test.qwk"]
    app.logger = MagicMock()

    mock_res = {
        "valid": True,
        "format": "qwk",
        "messages_count": 42,
        "errors": [],
        "warnings": [],
    }

    with (
        patch("pyqwk.gui.validate_archive", return_value=mock_res) as mock_val,
        patch("pyqwk.gui.tk.Toplevel") as mock_toplevel,
    ):
        mock_win = MagicMock()
        mock_toplevel.return_value = mock_win
        mock_txt = MagicMock()

        with patch("pyqwk.gui.tk.Text", return_value=mock_txt):
            app.validate_current_archives()

        mock_val.assert_called_once_with("test.qwk", app.logger, "cp437")
        mock_toplevel.assert_called_once()
        mock_txt.insert.assert_any_call(ANY, "VALID\n", "valid")


def test_validate_single_archive_invalid(app):
    """Test validating a single invalid archive path with errors and warnings."""
    app.current_paths = ["test.qwk"]
    app.logger = MagicMock()

    mock_res = {
        "valid": False,
        "format": "rep",
        "messages_count": 5,
        "errors": ["Bad alignment"],
        "warnings": ["Missing password"],
    }

    with (
        patch("pyqwk.gui.validate_archive", return_value=mock_res) as mock_val,
        patch("pyqwk.gui.tk.Toplevel") as mock_toplevel,
    ):
        mock_win = MagicMock()
        mock_toplevel.return_value = mock_win
        mock_txt = MagicMock()

        with patch("pyqwk.gui.tk.Text", return_value=mock_txt):
            app.validate_current_archives()

        mock_val.assert_called_once_with("test.qwk", app.logger, "cp437")
        mock_toplevel.assert_called_once()
        mock_txt.insert.assert_any_call(ANY, "INVALID\n", "invalid")
        mock_txt.insert.assert_any_call(ANY, "  ❌ Bad alignment\n", "error")
        mock_txt.insert.assert_any_call(ANY, "  ⚠️  Missing password\n", "warning")


def test_validate_archive_exception(app):
    """Test validation when validate_archive raises an exception."""
    app.current_paths = ["test.qwk"]
    app.logger = MagicMock()

    with (
        patch("pyqwk.gui.validate_archive", side_effect=Exception("Disk read error")) as mock_val,
        patch("pyqwk.gui.tk.Toplevel") as mock_toplevel,
    ):
        mock_win = MagicMock()
        mock_toplevel.return_value = mock_win
        mock_txt = MagicMock()

        with patch("pyqwk.gui.tk.Text", return_value=mock_txt):
            app.validate_current_archives()

        mock_val.assert_called_once()
        mock_toplevel.assert_called_once()
        # Verify it handled exception and inserted failure details
        mock_txt.insert.assert_any_call(ANY, "  ❌ Validation failed with exception: Disk read error\n", "error")


def test_validate_save_report(app):
    """Test saving the validation report to a file successfully."""
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
        patch("pyqwk.gui.tk.Toplevel") as mock_toplevel,
        patch("pyqwk.gui.filedialog.asksaveasfilename", return_value="report.txt") as mock_save_dlg,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info,
    ):
        mock_win = MagicMock()
        mock_toplevel.return_value = mock_win
        mock_txt = MagicMock()
        mock_txt.get.return_value = "Mock validation report content"

        # Capture the callback passed to the Save Report button
        save_btn_callback = None

        def mock_button(*args, **kwargs):
            nonlocal save_btn_callback
            if kwargs.get("text") == "Save Report...":
                save_btn_callback = kwargs.get("command")
            return MagicMock()

        with (
            patch("pyqwk.gui.tk.Text", return_value=mock_txt),
            patch("pyqwk.gui.ttk.Button", side_effect=mock_button),
        ):
            app.validate_current_archives()

        assert save_btn_callback is not None

        # Now trigger the callback
        m_open = mock_open()
        with patch("builtins.open", m_open):
            save_btn_callback()

        mock_save_dlg.assert_called_once()
        m_open.assert_called_once_with("report.txt", "w", encoding="utf-8")
        m_open().write.assert_called_once_with("Mock validation report content")
        mock_info.assert_called_once()


def test_validate_save_report_error(app):
    """Test saving the validation report when file writing raises an error."""
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
        patch("pyqwk.gui.tk.Toplevel") as mock_toplevel,
        patch("pyqwk.gui.filedialog.asksaveasfilename", return_value="report.txt"),
        patch("pyqwk.gui.messagebox.showerror") as mock_error,
    ):
        mock_win = MagicMock()
        mock_toplevel.return_value = mock_win
        mock_txt = MagicMock()
        mock_txt.get.return_value = "Mock validation report content"

        save_btn_callback = None

        def mock_button(*args, **kwargs):
            nonlocal save_btn_callback
            if kwargs.get("text") == "Save Report...":
                save_btn_callback = kwargs.get("command")
            return MagicMock()

        with (
            patch("pyqwk.gui.tk.Text", return_value=mock_txt),
            patch("pyqwk.gui.ttk.Button", side_effect=mock_button),
        ):
            app.validate_current_archives()

        assert save_btn_callback is not None

        # Now trigger the callback and make it raise an error
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            save_btn_callback()

        mock_error.assert_called_once_with("Save Report Error", "Permission denied")
