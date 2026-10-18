import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

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

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
        }


def test_search_entry_bindings(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Check if Shift-Return is bound
    app.search_entry.bind.assert_any_call("<Shift-Return>", app._on_search_shift_enter)


def test_on_search_enter_navigation(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Pressing Enter in search field when no search matches are present reloads messages and shifts focus to message_list
    app._search_timer = None
    app.root.focus_get.return_value = app.search_entry
    with patch.object(app, "reload_messages") as mock_reload:
        res = app._on_search_enter(MagicMock())
        mock_reload.assert_called_once()
        app.message_list.focus_set.assert_called_once()
        assert res == "break"

    # Pressing Enter in search field when search matches are present navigates forward through matches
    app._search_matches = [("1.0", "1.5")]
    app.root.focus_get.return_value = app.search_entry
    with patch.object(app, "_navigate_search_matches") as mock_nav:
        res = app._on_search_enter(MagicMock())
        mock_nav.assert_called_once_with(1)
        assert res == "break"


def test_on_search_shift_enter_navigation(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Navigate back if matches exist and focused
    app._search_matches = [("1.0", "1.5")]
    app.root.focus_get.return_value = app.search_entry
    with patch.object(app, "_navigate_search_matches") as mock_nav:
        res = app._on_search_shift_enter(MagicMock())
        mock_nav.assert_called_with(-1)
        assert res == "break"


def test_handle_search_navigation_pending_timer(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    app._search_timer = "active_timer_id"
    with patch.object(app, "reload_messages") as mock_reload:
        app._handle_search_navigation(1)
        mock_reload.assert_called_once()
        app.message_list.focus_set.assert_called_once()


def test_welcome_screen_updated_shortcuts(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    app.detail_text.insert.reset_mock()
    app._render_welcome_screen()

    # Check if Enter and Shift+Enter are mentioned in the shortcuts
    found_enter = False
    found_shift_enter = False

    all_calls_text = ""
    for call in app.detail_text.insert.call_args_list:
        for arg in call.args:
            all_calls_text += str(arg) + " "

    if "Enter" in all_calls_text and "Find Next (Search)" in all_calls_text:
        found_enter = True
    if "Shift+Enter" in all_calls_text and "Find Previous (Search)" in all_calls_text:
        found_shift_enter = True

    assert found_enter
    assert found_shift_enter


def test_navigate_search_matches_skips_zero_match_messages(mock_gui_deps):
    """Verify that navigating search matches skips intermediate messages containing 0 matches."""
    root = MagicMock()
    app = QwkGuiApp(root)
    app.search_var.get.return_value = "target"
    app._search_matches = [("1.0", "1.6")]
    app._current_match_idx = 0
    app._get_all_tree_items = MagicMock(return_value=["0", "1", "2"])

    app.message_list = MagicMock()
    app.message_list.selection.return_value = ("0",)

    # Mock _select_relative_message to simulate moving to item "1" (0 matches) then item "2" (1 match)
    call_count = 0

    def mock_select_rel(delta, force=False):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            app._search_matches = []
            return True
        elif call_count == 2:
            app._search_matches = [("2.0", "2.6")]
            return True
        return False

    app._select_relative_message = mock_select_rel

    # Navigate forward
    app._navigate_search_matches(1)

    assert call_count == 2
    assert app._search_matches == [("2.0", "2.6")]
    assert app._pending_match_idx == 0
