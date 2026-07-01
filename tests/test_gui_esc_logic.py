from unittest.mock import MagicMock, patch
import pytest
from pyqwk.gui import QwkGuiApp

@pytest.fixture
def mock_gui_deps():
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.filedialog") as mock_fd,
        patch("pyqwk.gui.messagebox") as mock_mb,
    ):
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

def test_clear_search_focused_clears_search(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Mock entries and variables
    app.search_entry = MagicMock()
    app.exclude_entry = MagicMock()
    app.search_var = MagicMock()
    app.exclude_var = MagicMock()
    app.message_list = MagicMock()

    # Case 1: search_entry is focused
    root.focus_get.return_value = app.search_entry
    with patch.object(app, "reload_messages") as mock_reload:
        app.clear_search()
        app.search_var.set.assert_called_with("")
        app.exclude_var.set.assert_called_with("")
        mock_reload.assert_called_once()
        app.message_list.focus_set.assert_called_once()

def test_clear_search_unfocused_with_content_clears_search(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    app.search_entry = MagicMock()
    app.exclude_entry = MagicMock()
    app.search_var = MagicMock()
    app.exclude_var = MagicMock()
    app.message_list = MagicMock()

    # Case 2: No focus, but search_var has content
    root.focus_get.return_value = None
    app.search_var.get.return_value = "query"

    with patch.object(app, "reload_messages") as mock_reload:
        app.clear_search()
        app.search_var.set.assert_called_with("")
        app.exclude_var.set.assert_called_with("")
        mock_reload.assert_called_once()
        app.message_list.focus_set.assert_called_once()

def test_clear_search_no_content_resets_all_filters(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    app.search_entry = MagicMock()
    app.exclude_entry = MagicMock()
    app.search_var = MagicMock()
    app.exclude_var = MagicMock()
    app.message_list = MagicMock()

    # Case 3: No focus, no content
    root.focus_get.return_value = None
    app.search_var.get.return_value = ""
    app.exclude_var.get.return_value = ""

    with patch.object(app, "clear_filters") as mock_clear:
        app.clear_search()
        mock_clear.assert_called_once()

def test_is_any_filter_active_includes_msg_links(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Manually configure variables to avoid interference
    app.search_var = MagicMock()
    app.exclude_var = MagicMock()
    app.bbs_combo = MagicMock()
    app.conf_combo = MagicMock()
    app.private_var = MagicMock()

    app.has_attach_var = MagicMock()
    app.mine_var = MagicMock()
    app.on_this_day_var = MagicMock()
    app.has_links_var = MagicMock()
    app.has_emails_var = MagicMock()
    app.has_phones_var = MagicMock()
    app.has_ansi_var = MagicMock()
    app.has_msg_links_var = MagicMock()

    # Reset all relevant variables to inactive
    app.search_var.get.return_value = ""
    app.exclude_var.get.return_value = ""
    app.bbs_combo.get.return_value = "All BBSes"
    app.conf_combo.get.return_value = "All Conferences"
    app.private_var.get.return_value = True # private shown

    vars_to_test = [
        app.has_attach_var, app.mine_var, app.on_this_day_var,
        app.has_links_var, app.has_emails_var, app.has_phones_var,
        app.has_ansi_var, app.has_msg_links_var
    ]

    for v in vars_to_test:
        v.get.return_value = False

    # Check initially inactive
    assert app._is_any_filter_active() is False

    # Check has_msg_links_var makes it active
    app.has_msg_links_var.get.return_value = True
    assert app._is_any_filter_active() is True
