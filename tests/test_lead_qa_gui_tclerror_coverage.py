import tkinter as tk
from unittest.mock import MagicMock, patch
from pyqwk.gui import QwkGuiApp

def test_focus_exclude_tclerror_handler():
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.root = root
            app.detail_text = MagicMock()
            app.exclude_entry = MagicMock()
            app.exclude_var = MagicMock()

            app.detail_text.tag_ranges.side_effect = tk.TclError("Mock TclError")

            root.focus_get.return_value = None

            app._focus_exclude()

            app.detail_text.tag_ranges.assert_called_with("sel")
            app.exclude_entry.focus_set.assert_called_once()
