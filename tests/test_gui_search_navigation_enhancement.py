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

    # Case 1: Search matches exist, no timer, focused -> should navigate
    app._search_matches = [("1.0", "1.5")]
    app._search_timer = None
    app.root.focus_get.return_value = app.search_entry
    with patch.object(app, "_navigate_search_matches") as mock_nav:
        app._on_search_enter(MagicMock())
        mock_nav.assert_called_with(1)

    # Case 2: No search matches -> should reload and focus list
    app._search_matches = []
    app._search_timer = None
    with patch.object(app, "reload_messages") as mock_reload:
        app._on_search_enter(MagicMock())
        mock_reload.assert_called_once()
        app.message_list.focus_set.assert_called_once()

    # Case 3: Search timer exists (pending) -> should reload even if matches exist
    app._search_matches = [("1.0", "1.5")]
    app._search_timer = "after#1"
    app.message_list.focus_set.reset_mock()
    with patch.object(app, "reload_messages") as mock_reload:
        app._on_search_enter(MagicMock())
        mock_reload.assert_called_once()
        app.message_list.focus_set.assert_called_once()


def test_on_search_shift_enter_navigation(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Navigate back if matches exist and focused
    app._search_matches = [("1.0", "1.5")]
    app.root.focus_get.return_value = app.search_entry
    with patch.object(app, "_navigate_search_matches") as mock_nav:
        app._on_search_shift_enter(MagicMock())
        mock_nav.assert_called_with(-1)


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
