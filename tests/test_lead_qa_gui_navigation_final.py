import sys
from unittest.mock import MagicMock, patch
import pytest
import tkinter as tk

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk
sys.modules["tkinter.simpledialog"] = MagicMock()

from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader

@pytest.fixture
def app():
    root = MagicMock()
    root.title.return_value = "pyqwk - Graphical Reader"
    with patch("pyqwk.gui.tk") as m_tk, \
         patch("pyqwk.gui.ttk") as m_ttk, \
         patch("pyqwk.gui.simpledialog"):

        m_tk.BooleanVar.side_effect = lambda **kwargs: MagicMock()
        m_tk.StringVar.side_effect = lambda **kwargs: MagicMock()
        m_tk.IntVar.side_effect = lambda **kwargs: MagicMock()

        # Define constants used in _navigate_search_matches
        m_tk.END = "end"

        app = QwkGuiApp(root)
        app.message_list = MagicMock()
        app.detail_text = MagicMock()
        app.status_label = MagicMock()
        app.search_count_label = MagicMock()
        return app

def test_navigate_search_matches_cycling(app):
    """Test _navigate_search_matches cycling and UI updates (lines 1090-1110)."""
    app._search_matches = [("1.0", "1.5"), ("2.0", "2.5")]
    app._current_match_idx = 0

    # Cycle forward
    app._navigate_search_matches(1)
    assert app._current_match_idx == 1
    app.detail_text.tag_add.assert_called_with("current_search_highlight", "2.0", "2.5")
    app.search_count_label.config.assert_called_with(text="2 / 2")

    # Cycle forward again (wrap around)
    app._navigate_search_matches(1)
    assert app._current_match_idx == 0
    app.detail_text.tag_add.assert_called_with("current_search_highlight", "1.0", "1.5")
    app.search_count_label.config.assert_called_with(text="1 / 2")

    # Cycle backward (wrap around to end)
    app._navigate_search_matches(-1)
    assert app._current_match_idx == 1

def test_on_search_changed_debouncing(app):
    """Test _on_search_changed debouncing logic (lines 1158-1160)."""
    app._search_timer = "timer1"

    app._on_search_changed()

    app.root.after_cancel.assert_called_with("timer1")
    app.root.after.assert_called_with(250, app.reload_messages)
    assert app._search_timer == app.root.after.return_value

def test_on_search_enter_with_pending_timer(app):
    """Test _on_search_enter triggers immediate reload if timer is pending (lines 1165-1167)."""
    app._search_timer = "timer1"

    app._on_search_enter(MagicMock())

    app.root.after_cancel.assert_called_with("timer1")
    assert app._search_timer is None
    app.message_list.focus_set.assert_called_once()

def test_open_folder_success(app):
    """Test open_folder successfully loads messages (lines 1153-1154)."""
    with patch("pyqwk.gui.filedialog.askdirectory", return_value="/path/to/archives"), \
         patch("pyqwk.gui.expand_paths", return_value=["/path/to/archives/test.qwk"]), \
         patch.object(app, "load_messages") as mock_load:

        app.open_folder()

        assert app.current_paths == ["/path/to/archives/test.qwk"]
        mock_load.assert_called_with(["/path/to/archives/test.qwk"])

def test_open_folder_no_archives(app):
    """Test open_folder when no archives are found (lines 1149-1151)."""
    with patch("pyqwk.gui.filedialog.askdirectory", return_value="/path/to/empty"), \
         patch("pyqwk.gui.expand_paths", return_value=[]), \
         patch("pyqwk.gui.messagebox.showinfo") as mock_info:

        app.open_folder()

        mock_info.assert_called_once()
