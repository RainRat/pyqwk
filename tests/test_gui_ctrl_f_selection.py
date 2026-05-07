import sys
from unittest.mock import MagicMock, patch

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.simpledialog"] = MagicMock()
sys.modules["tkinter.font"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

import pytest
from pyqwk.gui import QwkGuiApp

@pytest.fixture
def app():
    root = MagicMock()
    root.after = MagicMock()
    # Mock search_var as it's initialized with tk.StringVar()
    with patch("pyqwk.gui.tk.StringVar"), patch("pyqwk.gui.tk.BooleanVar"), patch("pyqwk.gui.font.Font"):
        app = QwkGuiApp(root)
        app.search_var = MagicMock()
        app.detail_text = MagicMock()
        app.search_entry = MagicMock()
        return app

def test_focus_search_with_selection(app):
    """Verify that _focus_search updates search_var when text is selected."""
    # Simulate a selection
    app.detail_text.tag_ranges.return_value = ("1.0", "1.4")
    app.detail_text.get.return_value = "selected"

    app._focus_search()

    app.search_var.set.assert_called_once_with("selected")
    app.search_entry.focus_set.assert_called_once()
    # We use "end" as a string instead of tk.END to avoid importing tkinter
    app.search_entry.selection_range.assert_called_once()

def test_focus_search_without_selection(app):
    """Verify that _focus_search does not update search_var when no text is selected."""
    # Simulate no selection
    app.detail_text.tag_ranges.return_value = ()

    app._focus_search()

    app.search_var.set.assert_not_called()
    app.search_entry.focus_set.assert_called_once()
    app.search_entry.selection_range.assert_called_once()

def test_focus_search_tcl_error(app):
    """Verify that _focus_search handles errors gracefully."""
    # We mock TclError as well since it's in tkinter
    app.detail_text.tag_ranges.side_effect = Exception("TclError simulation")

    # Should not raise exception because of the broad except block or specific handling
    # In my implementation I used 'except tk.TclError'
    # Since tk is mocked, tk.TclError is also a mock.
    # To catch it, we need the side_effect to be an instance of that mock.

    with patch("pyqwk.gui.tk.TclError", new=RuntimeError):
        app.detail_text.tag_ranges.side_effect = RuntimeError("Selection not found")
        app._focus_search()

    app.search_var.set.assert_not_called()
    app.search_entry.focus_set.assert_called_once()
