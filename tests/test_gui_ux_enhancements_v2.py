import sys
from unittest.mock import MagicMock, patch
import pytest
from pyqwk.gui import QwkGuiApp

@pytest.fixture
def mock_gui_deps():
    with patch("pyqwk.gui.tk") as mock_tk, \
         patch("pyqwk.gui.ttk") as mock_ttk, \
         patch("pyqwk.gui.filedialog") as mock_fd, \
         patch("pyqwk.gui.messagebox") as mock_mb:

        # Configure Variable mocks
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

        # Tkinter constants
        mock_tk.END = "end"
        mock_tk.HORIZONTAL = "horizontal"
        mock_tk.VERTICAL = "vertical"
        mock_tk.BOTH = "both"
        mock_tk.X = "x"
        mock_tk.Y = "y"
        mock_tk.LEFT = "left"
        mock_tk.RIGHT = "right"
        mock_tk.TOP = "top"
        mock_tk.BOTTOM = "bottom"
        mock_tk.SUNKEN = "sunken"
        mock_tk.W = "w"
        mock_tk.E = "e"
        mock_tk.WORD = "word"
        mock_tk.DISABLED = "disabled"
        mock_tk.NORMAL = "normal"
        mock_tk.INSERT = "insert"

        # Mock classes/types
        class TclError(Exception):
            pass
        mock_tk.TclError = TclError

        # Mock Combobox
        mock_combo = MagicMock()
        mock_ttk.Combobox.return_value = mock_combo

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
            "combo": mock_combo,
            "bbs_combo": MagicMock(),
            "conf_combo": MagicMock(),
        }

def test_clear_search_progressive(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Manually assign mocks to comboboxes to avoid using the same return_value from mock_ttk.Combobox
    app.bbs_combo = mock_gui_deps["bbs_combo"]
    app.conf_combo = mock_gui_deps["conf_combo"]

    # Case 1: Search bar has text
    app.search_var.get.return_value = "some search"
    with patch.object(app, 'reload_messages') as mock_reload, \
         patch.object(app, 'clear_filters') as mock_clear_filters:
        app.clear_search()
        app.search_var.set.assert_called_with("")
        mock_reload.assert_called_once()
        mock_clear_filters.assert_not_called()

    # Case 2: Search bar is already empty
    app.search_var.set.reset_mock()
    app.search_var.get.return_value = ""
    with patch.object(app, 'reload_messages') as mock_reload, \
         patch.object(app, 'clear_filters') as mock_clear_filters:
        app.clear_search()
        mock_clear_filters.assert_called_once()

def test_clear_filters_resets_search(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    app.bbs_combo = mock_gui_deps["bbs_combo"]
    app.conf_combo = mock_gui_deps["conf_combo"]

    with patch.object(app, 'reload_messages') as mock_reload:
        app.clear_filters()
        app.search_var.set.assert_called_with("")
        mock_reload.assert_called_once()
