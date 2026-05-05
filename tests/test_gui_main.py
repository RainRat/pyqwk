import sys
import argparse
from unittest.mock import MagicMock, patch

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

from pyqwk.gui import main


def test_gui_main_with_paths():
    """Test that gui.main correctly passes the paths argument to QwkGuiApp."""
    with (
        patch("pyqwk.gui.tk.Tk") as mock_tk_class,
        patch("pyqwk.gui.QwkGuiApp") as mock_app_class,
        patch("pyqwk.gui.expand_paths") as mock_expand,
        patch("argparse.ArgumentParser.parse_args") as mock_parse_args,
    ):
        mock_parse_args.return_value = argparse.Namespace(paths=["test.qwk"])
        mock_expand.return_value = ["test.qwk"]

        main()

        mock_tk_class.assert_called_once()
        mock_expand.assert_called_once_with(["test.qwk"])
        mock_app_class.assert_called_once_with(
            mock_tk_class.return_value, initial_paths=["test.qwk"]
        )
        mock_tk_class.return_value.mainloop.assert_called_once()


def test_gui_main_without_paths():
    """Test that gui.main works without path arguments."""
    with (
        patch("pyqwk.gui.tk.Tk") as mock_tk_class,
        patch("pyqwk.gui.QwkGuiApp") as mock_app_class,
        patch("pyqwk.gui.expand_paths") as mock_expand,
        patch("argparse.ArgumentParser.parse_args") as mock_parse_args,
    ):
        mock_parse_args.return_value = argparse.Namespace(paths=[])
        mock_expand.return_value = []

        main()

        mock_tk_class.assert_called_once()
        mock_expand.assert_called_once_with([])
        mock_app_class.assert_called_once_with(
            mock_tk_class.return_value, initial_paths=[]
        )
        mock_tk_class.return_value.mainloop.assert_called_once()
