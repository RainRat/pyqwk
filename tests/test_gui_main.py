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

def test_gui_main_with_path():
    """Test that gui.main correctly passes the path argument to QwkGuiApp."""
    with patch("pyqwk.gui.tk.Tk") as mock_tk_class, \
         patch("pyqwk.gui.QwkGuiApp") as mock_app_class, \
         patch("argparse.ArgumentParser.parse_args") as mock_parse_args:

        mock_parse_args.return_value = argparse.Namespace(path="test.qwk")

        main()

        mock_tk_class.assert_called_once()
        mock_app_class.assert_called_once_with(mock_tk_class.return_value, initial_path="test.qwk")
        mock_tk_class.return_value.mainloop.assert_called_once()

def test_gui_main_without_path():
    """Test that gui.main works without a path argument."""
    with patch("pyqwk.gui.tk.Tk") as mock_tk_class, \
         patch("pyqwk.gui.QwkGuiApp") as mock_app_class, \
         patch("argparse.ArgumentParser.parse_args") as mock_parse_args:

        mock_parse_args.return_value = argparse.Namespace(path=None)

        main()

        mock_tk_class.assert_called_once()
        mock_app_class.assert_called_once_with(mock_tk_class.return_value, initial_path=None)
        mock_tk_class.return_value.mainloop.assert_called_once()
